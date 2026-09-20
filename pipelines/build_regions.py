"""Deterministic Region Discovery and Tag-Lift Labeling Pipeline for Melovia (Phase 11).

Performs:
1. Seeded KMeans (k=24, random_state=42) on fused [t | a] normalized vectors.
2. Centroid computation: center_t and center_a per region.
3. Soft top-2 regional assignments for all catalog tracks.
4. Statistical tag-lift labeling (top-3 tags by lift, zero LLM).
5. Region adjacency graph (centroid cosine similarity).
6. Integration with optional manual override file (pipelines/region_labels.yaml).
7. Bundle updates: writes regions.json, updates tracks.parquet, updates manifest.json SHA-256.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def deterministic_kmeans(
    data: np.ndarray,
    k: int = 24,
    max_iters: int = 100,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Pure NumPy deterministic KMeans clustering with k-means++ initialization.

    Args:
        data: (N, D) normalized feature matrix.
        k: Number of clusters.
        max_iters: Maximum EM iterations.
        seed: Random seed for 100% reproducibility.

    Returns:
        (centroids, cluster_assignments)
    """
    n_samples, n_features = data.shape
    rng = np.random.RandomState(seed)

    # 1. k-means++ initialization
    centroids = np.zeros((k, n_features), dtype=np.float32)
    # Pick first center randomly
    first_idx = int(rng.randint(0, n_samples))
    centroids[0] = data[first_idx]

    # Pick remaining k-1 centers with probability proportional to squared Euclidean distance
    dists = np.sum((data - centroids[0]) ** 2, axis=1)
    for c in range(1, k):
        probs = dists / np.maximum(np.sum(dists), 1e-12)
        # Cumulative distribution sampling
        cum_probs = np.cumsum(probs)
        r = rng.rand()
        next_idx = int(np.searchsorted(cum_probs, r))
        next_idx = min(next_idx, n_samples - 1)
        centroids[c] = data[next_idx]

        new_dists = np.sum((data - centroids[c]) ** 2, axis=1)
        dists = np.minimum(dists, new_dists)

    # 2. EM Iterations
    labels = np.zeros(n_samples, dtype=np.int32)
    for _ in range(max_iters):
        # Assign step (closest Euclidean distance / highest cosine similarity)
        # Using dot products for normalized data: dist = 2 - 2*(x . c)
        sims = np.dot(data, centroids.T)  # (N, k)
        new_labels = np.argmax(sims, axis=1)

        # Check convergence
        if np.array_equal(labels, new_labels):
            break
        labels = new_labels

        # Update step
        for c in range(k):
            members = data[labels == c]
            if len(members) > 0:
                c_mean = np.mean(members, axis=0)
                norm = np.linalg.norm(c_mean)
                centroids[c] = c_mean / (norm + 1e-9)
            else:
                # Re-seed empty cluster with furthest point
                furthest = int(np.argmin(np.max(sims, axis=1)))
                centroids[c] = data[furthest]

    return centroids, labels


def compute_tag_lift(
    track_tags_list: list[list[str]],
    region_assignments: np.ndarray,
    all_vocab_tags: list[str],
    k: int = 24,
) -> dict[int, list[tuple[str, float]]]:
    """Compute tag lift for each region.

    Lift(T, R) = P(T | R) / P(T)
    """
    n_total = len(track_tags_list)

    # Overall tag frequencies
    tag_total_counts: dict[str, int] = {}
    for tags in track_tags_list:
        for t in set(tags):
            tag_total_counts[t] = tag_total_counts.get(t, 0) + 1

    # Regional tag counts
    region_tag_counts: dict[int, dict[str, int]] = {r: {} for r in range(k)}
    region_sizes: dict[int, int] = {r: 0 for r in range(k)}

    for idx, r in enumerate(region_assignments):
        region_sizes[int(r)] += 1
        for t in set(track_tags_list[idx]):
            region_tag_counts[int(r)][t] = region_tag_counts[int(r)].get(t, 0) + 1

    # Compute lift
    region_lifts: dict[int, list[tuple[str, float]]] = {}
    for r in range(k):
        r_size = max(1, region_sizes[r])
        tag_lift_pairs: list[tuple[str, float]] = []

        for tag, count_in_r in region_tag_counts[r].items():
            if count_in_r < 2:  # Min occurrences filter to avoid singletons with inflated lift
                continue
            p_tag_given_r = count_in_r / r_size
            p_tag_catalog = tag_total_counts.get(tag, 1) / n_total
            lift = p_tag_given_r / (p_tag_catalog + 1e-9)
            tag_lift_pairs.append((tag, lift))

        # Sort by lift descending
        tag_lift_pairs.sort(key=lambda x: (-x[1], x[0]))
        region_lifts[r] = tag_lift_pairs

    return region_lifts


