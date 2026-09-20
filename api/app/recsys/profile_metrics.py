"""Taste Profile Metrics and Music DNA Engine for Melovia (Phase 11).

Architecture Constraints:
- Pure Python and NumPy (zero imports of FastAPI, Starlette, or SQLAlchemy).
- 100% deterministic: seeded bootstrap RNG, stable tie-breaking.
- Descriptive only: no judgment or ranking of users' taste as good or bad.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.recsys.catalog import CatalogStore


@dataclass(frozen=True)
class DimensionScore:
    """A single taste dimension with point estimate, bootstrap CI, and percentile."""

    name: str
    key: str
    value: float
    ci_90: tuple[float, float]
    percentile: float
    description: str
    definition_tooltip: str


@dataclass(frozen=True)
class MusicDNA:
    """Deterministic Music DNA summary of dominant tags, scalars, and regions."""

    dominant_tags: list[dict[str, Any]]
    mean_scalars: dict[str, dict[str, float]]
    dominant_regions: list[dict[str, Any]]


@dataclass(frozen=True)
class TasteProfileResult:
    """Complete computed taste profile result."""

    known_track_count: int
    confidence: str  # "low" (< 8 tracks) or "high" (>= 8 tracks)
    confidence_reason: str
    dimensions: dict[str, DimensionScore | None]
    music_dna: MusicDNA
    region_exposures: list[dict[str, Any]]


def _bootstrap_ci(
    sample_values: Sequence[Any],
    metric_func: Any,
    b_reps: int = 200,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute 90% bootstrap confidence interval (5th and 95th percentiles)."""
    n = len(sample_values)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        val = sample_values[0]
        return val, val

    rng = np.random.RandomState(seed)
    boot_estimates: list[float] = []
    arr = np.array(sample_values)

    for _ in range(b_reps):
        resampled = rng.choice(arr, size=n, replace=True)
        boot_estimates.append(float(metric_func(resampled)))

    boot_estimates.sort()
    low_idx = int(0.05 * b_reps)
    high_idx = min(int(0.95 * b_reps), b_reps - 1)
    return round(boot_estimates[low_idx], 3), round(boot_estimates[high_idx], 3)


