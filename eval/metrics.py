"""Offline evaluation metrics for Melovia recommendation systems.

CIRCULARITY DISCLAIMER & LIMITATIONS:
- Intra-list diversity (ILD) and Seed-region hit-rate evaluate geometric dispersion
  and cluster coherence within the representation space (t and a).
- Seed-region hit-rate is an unsupervised neighborhood SANITY metric (circular for
  channel t) and MUST NEVER be reported as 'accuracy' or 'user satisfaction'.
- Novelty measures inverse-popularity exposure in bits, not subjective user surprise.
- Genuine relevance cannot be evaluated offline without verified human feedback logs.
"""

from collections import Counter
from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt


def intra_list_diversity(
    track_indices: Sequence[int],
    vectors_t: npt.NDArray[np.float32],
) -> float:
    """Compute Intra-List Diversity (ILD) based on semantic taste vectors:
    ILD(S) = 1 - (1 / (|S|(|S|-1))) * sum_{i != j} cos(v_i, v_j).

    Parameters:
    - track_indices: list or array of integer indices in the catalog.
    - vectors_t: (N, dim_t) L2-normalized semantic embeddings.

    Returns:
    - float in [0.0, 2.0] (typically [0.0, 1.0]).
    """
    n = len(track_indices)
    if n <= 1:
        return 0.0

    idx_arr = np.asarray(track_indices, dtype=np.int64)
    sub_vecs = vectors_t[idx_arr]  # (n, dim_t)
    # Cosine similarity matrix (since vectors are L2-normalized)
    sim_matrix = np.dot(sub_vecs, sub_vecs.T)

    # Extract strictly off-diagonal upper triangle
    triu_i, triu_j = np.triu_indices(n, k=1)
    mean_sim = float(np.mean(sim_matrix[triu_i, triu_j]))
    return float(np.clip(1.0 - mean_sim, 0.0, 2.0))


def novelty(
    track_popularities: Sequence[float] | npt.NDArray[np.floating[Any]],
    catalog_popularity_sum: float,
) -> float:
    """Compute mean item novelty (self-information in bits):
    Nov(S) = (1 / |S|) * sum_{i in S} -log2(p_i)
    where p_i = popularity_pct_i / catalog_popularity_sum.

    Parameters:
    - track_popularities: list of raw popularity values for recommended tracks.
    - catalog_popularity_sum: sum of popularity values across entire catalog.

    Returns:
    - float: mean novelty in bits.
    """
    n = len(track_popularities)
    if n == 0 or catalog_popularity_sum <= 0:
        return 0.0

    pops = np.asarray(track_popularities, dtype=np.float64)
    # Minimum probability clamp to avoid log2(0)
    p_i = np.maximum(pops / catalog_popularity_sum, 1e-12)
    self_info = -np.log2(p_i)
    return float(np.mean(self_info))


def artist_coverage(
    all_recommendation_artists: Sequence[Sequence[str]],
    total_catalog_artists: int,
) -> float:
    """Compute the fraction of catalog artists recommended across all evaluation seed sets:
    Coverage_artist = |Union_{S} Artists(S)| / TotalCatalogArtists.
    """
    if total_catalog_artists <= 0:
        return 0.0

    unique_artists: set[str] = set()
    for rec_list in all_recommendation_artists:
        for art in rec_list:
            if art:
                unique_artists.add(art)

    return float(min(1.0, len(unique_artists) / total_catalog_artists))


def catalog_coverage(
    all_recommendation_track_indices: Sequence[Sequence[int]],
    total_catalog_tracks: int,
) -> float:
    """Compute the fraction of total catalog tracks exposed across all evaluation seed sets:
    Coverage_catalog = |Union_{S} Tracks(S)| / TotalCatalogTracks.
    """
    if total_catalog_tracks <= 0:
        return 0.0

    unique_tracks: set[int] = set()
    for rec_list in all_recommendation_track_indices:
        unique_tracks.update(rec_list)

    return float(min(1.0, len(unique_tracks) / total_catalog_tracks))


def region_entropy(
    track_regions: Sequence[int | None],
) -> float:
    """Compute Shannon entropy of the region / cluster distribution:
    H = -sum_{r} p(r) * log2(p(r)).

    Returns:
    - float: entropy in bits (higher = broader exploration across genre clusters).
    """
    valid_regions = [r for r in track_regions if r is not None]
    total = len(valid_regions)
    if total <= 1:
        return 0.0

    counts = Counter(valid_regions)
    probs = np.array([c / total for c in counts.values()], dtype=np.float64)
    entropy = -np.sum(probs * np.log2(probs))
    return float(max(0.0, entropy))


def gini_exposure(
    item_exposure_counts: Sequence[int] | npt.NDArray[np.integer[Any]],
    total_catalog_tracks: int,
) -> float:
    """Compute the Gini coefficient of item recommendation exposure across all tracks:
    G = sum_{i=1}^N (2i - N - 1) * y_{(i)} / (N * sum_{i=1}^N y_{(i)}).

    A Gini coefficient of 0.0 indicates completely uniform exposure across all
    catalog tracks; 1.0 indicates maximum popularity bias / starvation.

    Parameters:
    - item_exposure_counts: exposure count array for all catalog tracks (length N).
    - total_catalog_tracks: total number of catalog tracks N.
    """
    if total_catalog_tracks <= 0:
        return 0.0

    y = np.asarray(item_exposure_counts, dtype=np.float64)
    if len(y) < total_catalog_tracks:
        # Pad with zeros for tracks that had 0 exposures
        padding = np.zeros(total_catalog_tracks - len(y), dtype=np.float64)
        y = np.concatenate([y, padding])

    total_exposure = np.sum(y)
    if total_exposure <= 0:
        return 0.0

    # Sort exposures ascending
    y_sorted = np.sort(y)
    n = total_catalog_tracks
    indices = np.arange(1, n + 1, dtype=np.float64)
    gini = np.sum((2.0 * indices - n - 1.0) * y_sorted) / (n * total_exposure)
    return float(np.clip(gini, 0.0, 1.0))


def seed_region_hit_rate(
    seed_regions: Sequence[int | None],
    recommended_regions: Sequence[int | None],
) -> float:
    """SANITY METRIC (CIRCULAR FOR T-CHANNEL):
    Compute the fraction of recommended tracks that belong to the seeds' regions.

    CIRCULARITY NOTICE:
    This evaluates cluster compactness and retrieval coherence for planted regions.
    Because channel t representations are clustered by genre/region, high hit-rate
    is an expected geometric consequence of vector similarity, NOT proof of relevance.
    """
    valid_seeds = [r for r in seed_regions if r is not None]
    valid_recs = [r for r in recommended_regions if r is not None]

    if not valid_seeds or not valid_recs:
        return 0.0

    seed_region_set = set(valid_seeds)
    hits = sum(1 for r in valid_recs if r in seed_region_set)
    return float(hits / len(valid_recs))
