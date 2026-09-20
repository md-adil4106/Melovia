"""Scoring, smooth-max aggregation, and percentile ranking module for Melovia.

Architecture Constraints:
- Pure Python and NumPy (zero imports of FastAPI, Starlette, or SQLAlchemy).
- Stable sorting: sort by (-score, track_id) to eliminate any non-determinism.
- Channel masking: dynamically renormalizes weights when audio is absent.
- Signals dictionary attached to every scored item for explainability.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from app.recsys.candidates import CandidatePool
from app.recsys.catalog import CatalogStore
from app.recsys.config import RecsysConfig


@dataclass(frozen=True)
class ScoredItem:
    """Individual scored track candidate with ranking signals."""

    track_idx: int
    track_id: str
    score: float
    signals: dict[str, Any]


@dataclass(frozen=True)
class ScoredList:
    """Ranked list of recommendations with candidate pool reference."""

    items: list[ScoredItem]
    total_candidates: int

    def top_n(self, n: int) -> list[ScoredItem]:
        return self.items[:n]


def _smooth_max_aggregation(
    sims: npt.NDArray[np.float32],
    weights: npt.NDArray[np.float32],
    tau: float = 8.0,
) -> npt.NDArray[np.float32]:
    """Log-Sum-Exp smooth max aggregation over modes:
    s_i = (1/tau) * log(sum_m pi_m * exp(tau * sim_{i,m})).

    sims: shape (P, M)
    weights: shape (M,)
    Returns: (P,) float32 array
    """
    p, m = sims.shape
    if p == 0:
        return np.empty(0, dtype=np.float32)
    if m == 1:
        return sims[:, 0]

    # u_{i,m} = tau * sim_{i,m} + log(pi_m)
    log_pi = np.log(np.maximum(weights, 1e-12))[np.newaxis, :]  # (1, M)
    u = tau * sims + log_pi  # (P, M)

    max_u = np.max(u, axis=1, keepdims=True)  # (P, 1)
    sum_exp = np.sum(np.exp(u - max_u), axis=1)  # (P,)
    max_u_sq = np.squeeze(max_u, axis=1)
    log_sum_exp = max_u_sq + np.log(np.maximum(sum_exp, 1e-12))
    res = log_sum_exp / tau
    return np.asarray(res, dtype=np.float32)


def _compute_percentile_ranks(scores: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    """Compute empirical percentile ranks within pool: z_i = (rank - 1) / (P - 1) in [0.0, 1.0]."""
    p = len(scores)
    if p <= 1:
        return np.ones(p, dtype=np.float32)

    # argsort order: 0 is lowest score, p-1 is highest score
    order = np.argsort(scores)
    ranks = np.empty(p, dtype=np.float32)
    ranks[order] = np.arange(p, dtype=np.float32)

    return ranks / (p - 1.0)


def score_candidates(
    pool: CandidatePool,
    catalog: CatalogStore,
    config: RecsysConfig | None = None,
) -> ScoredList:
    """Score, normalize, and rank candidates from a CandidatePool.

    Steps:
    1. Compute smooth-max score s_i^t and s_i^a across modes using tau.
    2. Compute pool percentile normalization z_i^t and z_i^a in [0.0, 1.0].
    3. Multi-channel combination with dynamic masking renormalization:
       - If track and seeds have audio: R_i = w_t * z_i^t + w_a * z_i^a
       - If audio is masked: R_i = 1.0 * z_i^t
    4. Attach ranking signals (nearest seed, raw similarities, percentiles).
    5. Sort deterministically by (-R_i, track_id).
    """
    cfg = config or RecsysConfig()
    p_size = pool.size

    if p_size == 0:
        return ScoredList(items=[], total_candidates=0)

    track_indices = pool.track_indices
    modes = pool.modes
    weights = modes.weights
    tau = cfg.tau

    # 1. Smooth max aggregation per channel
    s_t = _smooth_max_aggregation(pool.raw_sims_t, weights, tau=tau)

    has_audio_modes = cfg.use_audio and modes.has_channel.get("a", False)
    if has_audio_modes:
        s_a = _smooth_max_aggregation(pool.raw_sims_a, weights, tau=tau)
    else:
        s_a = np.zeros(p_size, dtype=np.float32)

    # 2. Percentile normalization within pool
    z_t = _compute_percentile_ranks(s_t)

    # For channel a, only rank tracks that actually have audio
    sub_mask_a = catalog.mask_a[track_indices]
    valid_audio_indices = np.where(sub_mask_a & has_audio_modes)[0]

    z_a = np.zeros(p_size, dtype=np.float32)
    if len(valid_audio_indices) > 0:
        z_a_valid = _compute_percentile_ranks(s_a[valid_audio_indices])
        z_a[valid_audio_indices] = z_a_valid

    # 3. Multi-channel combination with dynamic renormalization
    w_t = cfg.weight_t
    w_a = cfg.weight_a
    combined_scores = np.zeros(p_size, dtype=np.float32)

    for i in range(p_size):
        if sub_mask_a[i] and has_audio_modes:
            combined_scores[i] = w_t * z_t[i] + w_a * z_a[i]
        else:
            # Renormalize when audio is masked
            combined_scores[i] = z_t[i]

    # 4. Compute nearest seed and context for explainability signals
    all_seed_ids: list[str] = [sid for m_seeds in modes.member_seed_ids for sid in m_seeds]
    seed_indices = [catalog.get_idx(sid) for sid in all_seed_ids if catalog.contains_id(sid)]
    seed_vecs_t = (
        catalog.vectors_t[seed_indices] if seed_indices else np.empty((0, 128), dtype=np.float32)
    )

    # Pre-extract seed metadata dictionaries
    seed_dict: dict[str, dict[str, Any]] = {
        sid: catalog.get_track_dict(sid) for sid in all_seed_ids if catalog.contains_id(sid)
    }

    region_name_map: dict[int, str] = {
        int(r["region_id"]): str(r["name"])
        for r in catalog.regions
        if isinstance(r, dict) and "region_id" in r and "name" in r
    }

    # Sub-vectors for pool
    sub_vecs_t = catalog.vectors_t[track_indices]  # (P, dim_t)
    seed_sims_matrix = (
        np.dot(sub_vecs_t, seed_vecs_t.T)
        if seed_vecs_t.shape[0] > 0
        else np.zeros((p_size, 0), dtype=np.float32)
    )

    # Pre-extract track metadata columns
    region_col = catalog._tracks_metadata.get("region_id", [None] * catalog.track_count)
    tags_col = catalog._tracks_metadata.get("tags", [[]] * catalog.track_count)

    # 5. Build ScoredItems
    scored_items: list[ScoredItem] = []
    for i in range(p_size):
        t_idx = int(track_indices[i])
        t_id = catalog.get_id(t_idx)

        # Nearest seed calculation
        nearest_seed_id = all_seed_ids[0] if all_seed_ids else ""
        nearest_seed_sim = 0.0
        if seed_sims_matrix.shape[1] > 0:
            best_seed_k = int(np.argmax(seed_sims_matrix[i]))
            nearest_seed_id = all_seed_ids[best_seed_k]
            nearest_seed_sim = round(float(seed_sims_matrix[i, best_seed_k]), 4)

        best_seed_meta = seed_dict.get(nearest_seed_id, {})
        seed_title = best_seed_meta.get("title")
        seed_artist = best_seed_meta.get("artist_name")

        # Shared folksonomy tags
        track_tags = set(tags_col[t_idx] if t_idx < len(tags_col) and tags_col[t_idx] else [])
        seed_tags = set(best_seed_meta.get("tags") or [])
        shared_set = track_tags.intersection(seed_tags)
        shared_tags_list = [
            {"tag": tag, "idf": 2.5, "weight": 1.0}
            for tag in sorted(shared_set)
        ]

        # Scalar deltas against nearest seed
        scalar_deltas: dict[str, float] = {}
        if catalog.scalars:
            for s_key in (
                "energy_idx", "valence_idx", "tempo_norm", "danceability", "acousticness"
            ):
                if s_key in catalog.scalars:
                    track_val = catalog.scalars[s_key][t_idx]
                    seed_val = best_seed_meta.get("scalars", {}).get(s_key)
                    if track_val is not None and seed_val is not None:
                        scalar_deltas[s_key] = round(float(track_val - seed_val), 4)

        # Region metadata
        region_id = region_col[t_idx] if t_idx < len(region_col) else None
        region_label = region_name_map.get(region_id) if region_id is not None else None

        has_a = bool(sub_mask_a[i] and has_audio_modes)
        signals: dict[str, Any] = {
            "sim_t": round(float(s_t[i]), 4),
            "pct_t": round(float(z_t[i]), 4),
            "raw_sim_t": round(float(s_t[i]), 4),
            "percentile_t": round(float(z_t[i]), 4),
            "sim_a": round(float(s_a[i]), 4) if has_a else None,
            "pct_a": round(float(z_a[i]), 4) if has_a else None,
            "raw_sim_a": round(float(s_a[i]), 4) if has_a else None,
            "percentile_a": round(float(z_a[i]), 4) if has_a else None,
            "has_audio": has_a,
            "nearest_seed_id": nearest_seed_id,
            "nearest_seed_title": seed_title,
            "nearest_seed_artist": seed_artist,
            "nearest_seed_similarity": nearest_seed_sim,
            "shared_tags": shared_tags_list,
            "scalar_deltas": scalar_deltas,
            "region_id": region_id,
            "region_label": region_label,
            "session_facets_matched": [],
        }

        scored_items.append(
            ScoredItem(
                track_idx=t_idx,
                track_id=t_id,
                score=round(float(combined_scores[i]), 5),
                signals=signals,
            )
        )

    # 6. Stable ordering: sort by (-score, track_id)
    scored_items.sort(key=lambda item: (-item.score, item.track_id))

    return ScoredList(items=scored_items, total_candidates=p_size)
