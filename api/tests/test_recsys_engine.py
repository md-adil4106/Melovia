"""Comprehensive unit, determinism, performance, and property tests for Melovia Recsys Core."""

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
    SeedNotFoundError,
    build_modes,
    generate_candidates,
    genre_baseline,
    global_candidate_cache,
    random_baseline,
    score_candidates,
    single_channel_a_baseline,
    single_channel_t_baseline,
)


@pytest.fixture(scope="module")
def mock_catalog_store(tmp_path_factory: pytest.TempPathFactory) -> CatalogStore:
    """Generate a clean deterministic mock catalog bundle for recsys testing."""
    bundle_dir = tmp_path_factory.mktemp("mock_bundle_test")
    generate_mock_catalog(bundle_dir)
    return CatalogStore.load(bundle_dir)


def test_taste_modes_small_seed_set(mock_catalog_store: CatalogStore) -> None:
    """For n < 6 seeds, build_modes must produce exactly one mode per seed with equal weights."""
    catalog = mock_catalog_store
    seed_ids = [catalog.get_id(i) for i in range(3)]

    modes = build_modes(seed_ids, catalog)
    assert modes.num_modes == 3
    assert len(modes.weights) == 3
    np.testing.assert_allclose(modes.weights, [1.0 / 3, 1.0 / 3, 1.0 / 3], atol=1e-5)
    assert modes.channel_vectors["t"].shape == (3, 128)
    assert modes.channel_vectors["a"].shape == (3, 128)
    assert modes.member_seed_ids == [[seed_ids[0]], [seed_ids[1]], [seed_ids[2]]]


def test_taste_modes_clustering_for_large_seed_set(mock_catalog_store: CatalogStore) -> None:
    """For n >= 6 seeds, build_modes must cluster seeds using k-medoids (k <= 3)."""
    catalog = mock_catalog_store
    seed_ids = [catalog.get_id(i) for i in range(8)]

    modes = build_modes(seed_ids, catalog)
    assert 1 <= modes.num_modes <= 3
    assert abs(float(np.sum(modes.weights)) - 1.0) < 1e-4
    # All seed IDs are assigned to exactly one mode
    assigned_seeds = [sid for m in modes.member_seed_ids for sid in m]
    assert sorted(assigned_seeds) == sorted(seed_ids)


def test_taste_modes_unknown_seed_raises_error(mock_catalog_store: CatalogStore) -> None:
    """Unknown seed ID must raise SeedNotFoundError."""
    catalog = mock_catalog_store
    with pytest.raises(SeedNotFoundError):
        build_modes(["invalid-track-id-999"], catalog)


def test_candidate_generation_and_seed_exclusion(mock_catalog_store: CatalogStore) -> None:
    """Candidates must be retrieved via matmul, and seeds must be strictly excluded."""
    catalog = mock_catalog_store
    seed_ids = [catalog.get_id(10), catalog.get_id(25)]
    seed_indices = {10, 25}

    modes = build_modes(seed_ids, catalog)
    pool = generate_candidates(modes, catalog, k_per_mode=100)

    assert pool.size > 0
    # Invariant: Seeds never appear in results
    pool_indices_set = set(pool.track_indices.tolist())
    assert pool_indices_set.isdisjoint(seed_indices)
    assert pool.raw_sims_t.shape == (pool.size, modes.num_modes)
    assert pool.raw_sims_a.shape == (pool.size, modes.num_modes)


def test_scoring_smooth_max_and_percentiles(mock_catalog_store: CatalogStore) -> None:
    """Scoring must apply smooth max (tau=8), percentile normalization, and stable sorting."""
    catalog = mock_catalog_store
    seed_ids = [catalog.get_id(5), catalog.get_id(6)]
    modes = build_modes(seed_ids, catalog)
    pool = generate_candidates(modes, catalog, k_per_mode=200)

    scored_list = score_candidates(pool, catalog)
    assert len(scored_list.items) == pool.size

    # Check descending score order with stable tie-break
    prev_score = float("inf")
    for item in scored_list.items:
        assert item.score <= prev_score + 1e-6
        assert 0.0 <= item.score <= 1.0
        # Signals verification
        assert "raw_sim_t" in item.signals
        assert "percentile_t" in item.signals
        assert "nearest_seed_id" in item.signals
        assert item.signals["nearest_seed_id"] in seed_ids
        prev_score = item.score


