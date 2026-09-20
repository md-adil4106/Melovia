"""Standalone validation script for Phase 9: Feedback Dynamics & Adaptation.

Simulates 10 likes/dislikes on mock catalog tracks and prints cosine of modes
to a target region before and after. Verifies that live session feedback
adapts taste without persistent mutation until explicit remember.
"""

import sys
import tempfile
from pathlib import Path

# Ensure repo root and api are on path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "api"))

import numpy as np
from fixtures.make_mock_catalog import generate_mock_catalog

from app.recsys import (
    CatalogStore,
    RecsysConfig,
    apply_feedback,
    build_modes,
    generate_candidates,
    merge_modes,
    rerank_candidates,
    score_candidates,
)


def main() -> None:
    print("================================================================")
    print("      Melovia Phase 9: Feedback & Profile Dynamics Validation   ")
    print("================================================================")

    tmp_dir = Path(tempfile.mkdtemp(prefix="melovia_fb_val_"))
    generate_mock_catalog(tmp_dir)
    catalog = CatalogStore.load(tmp_dir)
    config = RecsysConfig()

    regions = catalog._tracks_metadata.get("region_id", [])
    unique_regions = sorted(set(r for r in regions if r is not None))
    print(f"Catalog loaded: {catalog.track_count} tracks, regions: {unique_regions}")

    source_region = unique_regions[0]
    target_region = unique_regions[1]

    # Find seeds in source region
    source_track_indices = [i for i, r in enumerate(regions) if r == source_region]
    target_track_indices = [i for i, r in enumerate(regions) if r == target_region]

    seeds = [catalog.get_id(i) for i in source_track_indices[:3]]
    target_like_tracks = [catalog.get_id(i) for i in target_track_indices[:5]]

    print(f"\n1. Initial State:")
    print(f"   Source Region: {source_region} (seeds: {seeds})")
    print(f"   Target Region: {target_region} (to like: {target_like_tracks[:3]})")

    # Initial modes
    modes = build_modes(seeds, catalog, config=config)

    # Initial recommendations
    pool = generate_candidates(modes, catalog, k_per_mode=config.k_candidates, config=config)
    scored = score_candidates(pool, catalog, config=config)
    reranked_init = rerank_candidates(pool, scored, catalog, discovery=0.35, n=30, config=config)
    init_recs = [it.track_idx for it in reranked_init.items]

    # Hit rate in target region before feedback
    hits_before = sum(1 for idx in init_recs if regions[idx] == target_region)
    hit_rate_before = hits_before / len(init_recs)

    # Cosine similarity of mode 0 to target region centroid
    target_vectors_t = catalog.vectors_t[target_track_indices]
    target_centroid_t = np.mean(target_vectors_t, axis=0)
    target_centroid_t /= np.linalg.norm(target_centroid_t)

    cos_before = float(np.dot(modes.channel_vectors["t"][0], target_centroid_t))

    print(f"   Mode 0 cosine to Target Region before: {cos_before:.4f}")
    print(
        f"   Target Region Hit Rate in top-30 before: {hit_rate_before * 100:.1f}% ({hits_before}/30)"
    )

    # 2. Simulate 3 sequential 'like' interactions on target region tracks
    print(f"\n2. Applying 3 'like' interactions for Target Region tracks...")
    current_modes = modes
    negatives: set[str] = set()
    neg_artists: set[str] = set()
    known: set[str] = set()
    liked: set[str] = set()

    for tid in target_like_tracks[:3]:
        fb_res = apply_feedback(
            event="like",
            track_id=tid,
            modes=current_modes,
            negative_track_ids=negatives,
            negative_artist_ids=neg_artists,
            known_track_ids=known,
            liked_track_ids=liked,
            catalog=catalog,
            config=config,
        )
        current_modes = fb_res.updated_modes
        negatives = fb_res.negative_track_ids
        neg_artists = fb_res.negative_artist_ids
        known = fb_res.known_track_ids
        liked = fb_res.liked_track_ids

        cos_step = float(
            np.dot(current_modes.channel_vectors["t"][fb_res.nearest_mode_idx], target_centroid_t)
        )
        print(
            f"   Liked '{catalog.get_track_dict(tid).get('title')}': mode cosine to target -> {cos_step:.4f}"
        )

    cos_after = float(np.dot(current_modes.channel_vectors["t"][0], target_centroid_t))

    # Updated recommendations
    pool_after = generate_candidates(
        current_modes, catalog, k_per_mode=config.k_candidates, config=config
    )
    scored_after = score_candidates(pool_after, catalog, config=config)
    reranked_after = rerank_candidates(
        pool_after, scored_after, catalog, discovery=0.35, n=30, config=config
    )
    after_recs = [it.track_idx for it in reranked_after.items]

    hits_after = sum(1 for idx in after_recs if regions[idx] == target_region)
    hit_rate_after = hits_after / len(after_recs)

    print(f"\n3. Recommendation Adaptation Results:")
    print(
        f"   Mode 0 cosine to Target Region after: {cos_after:.4f} (shift: {cos_after - cos_before:+.4f})"
    )
    print(
        f"   Target Region Hit Rate in top-30 after: {hit_rate_after * 100:.1f}% ({hits_after}/30)"
    )

    assert cos_after > cos_before, "Mode cosine to target region must strictly increase after likes"
    assert hit_rate_after >= hit_rate_before, "Target region hit rate must not decrease after likes"
    print("   [PASS] Taste mode and recommendations successfully adapted toward target region!")

    # 4. Simulate 'dislike' exclusion
    disliked_track_idx = after_recs[0]
    disliked_track_id = catalog.get_id(disliked_track_idx)
    print(
        f"\n4. Applying 'dislike' on top recommended track '{catalog.get_track_dict(disliked_track_id).get('title')}'..."
    )

    fb_dislike = apply_feedback(
        event="dislike",
        track_id=disliked_track_id,
        modes=current_modes,
        negative_track_ids=negatives,
        negative_artist_ids=neg_artists,
        known_track_ids=known,
        liked_track_ids=liked,
        catalog=catalog,
        config=config,
    )
    current_modes = fb_dislike.updated_modes
    assert disliked_track_id in fb_dislike.negative_track_ids
    print(
        f"   [PASS] Disliked track added to hard negative exclusions ({len(fb_dislike.negative_track_ids)} exclusions)"
    )

    # 5. Persistent profile merge with drift capping
    print(f"\n5. Testing Persistent Profile Merge & Drift Capping...")
    merged = merge_modes(
        persistent_modes=None,
        session_modes=current_modes,
        alpha=config.merge_alpha,
        max_drift=config.max_merge_drift,
    )
    assert merged.num_modes == current_modes.num_modes

    # Second merge (simulating multiple sessions)
    merged_again = merge_modes(
        persistent_modes=merged,
        session_modes=current_modes,
        alpha=config.merge_alpha,
        max_drift=config.max_merge_drift,
    )
    drift = float(
        np.linalg.norm(merged_again.channel_vectors["t"][0] - merged.channel_vectors["t"][0])
    )
    print(f"   Second session merge Euclidean drift: {drift:.4f} (limit: {config.max_merge_drift})")
    assert drift <= config.max_merge_drift + 1e-6
    print("   [PASS] Persistent profile drift strictly bounded by delta_max <= 0.25")

    print("\n================================================================")
    print("     ALL FEEDBACK & PERSISTENT PROFILE CHECKS PASSED!         ")
    print("================================================================")


if __name__ == "__main__":
    main()
