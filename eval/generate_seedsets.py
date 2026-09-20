"""Auto-generate deterministic tag/region-coherent seed sets for Melovia offline evaluation.

Produces at least 30 seed sets (3-4 tracks each) with fixed random seed (SEED=42).
Writes output to eval/seedsets.yaml.
"""

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

# Ensure repo root and api are on path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "api"))

import numpy as np  # noqa: E402
import yaml  # type: ignore  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402

from app.recsys.catalog import CatalogStore  # noqa: E402

SEED = 42


def generate_seedsets(
    catalog: CatalogStore,
    output_path: Path | None = None,
    num_seedsets: int = 36,
) -> dict[str, Any]:
    """Generate >=30 tag/region-coherent seed sets from catalog."""
    rng = np.random.default_rng(SEED)
    region_col = catalog._tracks_metadata.get("region_id", [])

    # Group track indices by region
    region_to_tracks: dict[int, list[int]] = {}
    for idx, reg in enumerate(region_col):
        if reg is not None:
            region_to_tracks.setdefault(int(reg), []).append(idx)

    available_regions = sorted(region_to_tracks.keys())
    if not available_regions:
        # Fallback if no regions: group by artist or genre tags
        available_regions = [0]
        region_to_tracks[0] = list(range(catalog.track_count))

    seed_sets: list[dict[str, Any]] = []
    sets_per_region = max(1, int(np.ceil(num_seedsets / len(available_regions))))

    set_counter = 1
    for reg_id in available_regions:
        tracks_in_reg = np.array(region_to_tracks[reg_id])
        if len(tracks_in_reg) < 4:
            continue

        # Shuffle deterministically
        shuffled = rng.permutation(tracks_in_reg)

        for s_idx in range(sets_per_region):
            if set_counter > num_seedsets:
                break

            # Pick 3 or 4 tracks
            size = 3 if (set_counter % 2 == 1) else 4
            offset = (s_idx * size) % (len(shuffled) - size)
            chosen_indices = shuffled[offset : offset + size]

            track_items = [catalog.get_track_dict(int(idx)) for idx in chosen_indices]
            seed_ids = [catalog.get_id(int(idx)) for idx in chosen_indices]

            seed_sets.append(
                {
                    "id": f"seedset_{set_counter:02d}",
                    "region_id": int(reg_id),
                    "name": f"Region {reg_id} Cluster {s_idx + 1}",
                    "track_count": len(seed_ids),
                    "seed_track_ids": seed_ids,
                    "seed_tracks": [
                        {
                            "id": t["id"],
                            "track_idx": t["track_idx"],
                            "title": t["title"],
                            "artist_name": t["artist_name"],
                            "year": t.get("year"),
                        }
                        for t in track_items
                    ],
                }
            )
            set_counter += 1

    payload = {
        "version": "1.0",
        "description": f"Auto-generated deterministic evaluation seed sets (N={len(seed_sets)})",
        "seed": SEED,
        "seed_sets_count": len(seed_sets),
        "seed_sets": seed_sets,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(payload, f, sort_keys=False, indent=2)
        print(f"[INFO] Successfully generated {len(seed_sets)} seed sets -> {output_path}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Melovia evaluation seed sets")
    parser.add_argument(
        "--output", type=str, default="eval/seedsets.yaml", help="Target output YAML path"
    )
    parser.add_argument("--count", type=int, default=36, help="Minimum number of seed sets (>=30)")
    args = parser.parse_args()

    bundle_path = repo_root / "data" / "bundles" / "v1"
    if bundle_path.exists():
        print(f"[INFO] Using catalog from {bundle_path}")
        catalog = CatalogStore.load(bundle_path)
    else:
        print("[INFO] Generating temporary mock catalog...")
        tmp_dir = Path(tempfile.mkdtemp(prefix="melovia_mock_seedsets_"))
        generate_mock_catalog(tmp_dir)
        catalog = CatalogStore.load(tmp_dir)

    out_file = repo_root / args.output
    generate_seedsets(catalog, output_path=out_file, num_seedsets=args.count)


if __name__ == "__main__":
    main()