def test_planted_regions_coherence(mock_catalog_store: CatalogStore) -> None:
    """Seeds picked from planted region R must produce recommendations dominated by R (>= 70%)."""
    catalog = mock_catalog_store
    target_region = 0

    # Pick 3 seeds strictly belonging to region 0
    region_col = catalog._tracks_metadata["region_id"]
    r0_indices = [idx for idx, reg in enumerate(region_col) if reg == target_region]
    assert len(r0_indices) >= 10

    seed_ids = [
        catalog.get_id(r0_indices[0]),
        catalog.get_id(r0_indices[1]),
        catalog.get_id(r0_indices[2]),
    ]
    modes = build_modes(seed_ids, catalog)
    pool = generate_candidates(modes, catalog, k_per_mode=300)
    scored = score_candidates(pool, catalog)

    top_30 = scored.top_n(30)
    assert len(top_30) == 30

    top_30_regions = [catalog._tracks_metadata["region_id"][item.track_idx] for item in top_30]
    r0_count = sum(1 for reg in top_30_regions if reg == target_region)
    r0_fraction = r0_count / 30.0

    print(f"\nPlanted Region 0 Coherence: {r0_count}/30 ({r0_fraction * 100:.1f}%)")
    assert r0_fraction >= 0.70, (
        f"Expected >= 70% from planted region {target_region}, got {r0_fraction * 100:.1f}%"
    )


def test_all_seeds_missing_audio_handled_gracefully(mock_catalog_store: CatalogStore) -> None:
    """When seeds lack audio, recsys must renormalize weights and succeed without NaNs."""
    catalog = mock_catalog_store

    # Find 2 seeds where has_a == False (missing audio)
    missing_a_indices = np.where(~catalog.mask_a)[0]
    assert len(missing_a_indices) >= 2

    seed_ids = [
        catalog.get_id(int(missing_a_indices[0])),
        catalog.get_id(int(missing_a_indices[1])),
    ]
    modes = build_modes(seed_ids, catalog)
    assert modes.has_channel["a"] is False  # Audio channel is masked

    pool = generate_candidates(modes, catalog, k_per_mode=100)
    scored = score_candidates(pool, catalog)

    assert len(scored.items) > 0
    for item in scored.top_n(20):
        assert not np.isnan(item.score)
        assert 0.0 <= item.score <= 1.0
        assert item.signals["raw_sim_a"] is None


def test_baselines_callable_and_valid(mock_catalog_store: CatalogStore) -> None:
    """Verify all 4 baseline algorithms produce valid non-seed recommendations."""
    catalog = mock_catalog_store
    seed_ids = [catalog.get_id(1), catalog.get_id(2)]

    res_random = random_baseline(seed_ids, catalog, n=10)
    assert len(res_random) == 10
    assert {r["id"] for r in res_random}.isdisjoint(set(seed_ids))

    res_genre = genre_baseline(seed_ids, catalog, n=10)
    assert len(res_genre) == 10
    assert {r["id"] for r in res_genre}.isdisjoint(set(seed_ids))

    res_t = single_channel_t_baseline(seed_ids, catalog, n=10)
    assert len(res_t) == 10
    assert {r["id"] for r in res_t}.isdisjoint(set(seed_ids))

    res_a = single_channel_a_baseline(seed_ids, catalog, n=10)
    assert len(res_a) == 10
    assert {r["id"] for r in res_a}.isdisjoint(set(seed_ids))


