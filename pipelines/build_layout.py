"""Deterministic 3D & 2D Catalog Layout and Quality Metrics Pipeline (Phase 12).

Performs:
1. Fuses L2-normalized vectors [vectors_t, vectors_a] (256d).
2. Computes deterministic 3D layout (3D UMAP with cosine metric if available, else PCA-3D fallback).
3. Computes deterministic 2D PCA layout for the instant canvas fallback.
4. Normalizes all coordinates into a unit cube [-1.0, 1.0].
5. Computes neighborhood preservation trustworthiness (k=15) and continuity metrics.
6. Generates a stratified render sample index (<= 15,000 points, region-balanced).
7. Saves layout3d.npy, layout2d.npy, render_sample.json,
   and updates manifest.json with fresh SHA-256 checksums.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from sklearn.decomposition import PCA
from sklearn.manifold import trustworthiness


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def normalize_to_unit_cube(arr: np.ndarray) -> np.ndarray:
    """Scale and center an (N, D) array into the unit cube [-1.0, 1.0]."""
    min_val = arr.min(axis=0)
    max_val = arr.max(axis=0)
    ranges = np.maximum(max_val - min_val, 1e-6)
    normed = 2.0 * (arr - min_val) / ranges - 1.0
    return normed.astype(np.float32)


def compute_continuity(
    high_dim: np.ndarray,
    low_dim: np.ndarray,
    n_neighbors: int = 15,
) -> float:
    """Compute neighborhood continuity (low-to-high rank preservation)."""
    # Continuity is equivalent to trustworthiness with inverted spaces
    return float(trustworthiness(low_dim, high_dim, n_neighbors=n_neighbors, metric="euclidean"))


def generate_stratified_sample(
    region_ids: list[int],
    max_points: int = 15000,
    seed: int = 42,
) -> list[int]:
    """Produce a stratified, region-balanced render sample of indices."""
    n_total = len(region_ids)
    if n_total <= max_points:
        return list(range(n_total))

    rng = np.random.RandomState(seed)
    # Group indices by region
    region_to_indices: dict[int, list[int]] = {}
    for idx, reg in enumerate(region_ids):
        region_to_indices.setdefault(reg, []).append(idx)

    sampled_indices: list[int] = []
    # Allocate sample quota proportionally per region
    for _reg, idxs in region_to_indices.items():
        quota = max(1, int(round(len(idxs) / n_total * max_points)))
        if len(idxs) <= quota:
            sampled_indices.extend(idxs)
        else:
            chosen = rng.choice(idxs, size=quota, replace=False).tolist()
            sampled_indices.extend(chosen)

    # Trim or fill to match max_points exactly if needed
    if len(sampled_indices) > max_points:
        sampled_indices = rng.choice(sampled_indices, size=max_points, replace=False).tolist()

    sampled_indices.sort()
    return sampled_indices


def build_layout(
    bundle_dir: str | Path,
    seed: int = 42,
    max_render_points: int = 15000,
) -> dict[str, Any]:
    """Build deterministic 3D and 2D layouts and update bundle artifacts."""
    bundle_path = Path(bundle_dir)
    if not bundle_path.is_dir():
        raise FileNotFoundError(f"Bundle directory does not exist: {bundle_path}")

    # 1. Load high-dimensional vectors and track metadata
    vectors_t = np.load(bundle_path / "vectors_t.npy")
    vectors_a = np.load(bundle_path / "vectors_a.npy")
    tracks_table = pq.read_table(bundle_path / "tracks.parquet")
    tracks_dict = tracks_table.to_pydict()
    n_tracks = len(tracks_dict["id"])

    # 2. Fuse vectors: [vectors_t, vectors_a] and normalize
    fused = np.hstack([vectors_t, vectors_a]).astype(np.float32)
    norms = np.linalg.norm(fused, axis=1, keepdims=True)
    fused_norm = fused / np.maximum(norms, 1e-9)

    print(f"Projecting {n_tracks} tracks into 3D and 2D coordinate spaces (seed={seed})...")

    # 3. 3D Projection (UMAP if installed, else deterministic PCA fallback)
    layout_3d: np.ndarray
    method_3d: str
    try:
        import umap  # type: ignore

        reducer_3d = umap.UMAP(
            n_components=3,
            metric="cosine",
            n_neighbors=30,
            min_dist=0.1,
            random_state=seed,
            n_jobs=1,  # Ensure single-threaded determinism
        )
        raw_3d = reducer_3d.fit_transform(fused_norm).astype(np.float32)
        method_3d = "umap-3d"
    except (ImportError, Exception) as e:
        print(f"Notice: UMAP-3D unavailable ({e}), using deterministic PCA-3D fallback.")
        pca_3d = PCA(n_components=3, random_state=seed)
        raw_3d = pca_3d.fit_transform(fused_norm).astype(np.float32)
        method_3d = "pca-3d"

    layout_3d = normalize_to_unit_cube(raw_3d)

    # 4. 2D Projection (PCA-2D for instant canvas fallback)
    pca_2d = PCA(n_components=2, random_state=seed)
    raw_2d = pca_2d.fit_transform(fused_norm).astype(np.float32)
    layout_2d = normalize_to_unit_cube(raw_2d)

    # 5. Compute Neighborhood Preservation Trustworthiness & Continuity
    print("Computing neighborhood preservation trustworthiness (k=15)...")
    eval_n = min(n_tracks, 2000)
    if n_tracks > eval_n:
        rng_eval = np.random.RandomState(seed)
        eval_idx = rng_eval.choice(n_tracks, size=eval_n, replace=False)
        tw_k15 = float(
            trustworthiness(
                fused_norm[eval_idx],
                layout_3d[eval_idx],
                n_neighbors=15,
                metric="cosine",
            )
        )
        cont_k15 = compute_continuity(
            fused_norm[eval_idx],
            layout_3d[eval_idx],
            n_neighbors=15,
        )
    else:
        tw_k15 = float(
            trustworthiness(
                fused_norm,
                layout_3d,
                n_neighbors=15,
                metric="cosine",
            )
        )
        cont_k15 = compute_continuity(
            fused_norm,
            layout_3d,
            n_neighbors=15,
        )

    print(
        f"3D Layout ({method_3d}) — Trustworthiness (k=15): {tw_k15:.4f}, "
        f"Continuity: {cont_k15:.4f}"
    )

    # 6. Stratified Render Sample
    region_col = tracks_dict.get("region_id", [0] * n_tracks)
    render_sample = generate_stratified_sample(
        region_ids=region_col,
        max_points=max_render_points,
        seed=seed,
    )

    # 7. Save bundle artifacts
    layout3d_file = bundle_path / "layout3d.npy"
    layout2d_file = bundle_path / "layout2d.npy"
    sample_file = bundle_path / "render_sample.json"

    np.save(layout3d_file, layout_3d)
    np.save(layout2d_file, layout_2d)

    sample_payload = {
        "sample_count": len(render_sample),
        "total_catalog_tracks": n_tracks,
        "sample_indices": render_sample,
    }
    with open(sample_file, "w", encoding="utf-8") as f:
        json.dump(sample_payload, f, indent=2)

    # 8. Update manifest.json with layout metrics and fresh hashes
    manifest_file = bundle_path / "manifest.json"
    with open(manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)

    files_dict = manifest.get("files", {})
    files_dict["layout3d.npy"] = compute_sha256(layout3d_file)
    files_dict["layout2d.npy"] = compute_sha256(layout2d_file)
    files_dict["render_sample.json"] = compute_sha256(sample_file)

    layout_metrics = {
        "trustworthiness_k15": round(tw_k15, 4),
        "continuity_k15": round(cont_k15, 4),
        "method_3d": method_3d,
        "method_2d": "pca-2d",
        "sample_count": len(render_sample),
    }
    manifest["layout_metrics"] = layout_metrics
    manifest["files"] = files_dict

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Updated bundle manifest at: {manifest_file}")
    return layout_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build 3D & 2D catalog layouts for Melovia.")
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "bundles" / "v1",
        help="Path to catalog bundle directory",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument(
        "--max-render-points",
        type=int,
        default=15000,
        help="Maximum points in stratified render sample (default: 15,000)",
    )
    args = parser.parse_args()
    build_layout(args.bundle_dir, seed=args.seed, max_render_points=args.max_render_points)
