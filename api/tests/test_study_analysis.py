"""Unit tests for study mode statistical analysis (Phase 15)."""

import sys
from pathlib import Path

# Add repo root to sys.path so eval can be imported
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from eval.study_analysis import (  # noqa: E402
    analyze_ratings,
    compute_bootstrap_ci,
    format_markdown_report,
    generate_synthetic_data,
)


def test_bootstrap_ci_computation():
    """Verify bootstrap confidence interval produces sensible bounds."""
    diffs = [1.0, 2.0, 1.0, 3.0, 2.0, 1.0, 2.0]
    import numpy as np

    arr = np.array(diffs, dtype=np.float64)
    low, high = compute_bootstrap_ci(arr, n_resamples=500, ci=0.95, seed=42)
    assert low < high
    assert low > 0.5
    assert high < 3.0


def test_synthetic_data_and_paired_analysis():
    """Verify synthetic rating generation and paired statistical testing."""
    records = generate_synthetic_data(n=30, seed=123)
    assert len(records) == 30

    analysis = analyze_ratings(records)
    assert analysis["n"] == 30
    assert "comparisons" in analysis
    assert len(analysis["comparisons"]) == 4

    metrics = {c.name: c for c in analysis["comparisons"]}
    assert "Relevance" in metrics
    assert "Discovery" in metrics
    assert "Flow" in metrics
    assert "Satisfaction" in metrics

    # Verify Discovery metrics
    disc = metrics["Discovery"]
    assert disc.mean_hybrid > 0
    assert disc.mean_baseline > 0
    assert disc.ci_95_diff[0] <= disc.ci_95_diff[1]
    assert 0.0 <= disc.p_val_wilcoxon <= 1.0
    assert 0.0 <= disc.p_val_ttest <= 1.0

    # Verify Markdown formatting
    md = format_markdown_report(analysis)
    assert "Empirical Evaluation Report" in md
    assert "Discovery" in md
    assert "Wilcoxon W" in md
    assert "Overall Preference" in md
