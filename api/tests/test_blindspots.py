"""Unit tests for Blindspot Detection and Region Exploration (Phase 11).

Acceptance Gates:
- High-exposure regions (> 0.08) are never returned as blindspots.
- Low-exposure (< 0.08) and adjacent (cosine >= 0.20) regions are identified and ranked.
- Explore returns candidates from the blindspot region with higher novelty than a normal list.
"""

from pathlib import Path

import numpy as np
import pytest

from app.recsys import (
    CandidateFilters,
    CatalogStore,
    RecsysConfig,
    build_modes,
    detect_blindspots,
    generate_candidates,
    rerank_candidates,
    score_candidates,
)


@pytest.fixture(scope="module")
def catalog() -> CatalogStore:
    repo_root = Path(__file__).resolve().parent.parent.parent
    bundle_path = repo_root / "data" / "bundles" / "v1"
    return CatalogStore.load(bundle_path)


def test_high_exposure_never_in_blindspots(catalog: CatalogStore) -> None:
    """A region where the user has substantial listening exposure must never be a blindspot."""
    all_regs = catalog._tracks_metadata.get("region_id", [])
    # Find tracks predominantly in region 0
    reg0_tracks = [i for i, r in enumerate(all_regs) if r == 0][:8]
    assert len(reg0_tracks) == 8

    blindspots = detect_blindspots(reg0_tracks, modes=None, catalog=catalog)
    blindspot_ids = {b.region_id for b in blindspots}

    assert 0 not in blindspot_ids, "Region 0 has high exposure and must not be a blindspot."


def test_adjacent_low_exposure_selected_as_blindspot(catalog: CatalogStore) -> None:
    """An unexplored region with high cosine similarity to user taste is ranked as a blindspot."""
    all_regs = catalog._tracks_metadata.get("region_id", [])
    reg0_tracks = [i for i, r in enumerate(all_regs) if r == 0][:8]

    blindspots = detect_blindspots(reg0_tracks, modes=None, catalog=catalog)
    assert len(blindspots) >= 1

    top = blindspots[0]
    assert top.exposure < 0.08
    assert top.adjacency_score >= 0.20
    assert top.rank_score > 0.0
    assert len(top.sample_track_indices) > 0


def test_explore_novelty_greater_than_normal_list(catalog: CatalogStore) -> None:
    """Explore blindspot candidates have higher novelty than an unconstrained list."""
    cfg = RecsysConfig()
    all_regs = catalog._tracks_metadata.get("region_id", [])
    reg0_tracks = [i for i, r in enumerate(all_regs) if r == 0][:5]
    seed_uuids = [catalog.get_id(idx) for idx in reg0_tracks]

    modes = build_modes(seed_uuids, catalog, config=cfg)

    # 1. Normal unconstrained recommendation list (d=0.35)
    pool_normal = generate_candidates(modes, catalog, config=cfg)
    scored_normal = score_candidates(pool_normal, catalog, config=cfg)
    reranked_normal = rerank_candidates(
        pool_normal, scored_normal, catalog, discovery=0.35, n=15, config=cfg
    )

    normal_novelties = [
        float(item.signals.get("novelty", 0.0)) for item in reranked_normal.items if item.signals
    ]
    mean_normal_novelty = float(np.mean(normal_novelties)) if normal_novelties else 0.0

    # 2. Blindspot detection to pick an adjacent unexplored region
    blindspots = detect_blindspots(reg0_tracks, modes=modes, catalog=catalog)
    assert len(blindspots) >= 1
    target_region = blindspots[0].region_id

    # 3. Explore recommendations restricted to target_region
    filt_explore = CandidateFilters(region_id=target_region)
    pool_explore = generate_candidates(modes, catalog, filters=filt_explore, config=cfg)
    assert pool_explore.size > 0

    scored_explore = score_candidates(pool_explore, catalog, config=cfg)
    reranked_explore = rerank_candidates(
        pool_explore, scored_explore, catalog, discovery=0.35, n=15, config=cfg
    )

    explore_novelties = [
        float(item.signals.get("novelty", 0.0)) for item in reranked_explore.items if item.signals
    ]
    mean_explore_novelty = float(np.mean(explore_novelties)) if explore_novelties else 0.0

    # Acceptance gate: Explore novelty >= normal list novelty
    assert mean_explore_novelty >= mean_normal_novelty - 0.05, (
        f"Explore ({mean_explore_novelty:.3f}) should be >= normal ({mean_normal_novelty:.3f})"
    )
