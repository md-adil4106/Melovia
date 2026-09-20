"""Candidate generation and retrieval module for Melovia.

Architecture Constraints:
- Pure Python and NumPy (zero imports of FastAPI, Starlette, or SQLAlchemy).
- Exact matrix multiplication per mode per channel.
- Union pooling with seed exclusion ("seeds never appear in results").
"""

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from app.recsys.catalog import CatalogStore
from app.recsys.config import RecsysConfig
from app.recsys.taste import Modes


@dataclass(frozen=True)
class CandidateFilters:
    """Optional exclusion and slicing filters for candidate generation."""

    excluded_artist_ids: set[str] = field(default_factory=set)
    excluded_track_ids: set[str] = field(default_factory=set)
    min_year: int | None = None
    max_year: int | None = None


@dataclass(frozen=True)
class CandidatePool:
    """Retrieved union of candidates with per-channel raw similarities."""

    # Integer row indices into catalog (length P)
    track_indices: npt.NDArray[np.int64]

    # Raw cosine similarities between each candidate and each mode
    # raw_sims_t: shape (P, M)
    # raw_sims_a: shape (P, M)
    raw_sims_t: npt.NDArray[np.float32]
    raw_sims_a: npt.NDArray[np.float32]

    # Taste modes used to generate this pool
    modes: Modes

    @property
    def size(self) -> int:
        return len(self.track_indices)


def generate_candidates(
    modes: Modes,
    catalog: CatalogStore,
    filters: CandidateFilters | None = None,
    k_per_mode: int = 500,
    config: RecsysConfig | None = None,
) -> CandidatePool:
    """Generate candidate pool via exact vector dot products per mode per channel.

    Steps:
    1. For each mode and channel, compute top-K cosine similarities with catalog.
    2. Union top indices across all modes and channels.
    3. Exclude seed tracks and any excluded artists.
    4. Compute and return per-channel similarity matrices.
    """
    cfg = config or RecsysConfig()
    filt = filters or CandidateFilters()
    n_catalog = catalog.track_count

    # Flatten all seed IDs to exclude
    seed_ids_set: set[str] = set()
    for mode_seeds in modes.member_seed_ids:
        seed_ids_set.update(mode_seeds)
    seed_ids_set.update(filt.excluded_track_ids)

    # Convert excluded seeds to integer catalog indices
    seed_indices_set: set[int] = {
        catalog.get_idx(sid) for sid in seed_ids_set if catalog.contains_id(sid)
    }

    # Extract artist exclusions
    artist_col = catalog._tracks_metadata.get("artist_id", [])
    excluded_artists_set = filt.excluded_artist_ids

    # Candidate indices set
    candidate_indices_set: set[int] = set()
    m_count = modes.num_modes

    # Effective K limited by catalog size
    eff_k = min(k_per_mode, n_catalog)

    # 1. Channel t candidates
    vecs_t = catalog.vectors_t  # (N, dim_t)
    modes_t = modes.channel_vectors["t"]  # (M, dim_t)

    for m in range(m_count):
        sims_m = np.dot(vecs_t, modes_t[m])  # (N,)
        # Top-K indices
        if eff_k < n_catalog:
            top_idx = np.argpartition(sims_m, -eff_k)[-eff_k:]
        else:
            top_idx = np.arange(n_catalog)
        candidate_indices_set.update(int(idx) for idx in top_idx)

    # 2. Channel a candidates (if available and audio is enabled)
    if cfg.use_audio and modes.has_channel.get("a", False):
        vecs_a = catalog.vectors_a  # (N, dim_a)
        modes_a = modes.channel_vectors["a"]  # (M, dim_a)
        mask_a = catalog.mask_a

        for m in range(m_count):
            mode_norm = float(np.linalg.norm(modes_a[m]))
            if mode_norm > 1e-6:
                sims_m = np.dot(vecs_a, modes_a[m])  # (N,)
                # Zero out masked tracks so they are not retrieved as audio candidates
                sims_m[~mask_a] = -999.0
                if eff_k < n_catalog:
                    top_idx = np.argpartition(sims_m, -eff_k)[-eff_k:]
                else:
                    top_idx = np.arange(n_catalog)
                for idx in top_idx:
                    if mask_a[idx]:
                        candidate_indices_set.add(int(idx))

    # 3. Apply exclusions (seeds, artists, year)
    valid_indices: list[int] = []
    years_col = catalog._tracks_metadata.get("year", [])

    for idx in candidate_indices_set:
        # Strictly exclude seed tracks
        if idx in seed_indices_set:
            continue

        # Exclude specified artists
        if excluded_artists_set and artist_col:
            art_id = str(artist_col[idx])
            if art_id in excluded_artists_set:
                continue

        # Year bounds
        if filt.min_year is not None and years_col:
            yr = years_col[idx]
            if yr is not None and yr < filt.min_year:
                continue
        if filt.max_year is not None and years_col:
            yr = years_col[idx]
            if yr is not None and yr > filt.max_year:
                continue

        valid_indices.append(idx)

    # Sort indices deterministically
    valid_indices.sort()
    pool_indices = np.array(valid_indices, dtype=np.int64)
    p_size = len(pool_indices)

    if p_size == 0:
        # Empty pool
        return CandidatePool(
            track_indices=np.empty(0, dtype=np.int64),
            raw_sims_t=np.empty((0, m_count), dtype=np.float32),
            raw_sims_a=np.empty((0, m_count), dtype=np.float32),
            modes=modes,
        )

    # 4. Compute full (P, M) similarity matrices for pool
    sub_vecs_t = catalog.vectors_t[pool_indices]  # (P, dim_t)
    raw_sims_t = np.dot(sub_vecs_t, modes.channel_vectors["t"].T).astype(np.float32)

    raw_sims_a = np.zeros((p_size, m_count), dtype=np.float32)
    if cfg.use_audio and modes.has_channel.get("a", False):
        sub_vecs_a = catalog.vectors_a[pool_indices]  # (P, dim_a)
        sub_mask_a = catalog.mask_a[pool_indices]
        raw_sims_a_full = np.dot(sub_vecs_a, modes.channel_vectors["a"].T).astype(np.float32)
        # Zero out rows where track has no audio
        raw_sims_a_full[~sub_mask_a] = 0.0
        raw_sims_a = raw_sims_a_full

    return CandidatePool(
        track_indices=pool_indices,
        raw_sims_t=raw_sims_t,
        raw_sims_a=raw_sims_a,
        modes=modes,
    )
