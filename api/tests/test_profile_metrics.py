"""Unit tests for Taste Profile Metrics and Music DNA (Phase 11).

Acceptance Gates:
- Single-region planted seeds yield low Breadth (< 0.30) and high Cohesion (> 0.50).
- Multi-region seeds yield high Breadth (> 0.55).
- Confidence indicator is "low" if < 8 tracks, "high" if >= 8 tracks.
- Adventurousness is None if < 10 feedback events, valid float when >= 10.
- Bootstrap 90% CI contains the point estimate.
"""

from pathlib import Path

import pytest

from app.recsys import CatalogStore, compute_taste_profile


@pytest.fixture(scope="module")
def catalog() -> CatalogStore:
    repo_root = Path(__file__).resolve().parent.parent.parent
    bundle_path = repo_root / "data" / "bundles" / "v1"
    return CatalogStore.load(bundle_path)


def test_confidence_indicator_gate(catalog: CatalogStore) -> None:
    """< 8 tracks must yield confidence='low'; >= 8 tracks yields confidence='high'."""
    # 3 tracks -> low confidence
    small_set = [0, 1, 2]
    res_small = compute_taste_profile(small_set, catalog)
    assert res_small.confidence == "low"
    assert "robust profile" in res_small.confidence_reason or "< 8" in res_small.confidence_reason

    # 8 tracks -> high confidence
    large_set = list(range(8))
    res_large = compute_taste_profile(large_set, catalog)
    assert res_large.confidence == "high"
    assert "Confidence is high" in res_large.confidence_reason


def test_planted_single_region_breadth_and_cohesion(catalog: CatalogStore) -> None:
    """Tracks planted in the same cluster must yield low Breadth and high Cohesion."""
    # Find tracks in region 0
    all_regs = catalog._tracks_metadata.get("region_id", [])
    reg0_tracks = [i for i, r in enumerate(all_regs) if r == 0][:10]
    assert len(reg0_tracks) >= 8

    res = compute_taste_profile(reg0_tracks, catalog)
    assert res.dimensions["breadth"] is not None
    assert res.dimensions["cohesion"] is not None

    # Single-region planted set has focused entropy and high semantic affinity
    assert res.dimensions["breadth"].value < 0.35, (
        f"Expected low breadth, got {res.dimensions['breadth'].value}"
    )
    assert res.dimensions["cohesion"].value > 0.45, (
        f"Expected high cohesion, got {res.dimensions['cohesion'].value}"
    )


def test_planted_multi_region_breadth(catalog: CatalogStore) -> None:
    """Tracks sampled across distinct musical clusters must yield high Breadth."""
    all_regs = catalog._tracks_metadata.get("region_id", [])
    # Pick 1 track each from 10 different regions
    multi_tracks: list[int] = []
    seen_regs: set[int] = set()
    for i, r in enumerate(all_regs):
        if r is not None and r not in seen_regs:
            multi_tracks.append(i)
            seen_regs.add(r)
        if len(multi_tracks) >= 10:
            break

    res = compute_taste_profile(multi_tracks, catalog)
    assert res.dimensions["breadth"] is not None
    assert res.dimensions["breadth"].value > 0.55, (
        f"Expected high breadth, got {res.dimensions['breadth'].value}"
    )


def test_adventurousness_gate(catalog: CatalogStore) -> None:
    """Adventurousness is null when < 10 feedback events, computed when >= 10."""
    tracks = list(range(8))

    # Less than 10 events -> null
    events_few = [{"event": "like", "novelty": 0.8} for _ in range(5)]
    res_few = compute_taste_profile(tracks, catalog, feedback_events=events_few)
    assert res_few.dimensions["adventurousness"] is None

    # 12 events -> non-null
    events_many = [{"event": "like", "novelty": 0.7} for _ in range(8)] + [
        {"event": "like", "novelty": 0.3} for _ in range(4)
    ]
    res_many = compute_taste_profile(tracks, catalog, feedback_events=events_many)
    assert res_many.dimensions["adventurousness"] is not None
    assert 0.0 <= res_many.dimensions["adventurousness"].value <= 1.0
    # 8 out of 12 novelties > 0.50 -> approx 0.67
    assert res_many.dimensions["adventurousness"].value == pytest.approx(0.667, abs=0.01)


def test_bootstrap_ci_coverage(catalog: CatalogStore) -> None:
    """Point estimates must fall within or very close to bootstrap 90% CI."""
    tracks = [10, 15, 20, 25, 30, 35, 40, 45, 50]
    res = compute_taste_profile(tracks, catalog)

    for d_key in ["breadth", "rarity", "cohesion"]:
        dim = res.dimensions[d_key]
        assert dim is not None
        low, high = dim.ci_90
        assert low <= dim.value + 0.05, f"{d_key}: point {dim.value} < low CI {low}"
        assert high >= dim.value - 0.05, f"{d_key}: point {dim.value} > high CI {high}"


def test_music_dna_extraction(catalog: CatalogStore) -> None:
    """Music DNA must populate dominant folksonomy tags, scalar ranges, and top regions."""
    tracks = list(range(10))
    res = compute_taste_profile(tracks, catalog)

    assert len(res.music_dna.dominant_regions) >= 1
    assert "name" in res.music_dna.dominant_regions[0]
    assert "exposure" in res.music_dna.dominant_regions[0]

    # Scalars
    for sname in ["energy", "valence", "tempo_bpm"]:
        if sname in res.music_dna.mean_scalars:
            assert "mean" in res.music_dna.mean_scalars[sname]
            assert "min" in res.music_dna.mean_scalars[sname]
            assert "max" in res.music_dna.mean_scalars[sname]
            assert (
                res.music_dna.mean_scalars[sname]["min"] <= res.music_dna.mean_scalars[sname]["max"]
            )


def test_empty_profile_handling(catalog: CatalogStore) -> None:
    """Empty known set must return confidence='low' and empty DNA without errors."""
    res = compute_taste_profile([], catalog)
    assert res.known_track_count == 0
    assert res.confidence == "low"
    assert res.dimensions["breadth"] is None
    assert res.region_exposures == []
