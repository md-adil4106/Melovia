"""Taste profile and multi-mode aggregation module for Melovia.

Architecture Constraints:
- Pure Python and NumPy (zero imports of FastAPI, Starlette, or SQLAlchemy).
- Deterministic behavior with stable tie-breaking.
- Constructs multi-modal taste representations (Modes) across semantic (t) and audio (a) channels.
"""

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from app.recsys.catalog import CatalogStore
from app.recsys.config import RecsysConfig


class RecsysError(Exception):
    """Base exception for recommendation engine errors."""


class SeedNotFoundError(RecsysError):
    """Raised when a requested seed track ID is not present in the catalog."""


@dataclass(frozen=True)
class Modes:
    """Multi-modal user taste representation decomposed across orthogonal channels."""

    # Mode centroid vectors per channel:
    # 't' -> (M, dim_t), 'a' -> (M, dim_a)
    channel_vectors: dict[str, npt.NDArray[np.float32]]

    # Mode prior weights pi_m summing to 1.0 (shape: (M,))
    weights: npt.NDArray[np.float32]

    # Member seed track IDs contributing to each mode (length M)
    member_seed_ids: list[list[str]]

    # Validity flag per channel for these modes
    has_channel: dict[str, bool] = field(default_factory=dict)

    @property
    def num_modes(self) -> int:
        return len(self.weights)


def _compute_cosine_distance_matrix(vectors: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    similarities = np.dot(vectors, vectors.T)
    distances = 1.0 - similarities
    clipped = np.clip(distances, 0.0, 2.0)
    return np.asarray(clipped, dtype=np.float32)


def _k_medoids(
    distances: npt.NDArray[np.float32],
    k: int,
    max_iters: int = 15,
) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]:
    """Deterministic k-medoids clustering using greedy furthest initialization and PAM updates.

    Returns:
    - medoid_indices: (k,) array of medoid point indices
    - assignments: (n,) array of cluster assignments (0 to k-1)
    """
    n = distances.shape[0]
    if k >= n:
        return np.arange(n, dtype=np.int64), np.arange(n, dtype=np.int64)

    # 1. Deterministic furthest-point initialization
    # First medoid is point with minimum total distance to all other points
    first_medoid = int(np.argmin(np.sum(distances, axis=1)))
    medoids = [first_medoid]

    while len(medoids) < k:
        # Distance of each point to its nearest already-chosen medoid
        min_dists = np.min(distances[:, medoids], axis=1)
        # Choose furthest point with deterministic tie-breaking (first index)
        next_medoid = int(np.argmax(min_dists))
        medoids.append(next_medoid)

    medoid_arr = np.array(medoids, dtype=np.int64)
    assignments = np.argmin(distances[:, medoid_arr], axis=1)

    # 2. Voronoi iteration (PAM update step)
    for _ in range(max_iters):
        changed = False
        new_medoids = []
        for cluster_id in range(k):
            members = np.where(assignments == cluster_id)[0]
            if len(members) == 0:
                new_medoids.append(medoid_arr[cluster_id])
                continue

            sub_dist = distances[np.ix_(members, members)]
            best_member_idx = int(np.argmin(np.sum(sub_dist, axis=1)))
            new_m = members[best_member_idx]
            new_medoids.append(new_m)
            if new_m != medoid_arr[cluster_id]:
                changed = True

        medoid_arr = np.array(new_medoids, dtype=np.int64)
        assignments = np.argmin(distances[:, medoid_arr], axis=1)
        if not changed:
            break

    return medoid_arr, assignments


def _compute_silhouette_score(
    distances: npt.NDArray[np.float32],
    assignments: npt.NDArray[np.int64],
    k: int,
) -> float:
    """Compute mean silhouette score for clustering."""
    n = distances.shape[0]
    if k <= 1 or k >= n:
        return 0.0

    silhouettes = np.zeros(n, dtype=np.float32)

    for i in range(n):
        c_i = assignments[i]
        members_c_i = np.where(assignments == c_i)[0]

        # a(i): mean intra-cluster distance
        if len(members_c_i) > 1:
            a_i = np.sum(distances[i, members_c_i]) / (len(members_c_i) - 1)
        else:
            a_i = 0.0

        # b(i): minimum mean distance to other clusters
        b_i = float("inf")
        for other_c in range(k):
            if other_c == c_i:
                continue
            other_members = np.where(assignments == other_c)[0]
            if len(other_members) > 0:
                dist_to_other = np.mean(distances[i, other_members])
                if dist_to_other < b_i:
                    b_i = float(dist_to_other)

        if b_i == float("inf"):
            b_i = 0.0

        denom = max(a_i, b_i)
        if denom > 1e-6:
            silhouettes[i] = (b_i - a_i) / denom
        else:
            silhouettes[i] = 0.0

    return float(np.mean(silhouettes))


