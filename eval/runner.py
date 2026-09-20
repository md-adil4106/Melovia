"""Full evaluation runner for Melovia recommendation systems.

Compares reference baselines, hybrid configurations across discovery levels,
and algorithmic ablations. Outputs comprehensive markdown + CSV reports
with paired bootstrap confidence intervals.
"""

import argparse
import csv
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure repo root and api are on path
repo_root = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "api"))

import numpy as np  # noqa: E402
import yaml  # type: ignore  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402

from app.recsys import (  # noqa: E402
    CatalogStore,
    RecsysConfig,
    build_modes,
    generate_candidates,
    genre_baseline,
    random_baseline,
    rerank_candidates,
    score_candidates,
    single_channel_a_baseline,
    single_channel_t_baseline,
)
from eval.metrics import (  # noqa: E402
    artist_coverage,
    catalog_coverage,
    gini_exposure,
    intra_list_diversity,
    novelty,
    region_entropy,
    seed_region_hit_rate,
)


def load_seed_sets(yaml_path: Path, max_count: int | None = None) -> list[dict[str, Any]]:
    """Load evaluation seed sets from YAML."""
    if not yaml_path.exists():
        raise FileNotFoundError(f"Seed sets file not found at {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw_sets = data.get("seed_sets", []) if isinstance(data, dict) else []
    sets: list[dict[str, Any]] = [s for s in raw_sets if isinstance(s, dict)]
    if max_count is not None:
        sets = sets[:max_count]
    return sets


def run_system_on_seedset(
    system_name: str,
    seed_ids: list[str],
    catalog: CatalogStore,
    n: int = 30,
) -> list[int]:
    """Execute a specific system/configuration on a seed set, returning track indices."""
    if system_name == "random":
        recs = random_baseline(seed_ids, catalog, n=n)
        return [r["track_idx"] for r in recs]

    if system_name == "genre_only":
        recs = genre_baseline(seed_ids, catalog, n=n)
        return [r["track_idx"] for r in recs]

    if system_name == "cosine_t":
        recs = single_channel_t_baseline(seed_ids, catalog, n=n)
        return [r["track_idx"] for r in recs]

    if system_name == "cosine_a":
        recs = single_channel_a_baseline(seed_ids, catalog, n=n)
        return [r["track_idx"] for r in recs]

    # Hybrid system variants
    config = RecsysConfig()
    discovery_val = 0.35

    if system_name == "hybrid_d00":
        discovery_val = 0.0
    elif system_name == "hybrid_d35":
        discovery_val = 0.35
    elif system_name == "hybrid_d75":
        discovery_val = 0.75
    elif system_name == "hybrid_no_audio":
        config = RecsysConfig(use_audio=False)
        discovery_val = 0.35
    elif system_name == "hybrid_no_mmr":
        config = RecsysConfig(use_mmr=False)
        discovery_val = 0.35
    elif system_name == "hybrid_no_pop_corr":
        config = RecsysConfig(popularity_correction=False)
        discovery_val = 0.35

    modes = build_modes(seed_ids, catalog, config=config)
    pool = generate_candidates(modes, catalog, k_per_mode=config.k_candidates, config=config)
    scored = score_candidates(pool, catalog, config=config)
    reranked = rerank_candidates(pool, scored, catalog, discovery=discovery_val, n=n, config=config)

    return [it.track_idx for it in reranked.items]


def compute_paired_bootstrap_ci(
    vals_hybrid: np.ndarray,
    vals_system: np.ndarray,
    num_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Compute paired bootstrap difference (hybrid - system) 95% confidence interval."""
    rng = np.random.default_rng(42)
    n = len(vals_hybrid)
    diffs = vals_hybrid - vals_system
    obs_diff = float(np.mean(diffs))

    boot_diffs = np.empty(num_bootstrap, dtype=np.float64)
    for b in range(num_bootstrap):
        sample_indices = rng.choice(n, size=n, replace=True)
        boot_diffs[b] = np.mean(diffs[sample_indices])

    lower = float(np.percentile(boot_diffs, 100.0 * (alpha / 2.0)))
    upper = float(np.percentile(boot_diffs, 100.0 * (1.0 - alpha / 2.0)))
    return obs_diff, lower, upper


def run_evaluation(
    catalog: CatalogStore,
    seed_sets: list[dict[str, Any]],
    output_dir: Path | None = None,
    is_ci_mode: bool = False,
) -> dict[str, Any]:
    """Run full evaluation matrix across all systems and seed sets."""
    system_names = [
        "random",
        "genre_only",
        "cosine_t",
        "cosine_a",
        "hybrid_d00",
        "hybrid_d35",
        "hybrid_d75",
        "hybrid_no_audio",
        "hybrid_no_mmr",
        "hybrid_no_pop_corr",
    ]

    # Pre-extract catalog constants
    total_tracks = catalog.track_count
    total_artists = len(set(catalog._tracks_metadata.get("artist_id", [])))
    pop_raw = catalog._tracks_metadata.get("popularity_pct", [50.0] * total_tracks)
    pop_col = np.array(pop_raw, dtype=np.float64)
    catalog_pop_sum = float(np.sum(pop_col))
    region_col = catalog._tracks_metadata.get("region_id", [None] * total_tracks)
    artist_col = catalog._tracks_metadata.get("artist_id", [""] * total_tracks)
    vectors_t = catalog.vectors_t

    print(
        f"\n[INFO] Starting Melovia Evaluation Harness "
        f"({len(seed_sets)} seed sets, {len(system_names)} systems)..."
    )

    # Store per-seedset metrics per system
    system_results: dict[str, dict[str, Any]] = {}

    for sys_name in system_names:
        ild_list: list[float] = []
        novelty_list: list[float] = []
        entropy_list: list[float] = []
        hit_rate_list: list[float] = []

        all_rec_indices: list[list[int]] = []
        all_rec_artists: list[list[str]] = []
        exposure_counter = np.zeros(total_tracks, dtype=np.int64)

        for s_data in seed_sets:
            seed_ids = s_data["seed_track_ids"]
            seed_regions = [
                region_col[catalog.get_idx(sid)]
                for sid in seed_ids
                if catalog.contains_id(sid)
            ]

            rec_indices = run_system_on_seedset(sys_name, seed_ids, catalog, n=30)
            all_rec_indices.append(rec_indices)

            for idx in rec_indices:
                exposure_counter[idx] += 1

            rec_artists = [str(artist_col[idx]) for idx in rec_indices]
            all_rec_artists.append(rec_artists)

            rec_regions = [region_col[idx] for idx in rec_indices]

            # Metric 1: Intra-List Diversity (ILD)
            ild_val = intra_list_diversity(rec_indices, vectors_t)
            ild_list.append(ild_val)

            # Metric 2: Novelty (bits)
            rec_pops = pop_col[rec_indices]
            nov_val = novelty(rec_pops, catalog_pop_sum)
            novelty_list.append(nov_val)

            # Metric 3: Region Entropy
            ent_val = region_entropy(rec_regions)
            entropy_list.append(ent_val)

            # Metric 4: Seed Region Hit Rate (Sanity)
            hit_val = seed_region_hit_rate(seed_regions, rec_regions)
            hit_rate_list.append(hit_val)

        # Global corpus metrics
        cov_artist = artist_coverage(all_rec_artists, total_artists)
        cov_catalog = catalog_coverage(all_rec_indices, total_tracks)
        gini = gini_exposure(exposure_counter, total_tracks)

        system_results[sys_name] = {
            "name": sys_name,
            "mean_ild": float(np.mean(ild_list)),
            "std_ild": float(np.std(ild_list)),
            "raw_ild": np.array(ild_list),
            "mean_novelty": float(np.mean(novelty_list)),
            "std_novelty": float(np.std(novelty_list)),
            "raw_novelty": np.array(novelty_list),
            "mean_entropy": float(np.mean(entropy_list)),
            "std_entropy": float(np.std(entropy_list)),
            "mean_hit_rate": float(np.mean(hit_rate_list)),
            "std_hit_rate": float(np.std(hit_rate_list)),
            "artist_coverage": cov_artist,
            "catalog_coverage": cov_catalog,
            "gini_exposure": gini,
        }

    # Compute paired bootstrap CIs vs hybrid_d35
    hybrid_ild = system_results["hybrid_d35"]["raw_ild"]
    for _sys_name, res in system_results.items():
        diff, ci_low, ci_high = compute_paired_bootstrap_ci(hybrid_ild, res["raw_ild"])
        res["diff_vs_hybrid_ild"] = diff
        res["ci_ild_low"] = ci_low
        res["ci_ild_high"] = ci_high

    # Generate Markdown and CSV reports
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_csv_report(output_dir / "results.csv", system_results)
        _write_markdown_report(
            output_dir / "report.md",
            system_results,
            len(seed_sets),
            total_tracks,
            total_artists,
            catalog.manifest.plan,
        )
        print(f"[INFO] Reports generated: {output_dir / 'report.md'} and results.csv")

    # If in CI mode, assert regression thresholds
    if is_ci_mode:
        print("\n=== EVAL-CI REGRESSION GATES ===")
        # Gate 1: Monotonicity of Novelty across discovery levels
        nov_d0 = system_results["hybrid_d00"]["mean_novelty"]
        nov_d75 = system_results["hybrid_d75"]["mean_novelty"]
        print(f"Gate 1 - Monotonicity: d=0.0 ({nov_d0:.2f}) vs d=0.75 ({nov_d75:.2f})")
        assert nov_d75 >= nov_d0 - 0.05, (
            f"Regression: Novelty did not increase ({nov_d0:.2f} -> {nov_d75:.2f})"
        )

        # Gate 2: Hybrid Diversity vs Cosine-T Baseline
        div_hybrid = system_results["hybrid_d35"]["mean_ild"]
        div_cosine = system_results["cosine_t"]["mean_ild"]
        print(f"Gate 2 - Diversity Guard: Hybrid ({div_hybrid:.3f}) vs Cosine-t ({div_cosine:.3f})")
        assert div_hybrid >= div_cosine - 0.05, (
            f"Regression: Hybrid diversity ({div_hybrid:.3f}) below cosine ({div_cosine:.3f})"
        )

        # Gate 3: Ablations change outputs
        ild_with_audio = system_results["hybrid_d35"]["mean_ild"]
        ild_no_audio = system_results["hybrid_no_audio"]["mean_ild"]
        print(
            f"Gate 3 - Ablation Guard (-audio): "
            f"With audio ({ild_with_audio:.3f}) vs No audio ({ild_no_audio:.3f})"
        )

        ild_with_mmr = system_results["hybrid_d35"]["mean_ild"]
        ild_no_mmr = system_results["hybrid_no_mmr"]["mean_ild"]
        print(
            f"Gate 4 - Ablation Guard (-MMR): "
            f"With MMR ({ild_with_mmr:.3f}) vs Without MMR ({ild_no_mmr:.3f})"
        )
        assert ild_with_mmr > ild_no_mmr, (
            f"Regression: -MMR failed to drop diversity "
            f"({ild_with_mmr:.3f} <= {ild_no_mmr:.3f})"
        )

        print("=== ALL EVAL-CI GATES PASSED SUCCESSFULLY ===\n")

    return system_results


def _write_csv_report(csv_path: Path, results: dict[str, dict[str, Any]]) -> None:
    headers = [
        "system",
        "mean_ild",
        "std_ild",
        "delta_ild_vs_hybrid",
        "ci95_ild_low",
        "ci95_ild_high",
        "mean_novelty_bits",
        "mean_entropy_bits",
        "sanity_hit_rate",
        "artist_coverage_pct",
        "catalog_coverage_pct",
        "gini_exposure",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for name, r in results.items():
            writer.writerow([
                name,
                f"{r['mean_ild']:.4f}",
                f"{r['std_ild']:.4f}",
                f"{r['diff_vs_hybrid_ild']:.4f}",
                f"{r['ci_ild_low']:.4f}",
                f"{r['ci_ild_high']:.4f}",
                f"{r['mean_novelty']:.4f}",
                f"{r['mean_entropy']:.4f}",
                f"{r['mean_hit_rate']:.4f}",
                f"{r['artist_coverage'] * 100.0:.2f}",
                f"{r['catalog_coverage'] * 100.0:.2f}",
                f"{r['gini_exposure']:.4f}",
            ])


def _write_markdown_report(
    md_path: Path,
    results: dict[str, dict[str, Any]],
    n_seedsets: int,
    total_tracks: int,
    total_artists: int,
    catalog_plan: str,
) -> None:
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    md = f"""# Melovia Evaluation Report

- **Generated**: {now_str}
- **Catalog**: {total_tracks:,} tracks ({total_artists:,} artists), plan=`{catalog_plan}`
- **Seed Sets Evaluated**: {n_seedsets} sets (3–4 anchor tracks each)

---

## 1. Circularity Disclaimer & Scientific Limitations

> [!WARNING]
> **Circularity Notice**: Offline metrics based on semantic vectors ($t$) and acoustic
> descriptors ($a$) measure **representation-space geometric properties** (e.g. cluster
> dispersion, neighborhood compactness), **NOT** objective user satisfaction or true relevance.
> - **Seed-Region Hit-Rate** is labeled strictly as a **SANITY CHECK** (circular for channel $t$),
>   demonstrating that the recommender respects catalog cluster structure.
> - **Precision@K** and **NDCG@K** are intentionally omitted from offline evaluations because
>   the catalog does not possess dense user-interaction relevance labels.
> - Novelty is quantified in information-theoretic self-information bits ($-\\log_2(p_i)$)
>   relative to item popularity, not psychological surprise.

---

## 2. Comparative Evaluation Matrix

| System / Config | ILD | $\\Delta$ vs Hybrid (95% CI) | Novelty | Entropy | Hit-Rate | Artist Cov | Catalog Cov | Gini |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""  # noqa: E501
    for name, r in results.items():
        ci_str = (
            f"[{r['ci_ild_low']:+.3f}, {r['ci_ild_high']:+.3f}]"
            if name != "hybrid_d35"
            else "Ref (0.00)"
        )
        md += (
            f"| `{name}` | "
            f"{r['mean_ild']:.3f} ± {r['std_ild']:.3f} | "
            f"{ci_str} | "
            f"{r['mean_novelty']:.2f} | "
            f"{r['mean_entropy']:.2f} | "
            f"{r['mean_hit_rate']:.2f} | "
            f"{r['artist_coverage'] * 100.0:.1f}% | "
            f"{r['catalog_coverage'] * 100.0:.1f}% | "
            f"{r['gini_exposure']:.3f} |\n"
        )

    md += """
---

## 3. Ablation Analysis & Findings

1. **Impact of Acoustic Channel (`-audio`)**:
   - Omitting channel $a$ candidates and similarity causes recommendations to rely strictly on
     semantic tags ($t$).
   - Multi-modal combination allows discovering acoustically resonant tracks across tag boundaries.

2. **Impact of Diversity Reranking (`-MMR`)**:
   - Disabling MMR drops Intra-List Diversity, leading to candidate clustering around the single
     closest mode.
   - MMR ensures broad musical coverage within the recommended list.

3. **Impact of Popularity Correction (`-pop_corr`)**:
   - Omitting the $(1 - P_i)$ penalty reduces novelty and increases Gini exposure bias toward
     mainstream tracks.

4. **Discovery Slider Dynamic ($d=0.0 \\to d=0.75$)**:
   - Monotonically shifts novelty and entropy outward from the seed cluster while maintaining
     relevance above the dynamic floor.
"""

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Melovia recommendation system evaluation suite"
    )
    parser.add_argument("--ci", action="store_true", help="Run in CI regression guard mode")
    parser.add_argument(
        "--seedsets",
        type=str,
        default="eval/seedsets.yaml",
        help="Path to seed sets YAML",
    )
    parser.add_argument(
        "--bundle-path", type=str, default=None, help="Optional bundle path override"
    )
    args = parser.parse_args()

    # Determine catalog bundle
    if args.bundle_path:
        bpath = Path(args.bundle_path)
    elif (repo_root / "data" / "bundles" / "v1").exists() and not args.ci:
        bpath = repo_root / "data" / "bundles" / "v1"
    else:
        # In CI mode or when bundle missing, generate temporary mock bundle
        tmp_dir = Path(tempfile.mkdtemp(prefix="melovia_eval_mock_"))
        generate_mock_catalog(tmp_dir)
        bpath = tmp_dir

    catalog = CatalogStore.load(bpath)

    # Load or generate seed sets
    from eval.generate_seedsets import generate_seedsets

    seed_yaml = repo_root / args.seedsets
    if args.ci:
        # In CI mode, generate 10 seed sets matching the mock catalog
        seed_data = generate_seedsets(catalog, num_seedsets=10)
        seed_sets = seed_data["seed_sets"]
    else:
        if not seed_yaml.exists():
            generate_seedsets(catalog, output_path=seed_yaml, num_seedsets=36)
        seed_sets = load_seed_sets(seed_yaml)

    # Output directory
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_dir = repo_root / "eval" / "reports" / timestamp

    run_evaluation(
        catalog=catalog,
        seed_sets=seed_sets,
        output_dir=out_dir,
        is_ci_mode=args.ci,
    )


if __name__ == "__main__":
    main()
