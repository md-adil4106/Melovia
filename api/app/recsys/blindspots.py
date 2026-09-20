"""Blindspot Detection and Region Exploration Engine for Melovia (Phase 11).

Architecture Constraints:
- Pure Python and NumPy (zero imports of FastAPI, Starlette, or SQLAlchemy).
- Deterministic: stable sorting by rank score, tie-breaking by region_id.
- Clear bridging explanations between user taste and blindspot regions.
"""

from dataclasses import dataclass

import numpy as np

from app.recsys.catalog import CatalogStore
from app.recsys.taste import Modes


@dataclass(frozen=True)
class BlindspotRegion:
    """A detected musical blindspot region adjacent to user taste."""

    region_id: int
    name: str
    genre_focus: str
    description: str
    top_tags: list[str]
    exposure: float
    adjacency_score: float
    rank_score: float
    bridge_tags: list[str]
    sample_track_indices: list[int]


def detect_blindspots(
    track_indices: list[int],
    modes: Modes | None,
    catalog: CatalogStore,
    exposure_threshold: float = 0.08,
    adjacency_floor: float = 0.05,
) -> list[BlindspotRegion]:
    """Detect and rank unexplored musical regions adjacent to user's taste.

    Args:
        track_indices: Known track indices K.
        modes: Taste modes (if available; otherwise computed from track_indices).
        catalog: Loaded immutable CatalogStore.
        exposure_threshold: Maximum exposure level to qualify as a blindspot (default 0.08).
        adjacency_floor: Minimum centroid similarity to qualify as adjacent bridge (default 0.20).

    Returns:
        List of BlindspotRegion sorted by rank_score descending.
    """
    k_regions = len(catalog.regions) if catalog.regions else 24
    if not catalog.regions or not track_indices:
        return []

    # 1. Compute region exposures over known set K
    reg_primaries = catalog._tracks_metadata.get("region_id", [0] * catalog.track_count)
    reg_secondaries = catalog._tracks_metadata.get("region_id_secondary", reg_primaries)
    reg_w_primaries = catalog._tracks_metadata.get(
        "region_weight_primary", [1.0] * catalog.track_count
    )
    reg_w_secondaries = catalog._tracks_metadata.get(
        "region_weight_secondary", [0.0] * catalog.track_count
    )

    region_counts = np.zeros(k_regions, dtype=np.float64)
    for idx in track_indices:
        r1 = (
            int(reg_primaries[idx])
            if idx < len(reg_primaries) and reg_primaries[idx] is not None
            else 0
        )
        r2 = (
            int(reg_secondaries[idx])
            if idx < len(reg_secondaries) and reg_secondaries[idx] is not None
            else r1
        )
        w1 = float(reg_w_primaries[idx]) if idx < len(reg_w_primaries) else 1.0
        w2 = float(reg_w_secondaries[idx]) if idx < len(reg_w_secondaries) else 0.0

        if 0 <= r1 < k_regions:
            region_counts[r1] += w1
        if 0 <= r2 < k_regions:
            region_counts[r2] += w2

    tot = np.sum(region_counts)
    exposures = region_counts / tot if tot > 0 else np.zeros(k_regions)

    # 2. Extract user taste vectors
    if modes and modes.channel_vectors.get("t") is not None and len(modes.channel_vectors["t"]) > 0:
        taste_vecs = modes.channel_vectors["t"]  # (M, dim_t)
    else:
        # Fall back to mean vector of known tracks
        known_vecs = catalog.vectors_t[track_indices]
        mean_v = np.mean(known_vecs, axis=0, keepdims=True)
        taste_vecs = np.asarray(
            mean_v / np.maximum(np.linalg.norm(mean_v, axis=1, keepdims=True), 1e-9),
            dtype=np.float32,
        )

    # User's known tags
    user_tags: set[str] = set()
    track_tags_col = catalog._tracks_metadata.get("tags")
    for idx in track_indices:
        t_list = track_tags_col[idx] if track_tags_col and idx < len(track_tags_col) else []
        if t_list:
            user_tags.update(t_list)

    # 3. Evaluate each region
    blindspot_candidates: list[BlindspotRegion] = []
    region_dict = {r["region_id"]: r for r in catalog.regions}

    for r_idx in range(k_regions):
        exp = float(exposures[r_idx])
        if exp >= exposure_threshold:
            # Already well-explored
            continue

        r_info = region_dict.get(r_idx, {})
        center_t = np.array(r_info.get("center_t", []), dtype=np.float32)
        if len(center_t) == 0:
            continue

        # Adjacency: maximum cosine similarity to any taste mode
        sims_to_modes = np.dot(taste_vecs, center_t)
        adjacency = float(np.max(sims_to_modes))

        if adjacency < adjacency_floor:
            # Too distant / unrelated
            continue

        rank_score = float(adjacency * (1.0 - exp))

        # Bridge tags: overlap between user tags and region tags, or top region tags
        reg_tags = r_info.get("top_tags", [])
        shared = [t for t in reg_tags if t in user_tags]
        bridge = shared if shared else reg_tags[:3]

        # Representative sample tracks in this region
        # Find top 3 tracks in region r_idx with highest similarity to taste_vecs
        all_reg_ids = catalog._tracks_metadata.get("region_id", [])
        candidate_indices = [
            i for i, r_val in enumerate(all_reg_ids) if r_val == r_idx and i not in track_indices
        ]
        if candidate_indices:
            cand_vecs = catalog.vectors_t[candidate_indices]
            cand_sims = np.max(np.dot(cand_vecs, taste_vecs.T), axis=1)
            best_sub_idx = np.argsort(cand_sims)[-3:][::-1]
            sample_tracks = [candidate_indices[int(si)] for si in best_sub_idx]
        else:
            sample_tracks = []

        blindspot_candidates.append(
            BlindspotRegion(
                region_id=r_idx,
                name=r_info.get("name", f"Region {r_idx}"),
                genre_focus=r_info.get("genre_focus", "Eclectic"),
                description=r_info.get("description", "Acoustically adjacent musical region."),
                top_tags=reg_tags,
                exposure=round(exp, 4),
                adjacency_score=round(adjacency, 3),
                rank_score=round(rank_score, 4),
                bridge_tags=bridge,
                sample_track_indices=sample_tracks,
            )
        )

    # Sort by rank_score descending, tie-breaking by region_id for determinism
    blindspot_candidates.sort(key=lambda b: (-b.rank_score, b.region_id))
    return blindspot_candidates
