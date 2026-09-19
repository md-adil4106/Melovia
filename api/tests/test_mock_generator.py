"""Tests for mock catalog generator determinism and specifications."""

import json
import sys
from pathlib import Path

# Add fixtures to path
fixtures_dir = Path(__file__).resolve().parent.parent.parent / "fixtures"
sys.path.insert(0, str(fixtures_dir))

from make_mock_catalog import generate_mock_catalog  # noqa: E402


def test_generator_determinism(tmp_path: Path) -> None:
    """Mock generator with seed=42 must produce byte-for-byte identical manifest checksums."""
    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"

    hashes1 = generate_mock_catalog(run1_dir)
    hashes2 = generate_mock_catalog(run2_dir)

    assert hashes1 == hashes2, "Hashes between two independent generator runs must be identical"

    # Verify manifest.json in both directories matches
    with open(run1_dir / "manifest.json", encoding="utf-8") as f1:
        m1 = json.load(f1)
    with open(run2_dir / "manifest.json", encoding="utf-8") as f2:
        m2 = json.load(f2)

    assert m1["track_count"] == 3000
    assert m1["dim_t"] == 128
    assert m1["dim_a"] == 128
    assert m1["files"] == m2["files"]