def build_modes(
    seed_ids: list[str],
    catalog: CatalogStore,
    config: RecsysConfig | None = None,
) -> Modes:
    """Build multi-modal taste representations from 1-10 seed track IDs.

    Rules:
    - n < 6 seeds: one mode per seed (equal weights pi_m = 1/n).
    - n >= 6 seeds: k-medoids clustering (k <= 3, silhouette-guided) in taste space.
    - Missing audio channels handled gracefully without errors.
    """
    cfg = config or RecsysConfig()
    n_seeds = len(seed_ids)

    if n_seeds < cfg.min_seeds or n_seeds > cfg.max_seeds:
        raise ValueError(
            f"Seed count must be between {cfg.min_seeds} and {cfg.max_seeds}, got {n_seeds}"
        )

    dim_t = catalog.vectors_t.shape[1]
    dim_a = catalog.vectors_a.shape[1]

    vecs_t = np.zeros((n_seeds, dim_t), dtype=np.float32)
    vecs_a = np.zeros((n_seeds, dim_a), dtype=np.float32)
    mask_a_seeds = np.zeros(n_seeds, dtype=np.bool_)

    for i, sid in enumerate(seed_ids):
        if not catalog.contains_id(sid):
            raise SeedNotFoundError(f"Seed track ID '{sid}' not found in catalog")

        if sid in catalog._id_to_idx:
            idx = catalog.get_idx(sid)
            vecs_t[i] = catalog.vectors_t[idx]
            vecs_a[i] = catalog.vectors_a[idx]
            mask_a_seeds[i] = catalog.mask_a[idx]
        else:
            # Dynamic external track registered on-the-fly
            dyn_vt = catalog.get_dynamic_vector_t(sid)
            if dyn_vt is not None:
                vecs_t[i] = dyn_vt
            else:
                rnd_v = np.ones(dim_t, dtype=np.float32)
                vecs_t[i] = rnd_v / np.linalg.norm(rnd_v)
            vecs_a[i] = np.zeros(dim_a, dtype=np.float32)
            mask_a_seeds[i] = False

    has_audio_any = bool(np.any(mask_a_seeds))

    # 2. Determine clustering / modes
    if n_seeds < cfg.k_medoids_threshold_seeds:
        # Case A: n < 6 seeds -> exactly one mode per seed
        weights = np.full(n_seeds, 1.0 / n_seeds, dtype=np.float32)
        member_seed_ids = [[sid] for sid in seed_ids]
        mode_vecs_t = vecs_t.copy()

        # For channel a: copy existing vectors (or zeros if missing)
        mode_vecs_a = np.zeros((n_seeds, dim_a), dtype=np.float32)
        if has_audio_any:
            for i in range(n_seeds):
                if mask_a_seeds[i]:
                    mode_vecs_a[i] = vecs_a[i]

    else:
        # Case B: n >= 6 seeds -> k-medoids clustering in taste space
        dist_matrix = _compute_cosine_distance_matrix(vecs_t)
        best_k = 2
        best_score = -1.0
        best_medoids = np.array([0, 1], dtype=np.int64)
        best_assignments = np.zeros(n_seeds, dtype=np.int64)

        for candidate_k in range(2, min(cfg.k_medoids_max_k + 1, n_seeds)):
            medoids, assignments = _k_medoids(dist_matrix, k=candidate_k)
            score = _compute_silhouette_score(dist_matrix, assignments, k=candidate_k)
            if score > best_score:
                best_score = score
                best_k = candidate_k
                best_medoids = medoids
                best_assignments = assignments

        # If silhouette is negative or very weak, fallback to k=1 centroid
        if best_score < cfg.silhouette_min_threshold:
            # Single composite mode
            best_k = 1
            best_assignments = np.zeros(n_seeds, dtype=np.int64)
            best_medoids = np.array([int(np.argmin(np.sum(dist_matrix, axis=1)))], dtype=np.int64)

        # Build cluster representations
        mode_vecs_t = np.zeros((best_k, dim_t), dtype=np.float32)
        mode_vecs_a = np.zeros((best_k, dim_a), dtype=np.float32)
        weights_list = []
        member_seed_ids = []

        for m_idx in range(best_k):
            members = np.where(best_assignments == m_idx)[0]
            weights_list.append(len(members) / n_seeds)
            member_seed_ids.append([seed_ids[i] for i in members])

            # Centroid in t-space, normalized
            c_t = np.mean(vecs_t[members], axis=0)
            norm_t = float(np.linalg.norm(c_t))
            mode_vecs_t[m_idx] = (c_t / norm_t) if norm_t > 1e-6 else vecs_t[best_medoids[m_idx]]

            # Centroid in a-space over members with valid audio
            audio_members = [i for i in members if mask_a_seeds[i]]
            if audio_members:
                c_a = np.mean(vecs_a[audio_members], axis=0)
                norm_a = float(np.linalg.norm(c_a))
                mode_vecs_a[m_idx] = (
                    (c_a / norm_a) if norm_a > 1e-6 else np.zeros(dim_a, dtype=np.float32)
                )
            else:
                mode_vecs_a[m_idx] = np.zeros(dim_a, dtype=np.float32)

        weights = np.array(weights_list, dtype=np.float32)

    return Modes(
        channel_vectors={"t": mode_vecs_t, "a": mode_vecs_a},
        weights=weights,
        member_seed_ids=member_seed_ids,
        has_channel={"t": True, "a": has_audio_any},
    )
