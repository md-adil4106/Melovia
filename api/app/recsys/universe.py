"""3D & 2D Universe projection, quantization, and kNN placement module for Melovia.

Architecture Constraints:
- Pure Python and NumPy (zero imports from FastAPI, Starlette, SQLAlchemy, or DB).
- Strictly deterministic tie-breaking.
- Non-linear distortion disclosures for 3D map projections.
- Recommendation decisions ALWAYS use high-dimensional vectors.
  3D coordinates are visualization-only.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np

from app.recsys.catalog import CatalogStore


def quantize_points(
    points_3d: np.ndarray,
    region_indices: Sequence[int] | np.ndarray,
    track_indices: Sequence[int] | np.ndarray,
) -> list[int]:
    """Quantize an (N, 3) float coordinate array in [-1.0, 1.0] to a flat list of Int16 integers.

    Format: [qx_0, qy_0, qz_0, region_idx_0, track_idx_0, qx_1, ...]
    Payload is compact and binary-friendly for fast network transport.

    Parameters
    ----------
    points_3d : np.ndarray
        (N, 3) array with coordinates bounded in [-1.0, 1.0].
    region_indices : Sequence[int]
        Length N sequence of integer region assignments (0..23).
    track_indices : Sequence[int]
        Length N sequence of catalog track row indices.

    Returns
    -------
    list[int]
        Flat 1D list of 5 * N integers.
    """
    n = len(points_3d)
    if n == 0:
        return []

    # Quantize float in [-1.0, 1.0] to Int16 [-32767, 32767]
    clamped = np.clip(points_3d, -1.0, 1.0)
    q_coords = np.round(clamped * 32767.0).astype(np.int32)

    flat: list[int] = []
    for i in range(n):
        flat.append(int(q_coords[i, 0]))
        flat.append(int(q_coords[i, 1]))
        flat.append(int(q_coords[i, 2]))
        flat.append(int(region_indices[i]))
        flat.append(int(track_indices[i]))

    return flat


def dequantize_points(flat: list[int]) -> tuple[np.ndarray, list[int], list[int]]:
    """Dequantize flat Int16 coordinate array back into Float32 (N, 3), regions, and tracks."""
    if len(flat) % 5 != 0:
        raise ValueError(f"Flat array length {len(flat)} is not a multiple of 5")

    n = len(flat) // 5
    coords = np.zeros((n, 3), dtype=np.float32)
    regions: list[int] = []
    tracks: list[int] = []

    for i in range(n):
        base = i * 5
        coords[i, 0] = flat[base] / 32767.0
        coords[i, 1] = flat[base + 1] / 32767.0
        coords[i, 2] = flat[base + 2] / 32767.0
        regions.append(flat[base + 3])
        tracks.append(flat[base + 4])

    return coords, regions, tracks


def place_in_universe(
    vectors: np.ndarray,
    catalog: CatalogStore,
    k: int = 10,
    temperature: float = 0.05,
) -> list[dict[str, Any]]:
    """Deterministically place dynamic vectors (e.g. taste modes or tracks) into 3D and 2D space.

    Uses k-Nearest Neighbors weighted interpolation in the original embedding space.
    Does NOT run per-request UMAP; guarantees instant, consistent spatial positioning.

    Parameters
    ----------
    vectors : np.ndarray
        (M, D) normalized query vectors. D=128 (taste) or D=256 (fused [t | a]).
    catalog : CatalogStore
        Mounted immutable catalog with layout3d and vectors.
    k : int
        Number of nearest neighbors to interpolate over (default 10).
    temperature : float
        Softmax scaling temperature (default 0.05).

    Returns
    -------
    list[dict[str, Any]]
        List of dicts containing 'position_3d', 'position_2d', 'nearest_track_ids', and 'weights'.
    """
    if catalog.layout3d is None:
        raise ValueError("Catalog has no layout3d coordinates loaded.")

    n_queries = len(vectors)
    if n_queries == 0:
        return []

    # Determine channel compatibility
    dim = vectors.shape[1]
    if dim == catalog.dim_t:
        ref_matrix = catalog.vectors_t
    elif dim == catalog.dim_t + catalog.dim_a:
        fused = np.hstack([catalog.vectors_t, catalog.vectors_a])
        norms = np.linalg.norm(fused, axis=1, keepdims=True)
        ref_matrix = (fused / np.maximum(norms, 1e-9)).astype(np.float32)
    else:
        raise ValueError(
            f"Input vector dimension {dim} does not match catalog taste ({catalog.dim_t}) "
            f"or fused ({catalog.dim_t + catalog.dim_a}) dimensions."
        )

    # Compute cosine similarity matrix: (n_queries, n_catalog)
    dots = np.clip(np.dot(vectors, ref_matrix.T), -1.0, 1.0)
    layout_3d = catalog.layout3d
    layout_2d = catalog.layout2d

    results: list[dict[str, Any]] = []

    for q_idx in range(n_queries):
        sims_q = dots[q_idx]
        # Top-k catalog indices
        top_k_indices = np.argsort(-sims_q)[:k]
        top_k_sims = sims_q[top_k_indices]

        # Softmax weights over top-k similarities
        scaled_sims = (top_k_sims - np.max(top_k_sims)) / max(temperature, 1e-4)
        exp_sims = np.exp(scaled_sims)
        weights = exp_sims / np.sum(exp_sims)  # (k,)

        # Weighted 3D position
        coords_3d = layout_3d[top_k_indices]  # (k, 3)
        pos_3d = np.sum(coords_3d * weights[:, np.newaxis], axis=0)

        # Weighted 2D position if available
        pos_2d: list[float] | None = None
        if layout_2d is not None:
            coords_2d = layout_2d[top_k_indices]  # (k, 2)
            pos_2d_arr = np.sum(coords_2d * weights[:, np.newaxis], axis=0)
            pos_2d = [round(float(pos_2d_arr[0]), 5), round(float(pos_2d_arr[1]), 5)]

        nearest_track_ids = [catalog.get_id(int(idx)) for idx in top_k_indices]

        results.append(
            {
                "position_3d": [
                    round(float(pos_3d[0]), 5),
                    round(float(pos_3d[1]), 5),
                    round(float(pos_3d[2]), 5),
                ],
                "position_2d": pos_2d,
                "nearest_track_indices": top_k_indices.tolist(),
                "nearest_track_ids": nearest_track_ids,
                "weights": [round(float(w), 5) for w in weights],
            }
        )

    return results


def find_original_neighbors(
    track_idx: int,
    catalog: CatalogStore,
    k: int = 6,
) -> list[dict[str, Any]]:
    """Compute true nearest neighbors in original high-dimensional vector space.

    Extracts cosine similarities in taste (t) and audio (a) spaces, along with shared tags.
    """
    if track_idx < 0 or track_idx >= catalog.track_count:
        raise IndexError(f"Track index {track_idx} out of range [0, {catalog.track_count})")

    v_t = catalog.vectors_t[track_idx]
    has_a = bool(catalog.mask_a[track_idx])
    v_a = catalog.vectors_a[track_idx] if has_a else None

    # Compute taste cosine similarities
    dots_t = np.clip(np.dot(catalog.vectors_t, v_t), -1.0, 1.0)

    # Compute audio cosine similarities if audio available
    if has_a and v_a is not None:
        dots_a = np.clip(np.dot(catalog.vectors_a, v_a), -1.0, 1.0)
        # 0.6 taste + 0.4 audio
        combined_sim = 0.6 * dots_t + 0.4 * dots_a
    else:
        dots_a = np.zeros(catalog.track_count, dtype=np.float32)
        combined_sim = dots_t

    # Sort descending, exclude self
    sorted_indices = np.argsort(-combined_sim)
    candidate_indices = [int(idx) for idx in sorted_indices if idx != track_idx][:k]

    # Target track tags
    target_dict = catalog.get_track_dict(track_idx)
    target_tags = set(target_dict.get("tags") or [])

    neighbors: list[dict[str, Any]] = []
    for neighbor_idx in candidate_indices:
        nb_dict = catalog.get_track_dict(neighbor_idx)
        nb_tags = set(nb_dict.get("tags") or [])
        shared = sorted(target_tags.intersection(nb_tags))

        sim_a_val: float | None = None
        if has_a and catalog.mask_a[neighbor_idx]:
            sim_a_val = float(dots_a[neighbor_idx])

        neighbors.append(
            {
                "track_idx": neighbor_idx,
                "track_id": catalog.get_id(neighbor_idx),
                "title": nb_dict.get("title", ""),
                "artist_name": nb_dict.get("artist_name", ""),
                "region_id": nb_dict.get("region_id"),
                "similarity_combined": float(combined_sim[neighbor_idx]),
                "similarity_t": float(dots_t[neighbor_idx]),
                "similarity_a": sim_a_val,
                "shared_tags": shared,
            }
        )

    return neighbors


def compute_region_3d_centroids(
    catalog: CatalogStore,
    user_exposures: dict[int, float] | None = None,
) -> list[dict[str, Any]]:
    """Compute 3D and 2D centroids, palette colors, and exposure levels for all catalog regions."""
    if catalog.layout3d is None:
        return []

    # 24 visually distinct palette colors (hex) for clear visual separation
    palette_24 = [
        "#38bdf8",  # 0: Sky Blue (Neon Nocturne)
        "#a78bfa",  # 1: Purple (Ethereal Drift)
        "#34d399",  # 2: Emerald (Cinematic Horizons)
        "#fbbf24",  # 3: Amber (Deep Chamber)
        "#f472b6",  # 4: Pink (Faded Cassette)
        "#f97316",  # 5: Orange (Solar Groove)
        "#4ade80",  # 6: Green (Sacred Timber)
        "#818cf8",  # 7: Indigo (Analog Odyssey)
        "#a3e635",  # 8: Lime (Dusk Reverie)
        "#06b6d4",  # 9: Cyan (Subterranean Bass)
        "#e879f9",  # 10: Fuchsia (Polyphonic Pulse)
        "#64748b",  # 11: Slate (Infinite Drone)
        "#2dd4bf",  # 12: Teal (Glitch & Resonance)
        "#fb7185",  # 13: Rose (Velvet Groove)
        "#ef4444",  # 14: Red (Industrial Monolith)
        "#d97706",  # 15: Warm Amber (Desert Mirage)
        "#0284c7",  # 16: Deep Sky (Hyper-Echo)
        "#c084fc",  # 17: Violet (Cloud Mirage)
        "#f59e0b",  # 18: Honey (Midnight Bop)
        "#94a3b8",  # 19: Gray (Static & Rust)
        "#e11d48",  # 20: Crimson (Baroque Twilight)
        "#ec4899",  # 21: Hot Pink (Vapor Echoes)
        "#6366f1",  # 22: Electric Indigo (Galactic Bass)
        "#84cc16",  # 23: Olive Lime (Acoustic Solitude)
    ]

    regions_info = catalog.regions
    track_regions = np.array(
        catalog._tracks_metadata.get("region_id", [0] * catalog.track_count),
        dtype=np.int32,
    )
    exposures = user_exposures or {}

    centroids: list[dict[str, Any]] = []

    for r_idx in range(len(regions_info)):
        r_meta = regions_info[r_idx]
        reg_id = int(r_meta.get("region_id", r_idx))
        mask = track_regions == reg_id
        if not np.any(mask):
            c_3d = [0.0, 0.0, 0.0]
            c_2d = [0.0, 0.0]
        else:
            mean_3d = np.mean(catalog.layout3d[mask], axis=0)
            c_3d = [round(float(x), 5) for x in mean_3d]
            if catalog.layout2d is not None:
                mean_2d = np.mean(catalog.layout2d[mask], axis=0)
                c_2d = [round(float(x), 5) for x in mean_2d]
            else:
                c_2d = [c_3d[0], c_3d[1]]

        color = palette_24[reg_id % len(palette_24)]
        exp_val = float(exposures.get(reg_id, 0.0))

        centroids.append(
            {
                "id": reg_id,
                "label": r_meta.get("name", f"Region {reg_id}"),
                "genre_focus": r_meta.get("genre_focus", ""),
                "description": r_meta.get("description", ""),
                "centroid_3d": c_3d,
                "centroid_2d": c_2d,
                "color": color,
                "exposure": exp_val,
                "top_tags": r_meta.get("top_tags", [])[:5],
                "track_count": int(np.sum(mask)),
            }
        )

    return centroids
