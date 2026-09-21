"""Benchmark baseline recommenders for Melovia recsys evaluation.

Architecture Constraints:
- Pure Python and NumPy (zero imports of FastAPI, Starlette, or SQLAlchemy).
- Seed-based determinism and stable tie-breaking.
- Baselines: random, genre-only (tag overlap), single-channel cosine (t), single-channel cosine (a).
"""

from typing import Any

import numpy as np

from app.recsys.catalog import CatalogStore


def _exclude_seeds(candidate_indices: list[int], seed_indices: set[int], n: int) -> list[int]:
    """Filter out seed indices and return top n."""
    filtered = [idx for idx in candidate_indices if idx not in seed_indices]
    return filtered[:n]


def random_baseline(
    seed_ids: list[str],
    catalog: CatalogStore,
    n: int = 30,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Uniform random selection of non-seed catalog tracks."""
    rng = np.random.default_rng(seed)
    seed_indices = {catalog.get_idx(sid) for sid in seed_ids if catalog.has_idx(sid)}

    all_indices = np.arange(catalog.track_count)
    rng.shuffle(all_indices)

    chosen = _exclude_seeds(all_indices.tolist(), seed_indices, n)
    return [catalog.get_track_dict(idx) for idx in chosen]


def genre_baseline(
    seed_ids: list[str],
    catalog: CatalogStore,
    n: int = 30,
) -> list[dict[str, Any]]:
    """Genre and tag overlap baseline (ranks by number of shared folksonomy tags)."""
    seed_indices = {catalog.get_idx(sid) for sid in seed_ids if catalog.has_idx(sid)}

    # Collect seed tags
    seed_tags: set[str] = set()
    for sid in seed_ids:
        if catalog.contains_id(sid):
            t_dict = catalog.get_track_dict(sid)
            raw_tags = t_dict.get("tags") or []
            for item in raw_tags:
                tname = item if isinstance(item, str) else item.get("name", "")
                if tname:
                    seed_tags.add(tname.lower().strip())

    scored_candidates: list[tuple[int, float, str, int]] = []
    popularities = catalog._tracks_metadata.get("popularity_pct", [50.0] * catalog.track_count)

    for idx in range(catalog.track_count):
        if idx in seed_indices:
            continue
        t_dict = catalog.get_track_dict(idx)
        t_tags = t_dict.get("tags") or []
        c_tags: set[str] = set()
        for item in t_tags:
            tname = item if isinstance(item, str) else item.get("name", "")
            if tname:
                c_tags.add(tname.lower().strip())

        overlap = len(seed_tags.intersection(c_tags))
        pop = float(popularities[idx])
        t_id = catalog.get_id(idx)
        # Sort by: -overlap, -popularity, t_id
        scored_candidates.append((overlap, pop, t_id, idx))

    scored_candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    chosen_indices = [item[3] for item in scored_candidates[:n]]
    return [catalog.get_track_dict(idx) for idx in chosen_indices]


def single_channel_t_baseline(
    seed_ids: list[str],
    catalog: CatalogStore,
    n: int = 30,
) -> list[dict[str, Any]]:
    """Single-channel cosine similarity baseline in semantic taste space (t)."""
    seed_indices = {catalog.get_idx(sid) for sid in seed_ids if catalog.has_idx(sid)}
    seed_vecs_list = [catalog.get_vector_t(sid) for sid in seed_ids if catalog.contains_id(sid)]
    if not seed_vecs_list:
        return []

    # Mean seed vector in t
    mean_vec = np.mean(seed_vecs_list, axis=0)
    norm = float(np.linalg.norm(mean_vec))
    if norm > 1e-12:
        mean_vec /= norm

    sims = np.dot(catalog.vectors_t, mean_vec)
    # Sort descending
    sorted_order = np.argsort(-sims)

    chosen = _exclude_seeds(sorted_order.tolist(), seed_indices, n)
    return [catalog.get_track_dict(idx) for idx in chosen]


def single_channel_a_baseline(
    seed_ids: list[str],
    catalog: CatalogStore,
    n: int = 30,
) -> list[dict[str, Any]]:
    """Single-channel cosine similarity baseline in acoustic audio space (a)."""
    seed_indices = [catalog.get_idx(sid) for sid in seed_ids if catalog.has_idx(sid)]
    audio_seed_indices = [idx for idx in seed_indices if catalog.mask_a[idx]]

    if not audio_seed_indices:
        # Fallback to channel t if no seeds have audio
        return single_channel_t_baseline(seed_ids, catalog, n)

    sub_vecs = catalog.vectors_a[audio_seed_indices]
    mean_vec = np.mean(sub_vecs, axis=0)
    norm = float(np.linalg.norm(mean_vec))
    if norm > 1e-12:
        mean_vec /= norm

    sims = np.dot(catalog.vectors_a, mean_vec)
    # Zero out masked tracks
    sims[~catalog.mask_a] = -999.0

    sorted_order = np.argsort(-sims)
    chosen = _exclude_seeds(sorted_order.tolist(), set(seed_indices), n)
    return [catalog.get_track_dict(idx) for idx in chosen]
