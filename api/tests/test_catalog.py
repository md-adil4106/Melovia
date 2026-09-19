"""Unit and determinism tests for CatalogStore and vector bundle loader."""

import shutil
from pathlib import Path

import numpy as np
import pytest

from app.recsys.catalog import (
    CatalogCorruptError,
    CatalogNotFoundError,
    CatalogStore,
)


@pytest.fixture
def bundle_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent.parent
    path = repo_root / "data" / "bundles" / "v1"
    if not path.exists():
        pytest.fail(f"Bundle directory not found at {path}. Run make make-mock first.")
    return path


def test_catalog_load_valid_bundle(bundle_path: Path) -> None:
    """CatalogStore must successfully load valid mock bundle and verify all hashes."""
    store = CatalogStore.load(bundle_path)

    assert store.manifest.version == "v1"
    assert store.manifest.plan in ("mock", "real")
    assert store.track_count > 0
    assert store.manifest.dim_t == 128
    assert store.manifest.dim_a > 0

    # Shape and mmap verification
    assert store.vectors_t.shape == (store.track_count, store.manifest.dim_t)
    assert store.vectors_a.shape == (store.track_count, store.manifest.dim_a)
    assert store.vectors_t.dtype == np.float32
    assert store.vectors_a.dtype == np.float32

    # L2-normalization invariant for taste vectors
    norms_t = np.linalg.norm(store.vectors_t, axis=1)
    np.testing.assert_allclose(norms_t, 1.0, atol=1e-4)

    # Missing channel a invariant
    assert np.any(~store.mask_a)  # Invariant: missing audio is detected and masked
    assert np.all(store.mask_t)  # Taste channel is 100% available

    # Audio vectors for missing tracks must be all zeros
    zero_audio_indices = np.where(~store.mask_a)[0]
    if len(zero_audio_indices) > 0:
        assert np.all(store.vectors_a[zero_audio_indices] == 0.0)

    # Audio vectors for available tracks must be L2-normalized
    active_audio_indices = np.where(store.mask_a)[0]
    if len(active_audio_indices) > 0:
        norms_a = np.linalg.norm(store.vectors_a[active_audio_indices], axis=1)
        np.testing.assert_allclose(norms_a, 1.0, atol=1e-4)


def test_catalog_bidirectional_indexes(bundle_path: Path) -> None:
    """CatalogStore must support fast bidirectional ID <-> index lookups."""
    store = CatalogStore.load(bundle_path)

    track_id_0 = store.get_id(0)
    assert isinstance(track_id_0, str)
    assert store.get_idx(track_id_0) == 0
    assert store.contains_id(track_id_0) is True

    last_idx = store.track_count - 1
    last_id = store.get_id(last_idx)
    assert store.get_idx(last_id) == last_idx
    assert store.contains_id(last_id) is True

    # Error handling
    with pytest.raises(KeyError):
        store.get_idx("non-existent-track-id")

    with pytest.raises(IndexError):
        store.get_id(999999)

    assert store.contains_id("non-existent-track-id") is False


def test_catalog_metadata_and_search(bundle_path: Path) -> None:
    """CatalogStore metadata access and fast text search."""
    store = CatalogStore.load(bundle_path)

    # Get track dict by index and by ID
    rec_0 = store.get_track_dict(0)
    assert rec_0["track_idx"] == 0
    assert "title" in rec_0
    assert "artist_name" in rec_0
    assert "scalars" in rec_0

    rec_by_id = store.get_track_dict(rec_0["id"])
    assert rec_by_id["id"] == rec_0["id"]

    # Search tracks using keyword from catalog
    first_title = store.get_track_dict(0)["title"]
    keyword = first_title.split()[0]
    results = store.search_tracks(keyword, limit=5)
    assert len(results) > 0
    assert len(results) <= 5


def test_catalog_checksum_failure_fails_fast(bundle_path: Path, tmp_path: Path) -> None:
    """Corrupted file in catalog bundle must raise CatalogCorruptError."""
    # Copy bundle to tmp_path
    corrupt_bundle = tmp_path / "corrupt_bundle"
    shutil.copytree(bundle_path, corrupt_bundle)

    # Corrupt a file (append a single byte to tracks.parquet)
    tracks_file = corrupt_bundle / "tracks.parquet"
    with open(tracks_file, "ab") as f:
        f.write(b"corruption")

    # Loading should immediately raise CatalogCorruptError
    with pytest.raises(CatalogCorruptError) as exc_info:
        CatalogStore.load(corrupt_bundle)

    assert "Checksum mismatch" in str(exc_info.value) or "tracks.parquet" in str(exc_info.value)


def test_catalog_missing_manifest_raises_not_found(tmp_path: Path) -> None:
    """Catalog bundle without manifest must raise CatalogNotFoundError."""
    empty_dir = tmp_path / "empty_bundle"
    empty_dir.mkdir()

    with pytest.raises(CatalogNotFoundError):
        CatalogStore.load(empty_dir)


def test_catalog_corrupt_manifest_json(bundle_path: Path, tmp_path: Path) -> None:
    """Malformed manifest.json must raise CatalogCorruptError."""
    corrupt_bundle = tmp_path / "corrupt_manifest_bundle"
    shutil.copytree(bundle_path, corrupt_bundle)

    manifest_file = corrupt_bundle / "manifest.json"
    with open(manifest_file, "w") as f:
        f.write("{invalid_json: true,")

    with pytest.raises(CatalogCorruptError):
        CatalogStore.load(corrupt_bundle)
