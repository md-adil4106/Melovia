"""Real-relevance evaluation proxy via public playlist continuation (JSPF).

EVALUATION METHODOLOGY & COVERAGE NOTICE:
- Maps public ListenBrainz JSPF playlists to the Melovia catalog via MBID.
- For playlists with >= 8 catalog-covered tracks, the first 4 tracks serve as seeds,
  and the remaining catalog-covered tracks constitute the ground-truth relevant set.
- Computes Recall@K and NDCG@K across recommendations.
- CRITICAL REQUIREMENT: These metrics MUST NEVER be reported without explicitly stating
  catalog track coverage alongside them. If coverage is sparse (< 20%), metrics reflect
  catalog overlap rather than genuine algorithmic quality.
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

# Ensure repo root and api are on path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "api"))

import numpy as np  # noqa: E402

from app.recsys import (  # noqa: E402
    CatalogStore,
    RecsysConfig,
    build_modes,
    generate_candidates,
    rerank_candidates,
    score_candidates,
)


def parse_jspf_playlists(filepath: Path) -> list[dict[str, Any]]:
    """Parse a JSPF JSON file or list of JSPF playlists."""
    if not filepath.exists():
        return []

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    playlists: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if "playlist" in item:
                playlists.append(item["playlist"])
    elif isinstance(data, dict):
        if "playlist" in data:
            playlists.append(data["playlist"])
        elif "playlists" in data:
            playlists.extend(data["playlists"])

    return playlists


def extract_mbid(track_entry: dict[str, Any]) -> str | None:
    """Extract recording MBID from JSPF track entry."""
    # JSPF identifier field often formatted as 'https://musicbrainz.org/recording/<mbid>'
    identifier = track_entry.get("identifier")
    if isinstance(identifier, list) and identifier:
        identifier = identifier[0]

    if isinstance(identifier, str):
        if "musicbrainz.org/recording/" in identifier:
            return identifier.split("musicbrainz.org/recording/")[-1].strip("/").lower()
        if len(identifier) == 36 and identifier.count("-") == 4:
            return identifier.lower()

    mbid = track_entry.get("mbid") or track_entry.get("musicbrainz_id")
    if isinstance(mbid, str) and len(mbid) == 36:
        return mbid.lower()

    return None


def compute_dcg_at_k(hits_binary: list[int], k: int) -> float:
    """Compute Discounted Cumulative Gain at K."""
    dcg = 0.0
    for r in range(min(k, len(hits_binary))):
        if hits_binary[r]:
            dcg += 1.0 / math.log2(r + 2)  # rank 1 is log2(2)=1
    return dcg


def evaluate_playlist_continuation(
    jspf_path: Path | None,
    catalog: CatalogStore,
    k_eval: int = 30,
) -> dict[str, Any] | None:
    """Evaluate playlist continuation if valid JSPF file is provided."""
    if not jspf_path or not jspf_path.exists():
        print("\n[INFO] No public JSPF playlist file provided or path does not exist.")
        print("To run the playlist continuation proxy, download ListenBrainz playlists (JSPF)")
        print("and run: python eval/playlist_continuation.py --jspf-path <path_to_jspf.json>\n")
        return None

    playlists = parse_jspf_playlists(jspf_path)
    if not playlists:
        print(f"[INFO] No valid JSPF playlists found in {jspf_path}.")
        return None

    total_playlist_tracks = 0
    total_covered_tracks = 0
    valid_evaluation_playlists = []

    config = RecsysConfig()

    for pl in playlists:
        tracks = pl.get("track", [])
        total_playlist_tracks += len(tracks)

        covered_indices: list[int] = []
        for t in tracks:
            mbid = extract_mbid(t)
            if mbid and catalog.contains_mbid(mbid):
                covered_indices.append(catalog.get_idx_by_mbid(mbid))

        total_covered_tracks += len(covered_indices)

        # Require at least 8 catalog-covered tracks: 4 seeds + >=4 ground-truth targets
        if len(covered_indices) >= 8:
            valid_evaluation_playlists.append(
                {
                    "title": pl.get("title", "Untitled"),
                    "seed_indices": covered_indices[:4],
                    "relevant_indices": set(covered_indices[4:]),
                }
            )

    catalog_coverage_pct = (total_covered_tracks / max(1, total_playlist_tracks)) * 100.0

    print("\n" + "=" * 80)
    print("PLAYLIST CONTINUATION PROXY EVALUATION (ListenBrainz JSPF)")
    print("=" * 80)
    print(f"Total playlists inspected:       {len(playlists):,}")
    print(f"Total playlist track entries:    {total_playlist_tracks:,}")
    cov_str = f"{total_covered_tracks:,} ({catalog_coverage_pct:.2f}% coverage)"
    print(f"Catalog-covered tracks:          {cov_str}")
    print(f"Playlists with >= 8 covered tracks: {len(valid_evaluation_playlists):,}")
    print("=" * 80)

    if len(valid_evaluation_playlists) == 0:
        print("\n[NOTICE] 0 playlists met the >= 8 catalog-covered tracks threshold.")
        print(f"Catalog coverage is currently {catalog_coverage_pct:.2f}%.")
        print("To run continuation, a larger catalog covering these MBIDs is required.")
        print("Skipping continuation scoring (zero eligible playlists).\n")
        return {
            "eligible_playlists": 0,
            "catalog_coverage_pct": round(catalog_coverage_pct, 2),
            "recall_at_30": None,
            "ndcg_at_30": None,
        }

    recalls_30: list[float] = []
    ndcgs_30: list[float] = []

    for pl_data in valid_evaluation_playlists:
        seed_ids = [catalog.get_id(idx) for idx in pl_data["seed_indices"]]
        target_set = pl_data["relevant_indices"]

        modes = build_modes(seed_ids, catalog, config=config)
        pool = generate_candidates(modes, catalog, k_per_mode=config.k_candidates)
        scored = score_candidates(pool, catalog, config=config)
        reranked = rerank_candidates(pool, scored, catalog, discovery=0.35, n=k_eval, config=config)

        rec_indices = [it.track_idx for it in reranked.items]
        hits_binary = [1 if idx in target_set else 0 for idx in rec_indices]

        # Recall@K
        hits_count = sum(hits_binary)
        recall = hits_count / max(1, len(target_set))
        recalls_30.append(recall)

        # NDCG@K
        dcg = compute_dcg_at_k(hits_binary, k_eval)
        ideal_hits = [1] * min(k_eval, len(target_set))
        idcg = compute_dcg_at_k(ideal_hits, k_eval)
        ndcg = (dcg / idcg) if idcg > 0 else 0.0
        ndcgs_30.append(ndcg)

    mean_recall = float(np.mean(recalls_30))
    mean_ndcg = float(np.mean(ndcgs_30))

    print(f"\nRESULTS (evaluated on {len(valid_evaluation_playlists)} playlists):")
    print(f"Catalog Coverage:  {catalog_coverage_pct:.2f}%")
    print(f"Recall@{k_eval}:          {mean_recall:.4f}")
    print(f"NDCG@{k_eval}:            {mean_ndcg:.4f}\n")

    return {
        "eligible_playlists": len(valid_evaluation_playlists),
        "catalog_coverage_pct": round(catalog_coverage_pct, 2),
        "recall_at_30": round(mean_recall, 4),
        "ndcg_at_30": round(mean_ndcg, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Melovia on public JSPF playlists")
    parser.add_argument("--jspf-path", type=str, default=None, help="Path to JSPF playlist export")
    parser.add_argument(
        "--bundle-path", type=str, default="data/bundles/v1", help="Path to catalog bundle"
    )
    parser.add_argument("--k", type=int, default=30, help="Top-K cutoff for Recall/NDCG")
    args = parser.parse_args()

    bundle_dir = repo_root / args.bundle_path
    if not bundle_dir.exists():
        print(f"[ERROR] Bundle directory not found at {bundle_dir}")
        sys.exit(1)

    catalog = CatalogStore.load(bundle_dir)
    jspf_file = Path(args.jspf_path) if args.jspf_path else None
    evaluate_playlist_continuation(jspf_file, catalog, k_eval=args.k)


if __name__ == "__main__":
    main()