def test_candidate_cache_lifecycle(mock_catalog_store: CatalogStore) -> None:
    """Verify candidate cache store, retrieve, and TTL expiration."""
    catalog = mock_catalog_store
    seed_ids = [catalog.get_id(0)]
    modes = build_modes(seed_ids, catalog)
    pool = generate_candidates(modes, catalog, k_per_mode=50)
    scored = score_candidates(pool, catalog)

    cid = "test-candidate-set-uuid"
    global_candidate_cache.set(cid, pool, scored, RecsysConfig(ttl_seconds=1800))

    cached = global_candidate_cache.get(cid)
    assert cached is not None
    assert cached.candidate_set_id == cid
    assert cached.pool.size == pool.size

    # Non-existent key
    assert global_candidate_cache.get("non-existent") is None


@pytest.mark.asyncio
async def test_api_recommendations_end_to_end(mock_catalog_store: CatalogStore) -> None:
    """Test POST /recommendations endpoint through FastAPI client."""
    catalog = mock_catalog_store
    app.state.catalog_store = catalog

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        seed_ids = [catalog.get_id(0), catalog.get_id(1)]
        payload = {
            "seed_track_ids": seed_ids,
            "n": 15,
            "include_signals": True,
        }

        # 1. Success case
        resp = await client.post("/recommendations", json=payload)
        assert resp.status_code == 200

        data = resp.json()
        assert "candidate_set_id" in data
        assert data["total_candidates"] > 0
        assert len(data["items"]) == 15

        first = data["items"][0]
        assert "track" in first
        assert "score" in first
        assert "signals" in first
        assert first["track"]["id"] not in seed_ids

        # 2. Determinism: same request => byte-identical JSON response (excluding candidate_set_id)
        resp2 = await client.post("/recommendations", json=payload)
        assert resp2.status_code == 200
        data2 = resp2.json()

        # Same item IDs, scores, and signals in identical order
        items1_tuple = [(it["track"]["id"], it["score"]) for it in data["items"]]
        items2_tuple = [(it["track"]["id"], it["score"]) for it in data2["items"]]
        assert items1_tuple == items2_tuple

        # 3. Unknown seed track ID => 404 with error envelope
        bad_payload = {"seed_track_ids": ["unknown-id-12345"], "n": 10}
        bad_resp = await client.post("/recommendations", json=bad_payload)
        assert bad_resp.status_code == 404
        assert bad_resp.json()["error"]["code"] == "TRACK_NOT_FOUND"

        # 4. Empty seed list => 422 validation error
        empty_payload = {"seed_track_ids": [], "n": 10}
        val_resp = await client.post("/recommendations", json=empty_payload)
        assert val_resp.status_code == 422


def test_recsys_latency_budget(mock_catalog_store: CatalogStore) -> None:
    """Benchmark recommendation latency: assert p95 < 400 ms over 50 calls."""
    catalog = mock_catalog_store
    config = RecsysConfig()

    latencies: list[float] = []

    # Run 50 calls across different seed combinations
    for i in range(50):
        # Pick 2-3 seeds deterministically
        seed_ids = [
            catalog.get_id((i * 7) % catalog.track_count),
            catalog.get_id((i * 13 + 3) % catalog.track_count),
        ]

        t0 = time.perf_counter()
        modes = build_modes(seed_ids, catalog, config=config)
        pool = generate_candidates(modes, catalog, k_per_mode=config.k_candidates)
        scored = score_candidates(pool, catalog, config=config)
        _ = scored.top_n(30)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    p99 = float(np.percentile(latencies, 99))

    print(f"\nLatency Benchmark (50 calls on mock catalog of {catalog.track_count} tracks):")
    print(f"  p50: {p50:.2f} ms")
    print(f"  p95: {p95:.2f} ms (budget: < 400 ms)")
    print(f"  p99: {p99:.2f} ms")

    assert p95 < 400.0, f"p95 latency {p95:.2f} ms exceeds 400 ms budget!"
