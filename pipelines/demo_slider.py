"""Validation demo script for Melovia Discovery Control (Familiarity <-> Discovery).

Prints top-10 recommended tracks at d=0, 0.5, 1.0 along with a quantitative
metrics comparison table across d in {0.0, 0.25, 0.5, 0.75, 1.0}.
"""

import sys
import tempfile
from pathlib import Path

# Ensure api and repo root are in python path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "api"))

import numpy as np  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402

from app.recsys import (  # noqa: E402
    CatalogStore,
    RecsysConfig,
    build_modes,
    generate_candidates,
    rerank_candidates,
    score_candidates,
)


def run_demo() -> None:
    bundle_path = repo_root / "data" / "bundles" / "v1"
    if not bundle_path.exists():
        print("[INFO] Bundle v1 not found at data/bundles/v1. Generating temporary mock bundle...")
        tmp_dir = Path(tempfile.mkdtemp(prefix="melovia_demo_"))
        generate_mock_catalog(tmp_dir)
        catalog = CatalogStore.load(tmp_dir)
    else:
        print(f"[INFO] Loading catalog from {bundle_path}...")
        catalog = CatalogStore.load(bundle_path)

    config = RecsysConfig()
    total_tracks = catalog.track_count
    print(f"[INFO] Catalog loaded: {total_tracks:,} tracks, plan={catalog.manifest.plan}")

    # Select 2 sample seeds
    seed_idx = [0, 1]
    seed_ids = [catalog.get_id(i) for i in seed_idx]
    seed_tracks = [catalog.get_track_dict(i) for i in seed_idx]

    print("\n" + "=" * 80)
    print("MELOVIA DISCOVERY CONTROL DEMO (Familiarity <-> Discovery)")
    print("=" * 80)
    print("Selected Seed Tracks:")
    for s in seed_tracks:
        print(f"  * {s['title']} — {s['artist_name']} ({s.get('year') or 'N/A'})")

    # 1. Taste modes and candidate retrieval
    modes = build_modes(seed_ids, catalog, config=config)
    pool = generate_candidates(modes, catalog, k_per_mode=config.k_candidates)
    scored = score_candidates(pool, catalog, config=config)

    print(f"\nRetrieved candidate pool: {pool.size:,} candidates")

    # 2. Print Top-10 at d = 0.0, 0.5, 1.0
    key_d_values = [0.0, 0.5, 1.0]
    descriptions = {
        0.0: "d = 0.00 (Pure Familiarity / High Acoustic & Semantic Cohesion)",
        0.5: "d = 0.50 (Balanced Discovery / Novelty + Cohesion Blend)",
        1.0: "d = 1.00 (Maximum Discovery / Serendipity & Exploratory Reach)",
    }

    for d in key_d_values:
        reranked = rerank_candidates(pool, scored, catalog, discovery=d, n=10, config=config)
        print("\n" + "-" * 80)
        print(f"TOP 10 RECOMMENDATIONS — {descriptions[d]}")
        print("-" * 80)
        print(f"{'#':<3} {'Title':<28} {'Artist':<22} {'Score':<7} {'Nov':<6} {'Fam':<6} {'ArtNew':<7} {'Pop%':<5}")
        print("-" * 80)
        for rank, item in enumerate(reranked.items, 1):
            t = catalog.get_track_dict(item.track_idx)
            sig = item.signals
            title = (t["title"][:26] + "..") if len(t["title"]) > 28 else t["title"]
            artist = (t["artist_name"][:20] + "..") if len(t["artist_name"]) > 22 else t["artist_name"]
            art_new = "Yes" if sig["artist_new"] else "No"
            print(
                f"{rank:<3} {title:<28} {artist:<22} {item.score:<7.3f} "
                f"{sig['novelty']:<6.2f} {sig['familiarity']:<6.2f} {art_new:<7} {sig['popularity_pct']:<5.1f}"
            )

    # 3. Metrics Summary Table across 5 d values
    d_grid = [0.0, 0.25, 0.5, 0.75, 1.0]
    print("\n" + "=" * 80)
    print("METRICS TABLE ACROSS DISCOVERY SLIDER (Top 30 Tracks)")
    print("=" * 80)
    print(f"{'Discovery (d)':<15} {'Mean Nov':<12} {'Mean Fam':<12} {'Artist New%':<14} {'Mean Pop%':<12} {'Mean Rel':<10} {'Unique Artists':<14}")
    print("-" * 80)

    for d in d_grid:
        res = rerank_candidates(pool, scored, catalog, discovery=d, n=30, config=config)
        items = res.items
        novs = [it.signals["novelty"] for it in items]
        fams = [it.signals["familiarity"] for it in items]
        art_news = [100.0 if it.signals["artist_new"] else 0.0 for it in items]
        pops = [it.signals["popularity_pct"] for it in items]
        rels = [it.signals["relevance"] for it in items]
        artists = {catalog.get_track_dict(it.track_idx)["artist_id"] for it in items}

        print(
            f"{d:<15.2f} "
            f"{np.mean(novs):<12.3f} "
            f"{np.mean(fams):<12.3f} "
            f"{np.mean(art_news):<14.1f}% "
            f"{np.mean(pops):<12.1f}% "
            f"{np.mean(rels):<10.3f} "
            f"{len(artists):<14}"
        )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_demo()