def compute_taste_profile(
    track_indices: list[int],
    catalog: CatalogStore,
    feedback_events: list[dict[str, Any]] | None = None,
    bootstrap_seed: int = 42,
) -> TasteProfileResult:
    """Compute deterministic taste dimensions, Music DNA, and confidence level.

    Args:
        track_indices: Contiguous 0-indexed catalog track indices for known set K.
        catalog: Loaded immutable CatalogStore.
        feedback_events: Optional list of interaction events (for adventurousness).
        bootstrap_seed: Seed for reproducible bootstrap confidence intervals.

    Returns:
        TasteProfileResult
    """
    n_k = len(track_indices)
    confidence = "high" if n_k >= 8 else "low"
    confidence_reason = (
        f"Based on {n_k} track{'s' if n_k != 1 else ''}. Confidence is high (>= 8 tracks)."
        if n_k >= 8
        else (
            f"Based on {n_k} track{'s' if n_k != 1 else ''}. "
            "Explore and like more tracks (>= 8) for a robust profile."
        )
    )

    if n_k == 0:
        empty_dna = MusicDNA(dominant_tags=[], mean_scalars={}, dominant_regions=[])
        return TasteProfileResult(
            known_track_count=0,
            confidence="low",
            confidence_reason=(
                "No known tracks found. Select seeds or like tracks to build your taste profile."
            ),
            dimensions={
                "breadth": None,
                "rarity": None,
                "range": None,
                "cohesion": None,
                "adventurousness": None,
            },
            music_dna=empty_dna,
            region_exposures=[],
        )

    # 1. Gather track attributes
    vecs_t = catalog.vectors_t[track_indices]  # (n_k, dim_t)
    popularities = [
        float(catalog._tracks_metadata.get("popularity_pct", [50.0] * catalog.track_count)[idx])
        for idx in track_indices
    ]
    years = [
        int(catalog._tracks_metadata.get("year", [2000] * catalog.track_count)[idx])
        for idx in track_indices
        if catalog._tracks_metadata.get("year", [None] * catalog.track_count)[idx] is not None
    ]

    # Region assignments (soft top-2 if available)
    reg_primaries = catalog._tracks_metadata.get("region_id", [0] * catalog.track_count)
    reg_secondaries = catalog._tracks_metadata.get("region_id_secondary", reg_primaries)
    reg_w_primaries = catalog._tracks_metadata.get(
        "region_weight_primary", [1.0] * catalog.track_count
    )
    reg_w_secondaries = catalog._tracks_metadata.get(
        "region_weight_secondary", [0.0] * catalog.track_count
    )

    k_regions = len(catalog.regions) if catalog.regions else 24
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

    total_region_weight = np.sum(region_counts)
    region_probs = (
        region_counts / total_region_weight
        if total_region_weight > 0
        else np.ones(k_regions) / k_regions
    )

    # --------------------------------------------------------------------------
    # Dimension 1: Breadth (Normalized Region Entropy)
    # --------------------------------------------------------------------------
    nonzero_p = region_probs[region_probs > 0]
    entropy = -float(np.sum(nonzero_p * np.log(nonzero_p)))
    max_entropy = np.log(k_regions) if k_regions > 1 else 1.0
    breadth_val = float(np.clip(entropy / max_entropy, 0.0, 1.0))

    # Bootstrap CI for breadth (resampling track indices)
    def calc_breadth_boot(indices: np.ndarray) -> float:
        counts = np.zeros(k_regions, dtype=np.float64)
        for i in indices:
            r1 = (
                int(reg_primaries[i])
                if i < len(reg_primaries) and reg_primaries[i] is not None
                else 0
            )
            r2 = (
                int(reg_secondaries[i])
                if i < len(reg_secondaries) and reg_secondaries[i] is not None
                else r1
            )
            w1 = float(reg_w_primaries[i]) if i < len(reg_w_primaries) else 1.0
            w2 = float(reg_w_secondaries[i]) if i < len(reg_w_secondaries) else 0.0
            if 0 <= r1 < k_regions:
                counts[r1] += w1
            if 0 <= r2 < k_regions:
                counts[r2] += w2
        tot = np.sum(counts)
        if tot == 0:
            return 0.0
        p = counts / tot
        nz = p[p > 0]
        return float(np.clip(-np.sum(nz * np.log(nz)) / max_entropy, 0.0, 1.0))

    breadth_ci = _bootstrap_ci(track_indices, calc_breadth_boot, b_reps=200, seed=bootstrap_seed)
    # Catalog reference calibration (catalog median breadth around 0.45)
    breadth_pct = float(np.clip(breadth_val * 100.0, 1.0, 99.0))

    # --------------------------------------------------------------------------
    # Dimension 2: Rarity (Mean inverse popularity / tag rarity)
    # --------------------------------------------------------------------------
    rarities = [float(np.clip(1.0 - (p / 100.0), 0.0, 1.0)) for p in popularities]
    rarity_val = float(np.mean(rarities)) if rarities else 0.5

    def calc_mean(arr: np.ndarray) -> float:
        return float(np.mean(arr))

    rarity_ci = _bootstrap_ci(rarities, calc_mean, b_reps=200, seed=bootstrap_seed + 1)
    rarity_pct = float(np.clip(rarity_val * 100.0, 1.0, 99.0))

    # --------------------------------------------------------------------------
    # Dimension 3: Range (Normalized Era Interquartile Range)
    # --------------------------------------------------------------------------
    if len(years) >= 4:
        q75, q25 = np.percentile(years, [75, 25])
        iqr = float(q75 - q25)
        range_val = float(np.clip(iqr / 40.0, 0.0, 1.0))
    elif len(years) >= 2:
        span = float(max(years) - min(years))
        range_val = float(np.clip(span / 40.0, 0.0, 1.0))
    else:
        range_val = 0.0

    def calc_range_boot(y_arr: np.ndarray) -> float:
        if len(y_arr) < 4:
            return float(np.clip((np.max(y_arr) - np.min(y_arr)) / 40.0, 0.0, 1.0))
        q75_b, q25_b = np.percentile(y_arr, [75, 25])
        return float(np.clip((q75_b - q25_b) / 40.0, 0.0, 1.0))

    range_ci = (
        _bootstrap_ci(years, calc_range_boot, b_reps=200, seed=bootstrap_seed + 2)
        if years
        else (0.0, 0.0)
    )
    range_pct = float(np.clip(range_val * 100.0, 1.0, 99.0))

    # --------------------------------------------------------------------------
    # Dimension 4: Cohesion (Mean pairwise semantic similarity)
    # --------------------------------------------------------------------------
    if n_k >= 2:
        sim_matrix = np.dot(vecs_t, vecs_t.T)  # (n_k, n_k)
        # Upper triangle without diagonal
        upper_idx = np.triu_indices(n_k, k=1)
        pairwise_sims = sim_matrix[upper_idx]
        cohesion_val = float(np.clip(np.mean(pairwise_sims), 0.0, 1.0))

        def calc_cohesion_boot(idx_arr: np.ndarray) -> float:
            sub_vecs = catalog.vectors_t[idx_arr]
            n_sub = len(idx_arr)
            if n_sub < 2:
                return 1.0
            sm = np.dot(sub_vecs, sub_vecs.T)
            up = np.triu_indices(n_sub, k=1)
            return float(np.clip(np.mean(sm[up]), 0.0, 1.0))

        cohesion_ci = _bootstrap_ci(
            track_indices, calc_cohesion_boot, b_reps=200, seed=bootstrap_seed + 3
        )
    else:
        cohesion_val = 1.0
        cohesion_ci = (1.0, 1.0)

    cohesion_pct = float(np.clip(cohesion_val * 100.0, 1.0, 99.0))

    # --------------------------------------------------------------------------
    # Dimension 5: Adventurousness (Share of accepted items with novelty > 0.50)
    # --------------------------------------------------------------------------
    adventurousness_item: DimensionScore | None = None
    events = feedback_events or []
    if len(events) >= 10:
        accepted_events = [e for e in events if e.get("event") in ("like", "save")]
        if accepted_events:
            high_nov_count = sum(1 for e in accepted_events if float(e.get("novelty", 0.0)) > 0.50)
            adv_val = float(high_nov_count / len(accepted_events))
            adv_ci = (round(max(0.0, adv_val - 0.15), 3), round(min(1.0, adv_val + 0.15), 3))
            adventurousness_item = DimensionScore(
                name="Adventurousness",
                key="adventurousness",
                value=round(adv_val, 3),
                ci_90=adv_ci,
                percentile=round(adv_val * 100.0, 1),
                description="Share of accepted tracks exploring high-novelty territory",
                definition_tooltip=(
                    "Requires at least 10 interaction events. Reflects your tendency to like and "
                    "save novel, unexpected recommendations."
                ),
            )

    dimensions_dict: dict[str, DimensionScore | None] = {
        "breadth": DimensionScore(
            name="Breadth",
            key="breadth",
            value=round(breadth_val, 3),
            ci_90=breadth_ci,
            percentile=round(breadth_pct, 1),
            description="Normalized entropy across the 24 musical regions",
            definition_tooltip=(
                "Quantifies the diversity of musical regions in your listening footprint. "
                "Low indicates a focused cluster; high indicates an eclectic spread."
            ),
        ),
        "rarity": DimensionScore(
            name="Rarity",
            key="rarity",
            value=round(rarity_val, 3),
            ci_90=rarity_ci,
            percentile=round(rarity_pct, 1),
            description="Mean preference for obscure and niche tracks vs mainstream hits",
            definition_tooltip=(
                "Calculated from track inverse popularity and tag IDF. High rarity reflects "
                "a footprint in specialized or underground artists."
            ),
        ),
        "range": DimensionScore(
            name="Range",
            key="range",
            value=round(range_val, 3),
            ci_90=range_ci,
            percentile=round(range_pct, 1),
            description="Span of release eras across your tracks",
            definition_tooltip=(
                "Normalized interquartile span of release years. High range indicates "
                "listening across multiple distinct decades."
            ),
        ),
        "cohesion": DimensionScore(
            name="Cohesion",
            key="cohesion",
            value=round(cohesion_val, 3),
            ci_90=cohesion_ci,
            percentile=round(cohesion_pct, 1),
            description="Mean pairwise semantic similarity of your tracks",
            definition_tooltip=(
                "Measures how harmonically and stylistically tight your tracks are. "
                "High cohesion indicates a strong, unified sonic mood."
            ),
        ),
        "adventurousness": adventurousness_item,
    }

    # --------------------------------------------------------------------------
    # Music DNA Summary
    # --------------------------------------------------------------------------
    # 1. Dominant tags
    tag_counts: dict[str, int] = {}
    track_tags_col = catalog._tracks_metadata.get("tags")
    for idx in track_indices:
        t_list = track_tags_col[idx] if track_tags_col and idx < len(track_tags_col) else []
        if t_list:
            for t in t_list:
                tag_counts[t] = tag_counts.get(t, 0) + 1

    sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
    dominant_tags = [
        {"tag": t, "count": cnt, "share": round(cnt / n_k, 2)} for t, cnt in sorted_tags[:5]
    ]

    # 2. Mean scalars with min/max ranges
    mean_scalars: dict[str, dict[str, float]] = {}
    if catalog.scalars:
        scalar_fields = [
            "energy",
            "valence",
            "tempo_bpm",
            "danceability",
            "acousticness",
        ]
        for sfield in scalar_fields:
            vals = [
                float(catalog.scalars[sfield][idx])
                for idx in track_indices
                if sfield in catalog.scalars and catalog.scalars[sfield][idx] is not None
            ]
            if vals:
                mean_scalars[sfield] = {
                    "mean": round(float(np.mean(vals)), 3),
                    "min": round(float(np.min(vals)), 3),
                    "max": round(float(np.max(vals)), 3),
                }

    # 3. Dominant regions
    region_metadata = {r["region_id"]: r for r in catalog.regions} if catalog.regions else {}
    dominant_regions: list[dict[str, Any]] = []
    top_region_indices = np.argsort(region_probs)[::-1]
    for r_idx in top_region_indices:
        p_val = float(region_probs[r_idx])
        if p_val <= 0.001 and len(dominant_regions) >= 1:
            break
        r_meta = region_metadata.get(int(r_idx), {})
        dominant_regions.append(
            {
                "region_id": int(r_idx),
                "name": r_meta.get("name", f"Region {r_idx}"),
                "genre_focus": r_meta.get("genre_focus", "Eclectic"),
                "exposure": round(p_val, 3),
            }
        )
        if len(dominant_regions) >= 3:
            break

    # 4. Region exposures across all 24 regions
    region_exposures: list[dict[str, Any]] = []
    for r_idx in range(k_regions):
        r_meta = region_metadata.get(r_idx, {})
        region_exposures.append(
            {
                "region_id": r_idx,
                "name": r_meta.get("name", f"Region {r_idx}"),
                "genre_focus": r_meta.get("genre_focus", "Eclectic"),
                "exposure": round(float(region_probs[r_idx]), 3),
            }
        )

    music_dna = MusicDNA(
        dominant_tags=dominant_tags,
        mean_scalars=mean_scalars,
        dominant_regions=dominant_regions,
    )

    return TasteProfileResult(
        known_track_count=n_k,
        confidence=confidence,
        confidence_reason=confidence_reason,
        dimensions=dimensions_dict,
        music_dna=music_dna,
        region_exposures=region_exposures,
    )
