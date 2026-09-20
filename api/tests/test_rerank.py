"""Tests for Discovery Control (Familiarity <-> Discovery) Reranking and API endpoints."""

import sys
import time
from pathlib import Path

# Ensure root is on path
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402
from app.recsys import (  # noqa: E402
    CatalogStore,
    RecsysConfig,
    build_modes,
    generate_candidates,
    rerank_candidates,
    score_candidates,
)


@pytest.fixture(scope="module")
def mock_catalog_store(tmp_path_factory: pytest.TempPathFactory) -> CatalogStore:
    """Generate a clean deterministic mock catalog bundle for reranking tests."""
    bundle_dir = tmp_path_factory.mktemp("mock_bundle_rerank_test")
    generate_mock_catalog(bundle_dir)
    return CatalogStore.load(bundle_dir)


def test_rerank_determinism(mock_catalog_store: CatalogStore) -> None:
    """Calling rerank_candidates twice with identical inputs must produce byte-identical results."""
    catalog = mock_catalog_store
    config = RecsysConfig()
    seed_ids = [catalog.get_id(10), catalog.get_id(20)]

    modes = build_modes(seed_ids, catalog, config=config)
    pool = generate_candidates(modes, catalog, k_per_mode=300)
    scored = score_candidates(pool, catalog, config=config)

    res1 = rerank_candidates(pool, scored, catalog, discovery=0.5, n=30, config=config)
    res2 = rerank_candidates(pool, scored, catalog, discovery=0.5, n=30, config=config)

    assert len(res1.items) == len(res2.items) == 30
    for it1, it2 in zip(res1.items, res2.items, strict=True):
        assert it1.track_id == it2.track_id
        assert it1.track_idx == it2.track_idx
        assert it1.score == it2.score
        assert it1.signals == it2.signals


def test_d0_overlap_with_phase4_baseline(mock_catalog_store: CatalogStore) -> None:
    """At d = 0.0, the top-30 must achieve >= 90% overlap with the Phase 4 raw score ranking."""
    catalog = mock_catalog_store
    config = RecsysConfig()
    seed_ids = [catalog.get_id(5), catalog.get_id(15), catalog.get_id(25)]

    modes = build_modes(seed_ids, catalog, config=config)
    pool = generate_candidates(modes, catalog, k_per_mode=300)
    scored = score_candidates(pool, catalog, config=config)

    phase4_top30 = [item.track_id for item in scored.top_n(30)]
    reranked_d0 = rerank_candidates(pool, scored, catalog, discovery=0.0, n=30, config=config)
    reranked_top30 = [item.track_id for item in reranked_d0.items]

    overlap = len(set(phase4_top30).intersection(set(reranked_top30)))
    overlap_ratio = overlap / 30.0

    # Acceptance requirement: >= 90% overlap (27/30 tracks)
    assert overlap_ratio >= 0.90, f"Overlap was {overlap_ratio:.2%}, expected >= 90%"


def test_artist_cap_enforced(mock_catalog_store: CatalogStore) -> None:
    """Verify artist cap: max 2 tracks for d < 0.7, max 1 track for d >= 0.7."""
    catalog = mock_catalog_store
    config = RecsysConfig()
    seed_ids = [catalog.get_id(1), catalog.get_id(2)]

    modes = build_modes(seed_ids, catalog, config=config)
    pool = generate_candidates(modes, catalog, k_per_mode=300)
    scored = score_candidates(pool, catalog, config=config)

    # 1. Test d = 0.35 (d < 0.7 => cap is 2)
    reranked_low = rerank_candidates(pool, scored, catalog, discovery=0.35, n=30, config=config)
    artist_counts_low: dict[str, int] = {}
    for item in reranked_low.items:
        art_id = catalog.get_track_dict(item.track_idx)["artist_id"]
        artist_counts_low[art_id] = artist_counts_low.get(art_id, 0) + 1
    assert max(artist_counts_low.values()) <= 2

    # 2. Test d = 0.85 (d >= 0.7 => cap is 1)
    reranked_high = rerank_candidates(pool, scored, catalog, discovery=0.85, n=30, config=config)
    artist_counts_high: dict[str, int] = {}
    for item in reranked_high.items:
        art_id = catalog.get_track_dict(item.track_idx)["artist_id"]
        artist_counts_high[art_id] = artist_counts_high.get(art_id, 0) + 1
    assert max(artist_counts_high.values()) <= 1


