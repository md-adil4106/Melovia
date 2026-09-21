"""Statistical Analysis for Double-Blind A/B Study Mode (Phase 15).

Calculates:
- Metric means, standard deviations, and mean paired differences (Hybrid - Baseline)
- Paired Student's t-test (t-stat, p-value)
- Paired Wilcoxon signed-rank test (W-stat, p-value)
- 95% Bootstrap Confidence Intervals (B=1000 resamples)
- Overall preference ratio breakdown (Hybrid vs Baseline vs Tie)
- Formatted Markdown summary table output

Usage:
  python study_analysis.py --csv path/to/study_ratings.csv
  python study_analysis.py --synthetic 50
"""

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy.stats as stats  # type: ignore


@dataclass
class MetricComparison:
    name: str
    n: int
    mean_hybrid: float
    std_hybrid: float
    mean_baseline: float
    std_baseline: float
    mean_diff: float
    ci_95_diff: tuple[float, float]
    t_stat: float
    p_val_ttest: float
    w_stat: float
    p_val_wilcoxon: float


def compute_bootstrap_ci(
    diffs: np.ndarray,
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute non-parametric bootstrap confidence interval for the mean difference."""
    if len(diffs) == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_resamples, dtype=np.float64)
    n = len(diffs)
    for b in range(n_resamples):
        sample = rng.choice(diffs, size=n, replace=True)
        boot_means[b] = np.mean(sample)
    alpha = (1.0 - ci) / 2.0
    low = float(np.percentile(boot_means, 100.0 * alpha))
    high = float(np.percentile(boot_means, 100.0 * (1.0 - alpha)))
    return (low, high)


def analyze_ratings(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Runs paired tests and bootstrap analysis across the 4 core Likert dimensions."""
    n = len(records)
    if n == 0:
        return {"error": "No records to analyze", "n": 0}

    metrics = ["relevance", "discovery", "flow", "satisfaction"]
    comparisons: list[MetricComparison] = []

    for m in metrics:
        h_vals = np.array([float(r[f"{m}_hybrid"]) for r in records], dtype=np.float64)
        b_vals = np.array([float(r[f"{m}_baseline"]) for r in records], dtype=np.float64)
        diffs = h_vals - b_vals

        mean_h = float(np.mean(h_vals))
        std_h = float(np.std(h_vals, ddof=1)) if n > 1 else 0.0
        mean_b = float(np.mean(b_vals))
        std_b = float(np.std(b_vals, ddof=1)) if n > 1 else 0.0
        mean_diff = float(np.mean(diffs))

        # Bootstrap 95% CI
        ci_low, ci_high = compute_bootstrap_ci(diffs)

        # Paired t-test
        if np.all(diffs == 0.0) or n < 2:
            t_stat, p_ttest = 0.0, 1.0
        else:
            try:
                res_t = stats.ttest_rel(h_vals, b_vals)
                t_stat, p_ttest = float(res_t.statistic), float(res_t.pvalue)
            except Exception:
                t_stat, p_ttest = 0.0, 1.0

        # Wilcoxon signed-rank test
        if np.all(diffs == 0.0) or n < 2:
            w_stat, p_wilcoxon = 0.0, 1.0
        else:
            try:
                res_w = stats.wilcoxon(h_vals, b_vals, zero_method="wilcox", alternative="two-sided")
                w_stat, p_wilcoxon = float(res_w.statistic), float(res_w.pvalue)
            except Exception:
                w_stat, p_wilcoxon = 0.0, 1.0

        comparisons.append(
            MetricComparison(
                name=m.capitalize(),
                n=n,
                mean_hybrid=mean_h,
                std_hybrid=std_h,
                mean_baseline=mean_b,
                std_baseline=std_b,
                mean_diff=mean_diff,
                ci_95_diff=(ci_low, ci_high),
                t_stat=t_stat,
                p_val_ttest=p_ttest,
                w_stat=w_stat,
                p_val_wilcoxon=p_wilcoxon,
            )
        )

    # Overall preference counts
    prefs = [r.get("preferred_overall_arm", "tie").lower() for r in records]
    n_hybrid_pref = sum(1 for p in prefs if p == "hybrid")
    n_baseline_pref = sum(1 for p in prefs if p == "baseline")
    n_tie = sum(1 for p in prefs if p in ("tie", "none", ""))

    return {
        "n": n,
        "comparisons": comparisons,
        "preference": {
            "hybrid_pct": 100.0 * n_hybrid_pref / n,
            "baseline_pct": 100.0 * n_baseline_pref / n,
            "tie_pct": 100.0 * n_tie / n,
            "counts": {"hybrid": n_hybrid_pref, "baseline": n_baseline_pref, "tie": n_tie},
        },
    }


def format_markdown_report(analysis: dict[str, Any]) -> str:
    """Formats analysis results as a GitHub Markdown document."""
    if "error" in analysis:
        return f"# Melovia Study Analysis\n\nError: {analysis['error']}"

    n = analysis["n"]
    pref = analysis["preference"]
    comparisons: list[MetricComparison] = analysis["comparisons"]

    lines = [
        "# Melovia Double-Blind A/B Study: Empirical Evaluation Report",
        "",
        f"**Sample Size (N)**: {n} participant evaluations",
        f"**Design**: Paired within-subjects, double-blind randomized assignment (System Hybrid vs Genre/Tag Baseline)",
        "",
        "## 1. Dimension Ratings (1–5 Likert Scale)",
        "",
        "| Metric | Hybrid (Mean ± SD) | Baseline (Mean ± SD) | Difference (Delta) | 95% Bootstrap CI | Paired t (p) | Wilcoxon W (p) | Sig |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |",
    ]

    for c in comparisons:
        sig = "***" if c.p_val_wilcoxon < 0.001 else ("**" if c.p_val_wilcoxon < 0.01 else ("*" if c.p_val_wilcoxon < 0.05 else "ns"))
        diff_str = f"+{c.mean_diff:.2f}" if c.mean_diff > 0 else f"{c.mean_diff:.2f}"
        ci_str = f"[{c.ci_95_diff[0]:+.2f}, {c.ci_95_diff[1]:+.2f}]"
        t_str = f"t={c.t_stat:.2f} (p={c.p_val_ttest:.3f})"
        w_str = f"W={c.w_stat:.1f} (p={c.p_val_wilcoxon:.3f})"

        lines.append(
            f"| **{c.name}** | {c.mean_hybrid:.2f} ± {c.std_hybrid:.2f} | {c.mean_baseline:.2f} ± {c.std_baseline:.2f} | {diff_str} | {ci_str} | {t_str} | {w_str} | **{sig}** |"
        )

    lines.extend([
        "",
        "Significance codes: `***` p < 0.001, `**` p < 0.01, `*` p < 0.05, `ns` not significant",
        "",
        "## 2. Overall Preference",
        "",
        f"- **System Hybrid**: {pref['hybrid_pct']:.1f}% ({pref['counts']['hybrid']}/{n})",
        f"- **Genre Baseline**: {pref['baseline_pct']:.1f}% ({pref['counts']['baseline']}/{n})",
        f"- **No Preference / Tie**: {pref['tie_pct']:.1f}% ({pref['counts']['tie']}/{n})",
        "",
        "## 3. Conclusions & Key Findings",
        "",
    ])

    # Dynamic conclusions
    disc = next((c for c in comparisons if c.name == "Discovery"), None)
    flow = next((c for c in comparisons if c.name == "Flow"), None)

    if disc and disc.mean_diff > 0 and disc.p_val_wilcoxon < 0.05:
        lines.append(f"- **Discovery Uplift Confirmed**: System Hybrid demonstrates statistically significant discovery advantage (Delta = +{disc.mean_diff:.2f}, p = {disc.p_val_wilcoxon:.4f}).")
    if flow and flow.mean_diff > 0 and flow.p_val_wilcoxon < 0.05:
        lines.append(f"- **Flow Coherence Confirmed**: Multi-channel sequencing and reranking significantly outperforms baseline genre overlap (Delta = +{flow.mean_diff:.2f}, p = {flow.p_val_wilcoxon:.4f}).")

    if pref["hybrid_pct"] > pref["baseline_pct"]:
        lines.append(f"- **Subjective Win Rate**: {pref['hybrid_pct']:.1f}% of participants preferred the Melovia Hybrid engine overall.")

    return "\n".join(lines)


def generate_synthetic_data(n: int = 50, seed: int = 42) -> list[dict[str, Any]]:
    """Generates synthetic rating data following realistic distributions for validation testing."""
    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []

    for i in range(n):
        # Hybrid scores higher on discovery and flow, equal/slightly higher on relevance
        rel_h = int(np.clip(rng.normal(4.2, 0.7), 1, 5))
        disc_h = int(np.clip(rng.normal(4.4, 0.6), 1, 5))
        flow_h = int(np.clip(rng.normal(4.1, 0.8), 1, 5))
        sat_h = int(np.clip(rng.normal(4.3, 0.7), 1, 5))

        rel_b = int(np.clip(rng.normal(3.8, 0.8), 1, 5))
        disc_b = int(np.clip(rng.normal(2.9, 0.9), 1, 5))
        flow_b = int(np.clip(rng.normal(3.2, 0.9), 1, 5))
        sat_b = int(np.clip(rng.normal(3.4, 0.8), 1, 5))

        h_score = rel_h + disc_h + flow_h + sat_h
        b_score = rel_b + disc_b + flow_b + sat_b

        pref = "hybrid" if h_score > b_score else ("baseline" if b_score > h_score else "tie")

        records.append({
            "rating_id": f"syn_{i}",
            "session_id": f"sess_{i}",
            "relevance_hybrid": rel_h,
            "discovery_hybrid": disc_h,
            "flow_hybrid": flow_h,
            "satisfaction_hybrid": sat_h,
            "relevance_baseline": rel_b,
            "discovery_baseline": disc_b,
            "flow_baseline": flow_b,
            "satisfaction_baseline": sat_b,
            "preferred_overall_arm": pref,
            "feedback_text": "Synthetic test participant feedback",
        })

    return records


def load_csv(file_path: Path) -> list[dict[str, Any]]:
    """Loads CSV export from Melovia /study/export."""
    records: list[dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Analyze Melovia Study Mode results")
    parser.add_argument("--csv", type=str, help="Path to exported study_ratings.csv")
    parser.add_argument("--synthetic", type=int, default=None, help="Generate N synthetic ratings for testing")
    parser.add_argument("--output", type=str, default=None, help="Optional path to save Markdown report")
    args = parser.parse_args()

    if args.synthetic is not None:
        records = generate_synthetic_data(n=args.synthetic)
    elif args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"Error: file not found at {csv_path}", file=sys.stderr)
            sys.exit(1)
        records = load_csv(csv_path)
    else:
        print("No CSV provided, running on default synthetic N=50 participant trial...")
        records = generate_synthetic_data(n=50)

    analysis = analyze_ratings(records)
    md_report = format_markdown_report(analysis)

    print(md_report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_report, encoding="utf-8")
        print(f"\nSaved report to: {out_path}")


if __name__ == "__main__":
    main()
