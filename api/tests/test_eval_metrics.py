"""Unit tests for offline evaluation metrics, playlist continuation, runner, and ablations."""

import math
import sys
from pathlib import Path

# Ensure root and api are on path
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "api"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from eval.metrics import (  # noqa: E402
    artist_coverage,
    catalog_coverage,
    gini_exposure,
    intra_list_diversity,
    novelty,
    region_entropy,
    seed_region_hit_rate,
)
from eval.playlist_continuation import compute_dcg_at_k, extract_mbid  # noqa: E402
from eval.runner import run_evaluation  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402

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
    """Generate a clean deterministic mock catalog bundle for evaluation tests."""
    bundle_dir = tmp_path_factory.mktemp("mock_bundle_eval_test")
    generate_mock_catalog(bundle_dir)
    return CatalogStore.load(bundle_dir)


# ============================================================================
# Hand-computed metric unit tests
# ============================================================================


def test_ild_hand_computed() -> None:
    """Test ILD against hand-computed values:

    ILD = 1 - mean(cos(v_i, v_j))
    """
    # 1. Single track -> 0.0
    vecs = np.array([[1.0, 0.0]], dtype=np.float32)
    assert intra_list_diversity([0], vecs) == 0.0

    # 2. Two identical vectors -> cos = 1.0 -> ILD = 0.0
    vecs_identical = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    assert intra_list_diversity([0, 1], vecs_identical) == 0.0

    # 3. Two orthogonal vectors -> cos = 0.0 -> ILD = 1.0
    vecs_ortho = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    assert pytest.approx(intra_list_diversity([0, 1], vecs_ortho), 1e-6) == 1.0

    # 4. Two opposite vectors -> cos = -1.0 -> ILD = 2.0
    vecs_opposite = np.array([[1.0, 0.0], [-1.0, 0.0]], dtype=np.float32)
    assert pytest.approx(intra_list_diversity([0, 1], vecs_opposite), 1e-6) == 2.0

    # 5. Three pairwise orthogonal vectors in R^3 -> all pairwise dot = 0 -> ILD = 1.0
    vecs_3d = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float32,
    )
    assert pytest.approx(intra_list_diversity([0, 1, 2], vecs_3d), 1e-6) == 1.0

    # 6. Three vectors with known angles: 0, pi/3 (60 deg), pi/2 (90 deg)
    # cos(0, 60) = 0.5
    # cos(0, 90) = 0.0
    # cos(60, 90) = cos(30 deg) = sqrt(3)/2 ≈ 0.8660254038
    # mean_cos = (0.5 + 0.0 + 0.8660254038) / 3 = 0.4553418
    # ILD = 1.0 - 0.4553418 = 0.5446582
    v0 = [1.0, 0.0]
    v1 = [math.cos(math.pi / 3), math.sin(math.pi / 3)]
    v2 = [0.0, 1.0]
    vecs_angles = np.array([v0, v1, v2], dtype=np.float32)
    expected_mean_cos = (0.5 + 0.0 + math.sqrt(3) / 2) / 3.0
    expected_ild = 1.0 - expected_mean_cos
    assert pytest.approx(intra_list_diversity([0, 1, 2], vecs_angles), rel=1e-5) == expected_ild


def test_novelty_hand_computed() -> None:
    """Test novelty self-information against hand-computed values:

    Nov(S) = (1/|S|) * sum -log2(p_i), where p_i = pop_i / total_pop.
    """
    # Empty list or zero total -> 0.0
    assert novelty([], 100.0) == 0.0
    assert novelty([10.0], 0.0) == 0.0

    # 2 items with pop=25, total=100 -> p_i = 0.25 -> -log2(0.25) = 2.0 bits
    assert pytest.approx(novelty([25.0, 25.0], 100.0), 1e-6) == 2.0

    # 2 items with pop=50 and pop=25, total=100
    # p1 = 0.5 -> -log2(0.5) = 1.0 bit
    # p2 = 0.25 -> -log2(0.25) = 2.0 bits
    # mean = (1.0 + 2.0) / 2 = 1.5 bits
    assert pytest.approx(novelty([50.0, 25.0], 100.0), 1e-6) == 1.5

    # 4 items with pop=12.5, total=100 -> p_i = 0.125 -> -log2(0.125) = 3.0 bits
    assert pytest.approx(novelty([12.5, 12.5, 12.5, 12.5], 100.0), 1e-6) == 3.0