def test_monotonicity_across_discovery_values(mock_catalog_store: CatalogStore) -> None:
    """Across d in {0, .25, .5, .75, 1}: novelty and artist-newness non-decreasing."""
    catalog = mock_catalog_store
    config = RecsysConfig()
    d_values = [0.0, 0.25, 0.5, 0.75, 1.0]

    # Test on 3 distinct planted-region seed sets
    region_col = catalog._tracks_metadata["region_id"]
    seed_sets = []
    for reg_id in [0, 1, 2]:
        reg_indices = [idx for idx, reg in enumerate(region_col) if reg == reg_id]
        assert len(reg_indices) >= 5
        seed_sets.append([catalog.get_id(reg_indices[0]), catalog.get_id(reg_indices[1])])

    for seeds in seed_sets:
        modes = build_modes(seeds, catalog, config=config)
        pool = generate_candidates(modes, catalog, k_per_mode=300)
        scored = score_candidates(pool, catalog, config=config)

        mean_novs: list[float] = []
        mean_art_news: list[float] = []
        mean_rels: list[float] = []

        for d in d_values:
            reranked = rerank_candidates(pool, scored, catalog, discovery=d, n=30, config=config)
            items = reranked.items
            assert len(items) == 30

            novs = [float(it.signals["novelty"]) for it in items]
            art_news = [1.0 if it.signals["artist_new"] else 0.0 for it in items]
            rels = [float(it.signals["relevance"]) for it in items]

            mean_nov = float(np.mean(novs))
            mean_art_new = float(np.mean(art_news))
            mean_rel = float(np.mean(rels))

            mean_novs.append(mean_nov)
            mean_art_news.append(mean_art_new)
            mean_rels.append(mean_rel)

            # Relevance floor: floor = 0.6 - 0.3 * d
            expected_floor = 0.6 - 0.3 * d
            assert mean_rel >= expected_floor - 1e-4, (
                f"Mean relevance {mean_rel:.3f} fell below floor {expected_floor:.3f} at d={d}"
            )

        # Monotonicity checks:
        # Novelty at d=1.0 must be significantly higher than at d=0.0
        assert mean_novs[-1] > mean_novs[0], (
            f"Expected higher novelty at d=1.0 than d=0.0: {mean_novs}"
        )
        # Non-decreasing trend across consecutive steps (with small tolerance for discrete rankings)
        for k in range(1, len(d_values)):
            assert mean_novs[k] >= mean_novs[k - 1] - 0.03, (
                f"Novelty decreased from d={d_values[k - 1]} to {d_values[k]}: {mean_novs}"
            )

        # Artist newness at d=1.0 must be >= artist newness at d=0.0
        assert mean_art_news[-1] >= mean_art_news[0]


def test_signals_emitted_correctly(mock_catalog_store: CatalogStore) -> None:
    """Verify that all requested explainability signals are emitted on every item."""
    catalog = mock_catalog_store
    config = RecsysConfig()
    seed_ids = [catalog.get_id(3), catalog.get_id(7)]

    modes = build_modes(seed_ids, catalog, config=config)
    pool = generate_candidates(modes, catalog, k_per_mode=100)
    scored = score_candidates(pool, catalog, config=config)

    res = rerank_candidates(pool, scored, catalog, discovery=0.6, n=15, config=config)
    assert len(res.items) == 15

    for item in res.items:
        sig = item.signals
        assert "novelty" in sig
        assert "familiarity" in sig
        assert "artist_new" in sig
        assert "popularity_pct" in sig
        assert "mmr_penalty" in sig
        assert "relevance" in sig
        assert "utility" in sig
        assert "discovery_score" in sig
        assert "discovery_d" in sig
        assert np.isclose(sig["familiarity"] + sig["novelty"], 1.0, atol=1e-3)
        assert 0.0 <= sig["novelty"] <= 2.0
        assert isinstance(sig["artist_new"], bool)


def test_rerank_latency_benchmark(mock_catalog_store: CatalogStore) -> None:
    """Rerank latency on cached pool must satisfy p95 < 100 ms."""
    catalog = mock_catalog_store
    config = RecsysConfig()
    seed_ids = [catalog.get_id(1), catalog.get_id(10), catalog.get_id(20)]

    modes = build_modes(seed_ids, catalog, config=config)
    pool = generate_candidates(modes, catalog, k_per_mode=config.k_candidates)
    scored = score_candidates(pool, catalog, config=config)

    latencies_ms: list[float] = []
    # Warmup
    for _ in range(5):
        rerank_candidates(pool, scored, catalog, discovery=0.5, n=30, config=config)

    # 50 iterations
    for i in range(50):
        d_val = (i % 10) / 10.0
        t0 = time.perf_counter()
        rerank_candidates(pool, scored, catalog, discovery=d_val, n=30, config=config)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)

    p50 = float(np.percentile(latencies_ms, 50))
    p95 = float(np.percentile(latencies_ms, 95))

    print(f"\n[BENCHMARK] Rerank: p50 = {p50:.2f} ms, p95 = {p95:.2f} ms")
    assert p95 < 100.0, f"Rerank latency p95 was {p95:.2f} ms, exceeding 100 ms budget"


@pytest.mark.asyncio
async def test_recommendations_and_rerank_endpoints(mock_catalog_store: CatalogStore) -> None:
    """Test POST /recommendations and POST /recommendations/rerank via ASGI test client."""
    app.state.catalog_store = mock_catalog_store
    seed_id = mock_catalog_store.get_id(42)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create initial recommendations with discovery=0.25
        payload = {
            "seed_track_ids": [seed_id],
            "n": 20,
            "discovery": 0.25,
            "include_signals": True,
        }
        res = await client.post("/recommendations", json=payload)
        assert res.status_code == 200
        data = res.json()
        cand_set_id = data["candidate_set_id"]
        assert len(data["items"]) == 20
        assert data["items"][0]["signals"]["discovery_d"] == 0.25

        # 2. Rerank the cached candidate set with discovery=0.8
        rerank_payload = {
            "candidate_set_id": cand_set_id,
            "discovery": 0.8,
            "n": 20,
            "include_signals": True,
        }
        rerank_res = await client.post("/recommendations/rerank", json=rerank_payload)
        assert rerank_res.status_code == 200
        rerank_data = rerank_res.json()
        assert rerank_data["candidate_set_id"] == cand_set_id
        assert len(rerank_data["items"]) == 20
        assert rerank_data["items"][0]["signals"]["discovery_d"] == 0.8

        # 3. Request reranking on expired/invalid candidate set => 404 error envelope
        bad_payload = {
            "candidate_set_id": "nonexistent-uuid-12345",
            "discovery": 0.5,
            "n": 20,
        }
        bad_res = await client.post("/recommendations/rerank", json=bad_payload)
        assert bad_res.status_code == 404
        bad_err = bad_res.json()
        assert bad_err["error"]["code"] == "CANDIDATE_SET_EXPIRED"