def build_regions(
    bundle_dir: str | Path,
    k: int = 24,
    override_file: str | Path | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Build discovered regions with soft assignments, lift labels, and adjacency graph."""
    bundle_path = Path(bundle_dir)
    if not bundle_path.is_dir():
        raise FileNotFoundError(f"Bundle directory does not exist: {bundle_path}")

    # 1. Load data
    vectors_t = np.load(bundle_path / "vectors_t.npy")  # (N, dim_t)
    vectors_a = np.load(bundle_path / "vectors_a.npy")  # (N, dim_a)
    tracks_table = pq.read_table(bundle_path / "tracks.parquet")
    tracks_dict = tracks_table.to_pydict()
    n_tracks = len(tracks_dict["id"])

    # Load tag vocabulary if present
    tag_vocab_file = bundle_path / "tag_vocab.json"
    tag_vocab: list[str] = []
    if tag_vocab_file.exists():
        with open(tag_vocab_file, encoding="utf-8") as f:
            v_data = json.load(f)
            tag_vocab = v_data.get("tags", [])

    # Extract or synthesize track tags
    # If tracks_table already has 'tags', use it; otherwise synthesize from tag vocabulary & taste similarity
    if "tags" in tracks_dict and any(tracks_dict["tags"]):
        track_tags_list: list[list[str]] = [
            list(t) if t is not None else [] for t in tracks_dict["tags"]
        ]
    else:
        # Synthesize tags for mock catalog tracks based on their planted region or taste vectors
        track_tags_list = []
        old_regions_file = bundle_path / "regions.json"
        old_region_tags: dict[int, list[str]] = {}
        if old_regions_file.exists():
            with open(old_regions_file, encoding="utf-8") as f:
                old_regs = json.load(f)
            for r in old_regs:
                old_region_tags[r["region_id"]] = r.get("top_tags", [])

        rng = np.random.RandomState(seed)
        old_reg_ids = tracks_dict.get("region_id", [0] * n_tracks)
        for i in range(n_tracks):
            reg = int(old_reg_ids[i])
            base_tags = list(old_region_tags.get(reg, []))
            # Pick 2-4 base tags
            n_tags = min(len(base_tags), rng.randint(2, 5))
            chosen = list(rng.choice(base_tags, size=n_tags, replace=False)) if base_tags else []
            # Add occasional genre tag from vocabulary
            if tag_vocab and rng.rand() < 0.25:
                extra_t = tag_vocab[rng.randint(0, len(tag_vocab))]
                if extra_t not in chosen:
                    chosen.append(extra_t)
            track_tags_list.append(chosen)

    # 2. Fuse vectors: concatenate [vectors_t, vectors_a] and normalize
    # For tracks with has_a=False, vectors_a is already zero
    fused = np.hstack([vectors_t, vectors_a]).astype(np.float32)
    norms = np.linalg.norm(fused, axis=1, keepdims=True)
    fused_norm = fused / np.maximum(norms, 1e-9)

    # 3. Seeded KMeans clustering
    print(f"Clustering {n_tracks} tracks into {k} regions (seed={seed})...")
    fused_centroids, primary_assignments = deterministic_kmeans(
        fused_norm, k=k, max_iters=100, seed=seed
    )

    # 4. Compute centroids center_t and center_a
    dim_t = vectors_t.shape[1]
    dim_a = vectors_a.shape[1]
    has_a_mask = np.array(tracks_dict.get("has_a", [True] * n_tracks), dtype=bool)

    centroids_t = np.zeros((k, dim_t), dtype=np.float32)
    centroids_a = np.zeros((k, dim_a), dtype=np.float32)

    for c in range(k):
        members = primary_assignments == c
        if np.any(members):
            # Taste centroid
            mean_t = np.mean(vectors_t[members], axis=0)
            norm_t = np.linalg.norm(mean_t)
            centroids_t[c] = mean_t / (norm_t + 1e-9)

            # Audio centroid (using only tracks with valid audio)
            audio_members = members & has_a_mask
            if np.any(audio_members):
                mean_a = np.mean(vectors_a[audio_members], axis=0)
                norm_a = np.linalg.norm(mean_a)
                centroids_a[c] = mean_a / (norm_a + 1e-9)
            else:
                centroids_a[c] = np.zeros(dim_a, dtype=np.float32)

    # 5. Compute soft top-2 assignments
    # Cosine similarity of all tracks to all 24 fused centroids
    sim_matrix = np.dot(fused_norm, fused_centroids.T)  # (N, k)

    region_id_primary = np.zeros(n_tracks, dtype=np.int32)
    region_id_secondary = np.zeros(n_tracks, dtype=np.int32)
    region_weight_primary = np.zeros(n_tracks, dtype=np.float32)
    region_weight_secondary = np.zeros(n_tracks, dtype=np.float32)

    for i in range(n_tracks):
        sims_i = sim_matrix[i]
        top2_idx = np.argsort(sims_i)[-2:][::-1]
        r1, r2 = int(top2_idx[0]), int(top2_idx[1])
        s1, s2 = float(sims_i[r1]), float(sims_i[r2])

        # Temperature-scaled soft weights
        tau = 0.2
        exp1 = np.exp(s1 / tau)
        exp2 = np.exp(s2 / tau)
        w1 = float(exp1 / (exp1 + exp2))
        w2 = float(1.0 - w1)

        region_id_primary[i] = r1
        region_id_secondary[i] = r2
        region_weight_primary[i] = round(w1, 3)
        region_weight_secondary[i] = round(w2, 3)

    # 6. Statistical tag-lift labeling
    print("Computing statistical tag-lift for regions...")
    region_lifts = compute_tag_lift(
        track_tags_list=track_tags_list,
        region_assignments=primary_assignments,
        all_vocab_tags=tag_vocab,
        k=k,
    )

    # 7. Adjacency graph based on taste centroid cosine similarity
    adjacency_matrix = np.dot(centroids_t, centroids_t.T)  # (k, k)

    # 8. Load manual label overrides if available
    override_dict: dict[int, dict[str, str]] = {}
    if override_file is None:
        default_override = Path(__file__).resolve().parent / "region_labels.yaml"
        if default_override.exists():
            override_file = default_override

    if override_file and Path(override_file).exists():
        import yaml

        with open(override_file, encoding="utf-8") as f:
            raw_overrides = yaml.safe_load(f)
            if isinstance(raw_overrides, dict):
                for r_key, val in raw_overrides.items():
                    try:
                        override_dict[int(r_key)] = val
                    except (ValueError, TypeError):
                        pass

    # 9. Assemble regions.json
    regions_payload: list[dict[str, Any]] = []
    for c in range(k):
        # Top-3 tags by lift
        top_lift_pairs = region_lifts.get(c, [])[:5]
        top_tags = [pair[0] for pair in top_lift_pairs[:3]]
        if not top_tags:
            top_tags = [f"region-{c}"]

        # Top adjacent regions (excluding self)
        adj_pairs = []
        for other in range(k):
            if other != c:
                adj_pairs.append({
                    "region_id": other,
                    "similarity": round(float(adjacency_matrix[c, other]), 4),
                })
        adj_pairs.sort(key=lambda x: -x["similarity"])

        # Override or auto-generate display labels
        override = override_dict.get(c, {})
        if override and "name" in override:
            name = override["name"]
            genre_focus = override.get("genre_focus", " / ".join(t.title() for t in top_tags))
            description = override.get("description", f"Musical cluster emphasizing {', '.join(top_tags)}.")
        else:
            name = " / ".join(t.title() for t in top_tags[:2])
            genre_focus = " / ".join(t.title() for t in top_tags)
            description = f"Cluster characterized by {', '.join(top_tags)} with acoustic affinity."

        regions_payload.append({
            "region_id": c,
            "name": name,
            "genre_focus": genre_focus,
            "description": description,
            "center_t": [round(float(v), 6) for v in centroids_t[c]],
            "center_a": [round(float(v), 6) for v in centroids_a[c]],
            "top_tags": top_tags,
            "adjacent_regions": adj_pairs[:6],  # Top 6 most adjacent
        })

    # 10. Write updated regions.json
    regions_file = bundle_path / "regions.json"
    with open(regions_file, "w", encoding="utf-8") as f:
        json.dump(regions_payload, f, indent=2)
    print(f"Wrote {len(regions_payload)} regions to {regions_file}")

    # 11. Update tracks.parquet with soft assignments and explicit tags
    tracks_dict["region_id"] = region_id_primary.tolist()
    tracks_dict["region_id_secondary"] = region_id_secondary.tolist()
    tracks_dict["region_weight_primary"] = region_weight_primary.tolist()
    tracks_dict["region_weight_secondary"] = region_weight_secondary.tolist()
    tracks_dict["tags"] = track_tags_list

    updated_table = pa.Table.from_pydict(tracks_dict)
    tracks_file = bundle_path / "tracks.parquet"
    pq.write_table(updated_table, tracks_file)
    print(f"Updated {tracks_file} with soft region assignments and tags.")

    # 12. Update manifest.json hashes
    manifest_file = bundle_path / "manifest.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for fname in manifest.get("files", {}):
        fpath = bundle_path / fname
        if fpath.exists():
            manifest["files"][fname] = compute_sha256(fpath)

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Updated {manifest_file} with fresh checksums.")

    return {
        "k": k,
        "bundle_path": str(bundle_path),
        "regions": regions_payload,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Melovia discovered regions and tag-lift labels.")
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "bundles" / "v1",
        help="Path to catalog bundle directory",
    )
    parser.add_argument("--k", type=int, default=24, help="Number of regions (default: 24)")
    parser.add_argument(
        "--override-file",
        type=Path,
        default=Path(__file__).resolve().parent / "region_labels.yaml",
        help="Optional manual override YAML file",
    )
    parser.add_argument("--seed", type=int, default=42, help="KMeans random seed (default: 42)")

    args = parser.parse_args()
    build_regions(
        bundle_dir=args.bundle_dir,
        k=args.k,
        override_file=args.override_file,
        seed=args.seed,
    )