def test_region_entropy_hand_computed() -> None:
    """Test Shannon entropy of regions against hand-computed values:

    H = - sum p * log2(p).
    """
    # Single item or empty -> 0.0
    assert region_entropy([]) == 0.0
    assert region_entropy([1]) == 0.0

    # All items from identical region -> H = 0.0
    assert region_entropy([2, 2, 2, 2]) == 0.0

    # Uniform distribution across 4 distinct regions -> p = 0.25 for each
    # H = - 4 * (0.25 * log2(0.25)) = - 4 * (0.25 * -2.0) = 2.0 bits
    assert pytest.approx(region_entropy([0, 1, 2, 3]), 1e-6) == 2.0

    # 2 regions with ratio 3:1 -> p = [0.75, 0.25]
    # H = -(0.75 * log2(0.75) + 0.25 * log2(0.25))
    #   = -(0.75 * (-0.4150375) + 0.25 * (-2.0))
    #   = -(-0.3112781 - 0.5) = 0.8112781 bits
    expected_entropy = -(0.75 * math.log2(0.75) + 0.25 * math.log2(0.25))
    assert pytest.approx(region_entropy([0, 0, 0, 1]), rel=1e-5) == expected_entropy

    # None handling
    assert pytest.approx(region_entropy([0, None, 1, 2, 3]), 1e-6) == 2.0


def test_gini_exposure_hand_computed() -> None:
    """Test Gini coefficient against hand-computed values:

    - Uniform exposure -> G = 0.0
    - Complete monopoly (1 item has all, rest 0) -> G = (N-1)/N
    """
    # Uniform exposure: each of 4 items has 5 impressions
    assert pytest.approx(gini_exposure([5, 5, 5, 5], 4), 1e-6) == 0.0

    # Complete monopoly: 1 item has 4 impressions, remaining 3 have 0
    # N = 4, y_sorted = [0, 0, 0, 4]
    # G = (2*4 - 4 - 1)*4 / (4 * 4) = 3 * 4 / 16 = 0.75 = (4 - 1) / 4
    assert pytest.approx(gini_exposure([0, 0, 0, 4], 4), 1e-6) == 0.75

    # Zero total exposure -> 0.0
    assert gini_exposure([0, 0, 0], 3) == 0.0
    assert gini_exposure([], 0) == 0.0

    # Auto zero-padding: passing 2 exposed items when catalog has 4 items
    assert pytest.approx(gini_exposure([0, 4], 4), 1e-6) == 0.75


def test_artist_and_catalog_coverage() -> None:
    """Test artist and catalog coverage fractions."""
    # Artist coverage
    recs_artists = [["ArtistA", "ArtistB"], ["ArtistB", "ArtistC"]]
    # 3 unique artists out of 10
    assert pytest.approx(artist_coverage(recs_artists, 10), 1e-6) == 0.3
    assert artist_coverage([], 10) == 0.0
    assert artist_coverage([["A"]], 0) == 0.0

    # Catalog coverage
    recs_tracks = [[1, 2, 3], [3, 4, 5]]
    # 5 unique tracks out of 20
    assert pytest.approx(catalog_coverage(recs_tracks, 20), 1e-6) == 0.25
    assert catalog_coverage([], 20) == 0.0


def test_seed_region_hit_rate() -> None:
    """Test seed region hit rate calculation and None filtering."""
    seeds = [1, 2]
    recs = [1, 2, 3, 4]
    # 2 out of 4 recs match seed regions {1, 2} -> 0.5
    assert pytest.approx(seed_region_hit_rate(seeds, recs), 1e-6) == 0.5

    # With Nones
    seeds_with_none = [1, None]
    recs_with_none = [1, None, 3, 1]
    # Valid recs: [1, 3, 1], hits: 2 / 3
    assert pytest.approx(seed_region_hit_rate(seeds_with_none, recs_with_none), 1e-6) == 2.0 / 3.0

    # Empty
    assert seed_region_hit_rate([], [1, 2]) == 0.0
    assert seed_region_hit_rate([1], []) == 0.0


def test_compute_dcg_at_k() -> None:
    """Test DCG@K computation: rank r contributes 1.0 / log2(r + 2)."""
    hits = [1, 0, 1]
    # rank 0: 1.0 / log2(2) = 1.0
    # rank 1: 0.0
    # rank 2: 1.0 / log2(4) = 0.5
    # total DCG = 1.5
    assert pytest.approx(compute_dcg_at_k(hits, 3), 1e-6) == 1.5
    assert pytest.approx(compute_dcg_at_k(hits, 1), 1e-6) == 1.0
    assert compute_dcg_at_k([0, 0, 0], 3) == 0.0


def test_extract_mbid() -> None:
    """Test extraction of MBIDs from JSPF track structures."""
    # URI format
    t1 = {"identifier": ["https://musicbrainz.org/recording/12345678-1234-1234-1234-123456789abc"]}
    assert extract_mbid(t1) == "12345678-1234-1234-1234-123456789abc"

    # Direct UUID identifier
    t2 = {"identifier": "12345678-1234-1234-1234-123456789abc"}
    assert extract_mbid(t2) == "12345678-1234-1234-1234-123456789abc"

    # Explicit mbid key
    t3 = {"mbid": "12345678-1234-1234-1234-123456789abc"}
    assert extract_mbid(t3) == "12345678-1234-1234-1234-123456789abc"

    # Missing / malformed
    assert extract_mbid({}) is None
    assert extract_mbid({"identifier": "not-a-valid-uuid"}) is None


# ============================================================================
# Recsys Ablation and Determinism Tests
# ============================================================================


def test_ablation_flags_effect(mock_catalog_store: CatalogStore) -> None:
    """Verify that ablation switches (-audio, -mmr, -pop_corr) produce differing ranking outputs."""
    catalog = mock_catalog_store
    seed_ids = [catalog.get_id(10), catalog.get_id(20), catalog.get_id(30)]

    # 1. Full system
    cfg_full = RecsysConfig(use_audio=True, use_mmr=True, popularity_correction=True)
    modes = build_modes(seed_ids, catalog, config=cfg_full)
    pool_full = generate_candidates(modes, catalog, k_per_mode=150, config=cfg_full)
    scored_full = score_candidates(pool_full, catalog, config=cfg_full)
    res_full = rerank_candidates(
        pool_full, scored_full, catalog, discovery=0.35, n=30, config=cfg_full
    )
    full_ids = [it.track_id for it in res_full.items]

    # 2. Ablation: -audio
    cfg_no_audio = RecsysConfig(use_audio=False, use_mmr=True, popularity_correction=True)
    pool_no_audio = generate_candidates(modes, catalog, k_per_mode=150, config=cfg_no_audio)
    scored_no_audio = score_candidates(pool_no_audio, catalog, config=cfg_no_audio)
    res_no_audio = rerank_candidates(
        pool_no_audio, scored_no_audio, catalog, discovery=0.35, n=30, config=cfg_no_audio
    )
    no_audio_ids = [it.track_id for it in res_no_audio.items]

    # Candidates and scores must reflect absence of audio channel
    assert full_ids != no_audio_ids, "-audio ablation must alter recommendation ranking"

    # 3. Ablation: -mmr
    cfg_no_mmr = RecsysConfig(use_audio=True, use_mmr=False, popularity_correction=True)
    res_no_mmr = rerank_candidates(
        pool_full, scored_full, catalog, discovery=0.35, n=30, config=cfg_no_mmr
    )
    no_mmr_ids = [it.track_id for it in res_no_mmr.items]

    # Without MMR diversity penalties, ranking order changes
    assert full_ids != no_mmr_ids, "-mmr ablation must alter recommendation ranking"

    # 4. Ablation: -pop_corr
    cfg_no_pop = RecsysConfig(use_audio=True, use_mmr=True, popularity_correction=False)
    res_no_pop = rerank_candidates(
        pool_full, scored_full, catalog, discovery=0.35, n=30, config=cfg_no_pop
    )
    no_pop_ids = [it.track_id for it in res_no_pop.items]

    assert full_ids != no_pop_ids, "-pop_corr ablation must alter recommendation ranking"


def test_eval_runner_determinism(mock_catalog_store: CatalogStore) -> None:
    """Verify that run_evaluation produces identical metrics given fixed seeds."""
    catalog = mock_catalog_store
    seedsets = [
        {
            "name": "test_set_1",
            "seed_track_ids": [catalog.get_id(1), catalog.get_id(2), catalog.get_id(3)],
        },
        {
            "name": "test_set_2",
            "seed_track_ids": [catalog.get_id(10), catalog.get_id(11), catalog.get_id(12)],
        },
    ]

    res1 = run_evaluation(catalog, seedsets, output_dir=None, is_ci_mode=False)
    res2 = run_evaluation(catalog, seedsets, output_dir=None, is_ci_mode=False)

    for sys_name in res1:
        m1 = res1[sys_name]
        m2 = res2[sys_name]
        for metric_name in [
            "mean_ild",
            "mean_novelty",
            "mean_entropy",
            "mean_hit_rate",
            "artist_coverage",
            "catalog_coverage",
            "gini_exposure",
        ]:
            msg = f"{sys_name} {metric_name} must be deterministic"
            assert m1[metric_name] == m2[metric_name], msg
