"""CatalogStore: Immutable Vector Catalog Loader and Store.

Architecture Constraints:
- Pure Python (zero imports from FastAPI, Starlette, or SQLAlchemy).
- Enforces SHA-256 checksum validation for all bundle files.
- Uses memory-mapped arrays for high-dimensional vectors.
- Exposes bidirectional ID <-> Index lookups and missing-channel masks.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow.parquet as pq


class CatalogError(Exception):
    """Base exception for catalog-related failures."""


class CatalogNotFoundError(CatalogError):
    """Raised when bundle directory or required files are missing."""


class CatalogCorruptError(CatalogError):
    """Raised when a bundle file fails SHA-256 checksum validation."""


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute hex-encoded SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass(frozen=True)
class CatalogManifest:
    version: str
    created_at: str
    plan: str
    track_count: int
    dim_t: int
    dim_a: int
    files: dict[str, str]


class CatalogStore:
    """In-memory index and memory-mapped array holder for a catalog version bundle."""

    def __init__(
        self,
        bundle_path: Path,
        manifest: CatalogManifest,
        track_ids: list[str],
        tracks_metadata: dict[str, list[Any]],
        vectors_t: npt.NDArray[np.float32],
        vectors_a: npt.NDArray[np.float32],
        mask_t: npt.NDArray[np.bool_],
        mask_a: npt.NDArray[np.bool_],
        scalars: dict[str, list[Any]] | None = None,
        tag_vocab: dict[str, Any] | None = None,
        regions: list[dict[str, Any]] | None = None,
        layout3d: npt.NDArray[np.float32] | None = None,
    ) -> None:
        self.bundle_path = bundle_path
        self.manifest = manifest
        self.track_ids = track_ids
        self._tracks_metadata = tracks_metadata
        self.vectors_t = vectors_t
        self.vectors_a = vectors_a
        self.mask_t = mask_t
        self.mask_a = mask_a
        self.scalars = scalars or {}
        self.tag_vocab = tag_vocab or {}
        self.regions = regions or []
        self.layout3d = layout3d

        # Bidirectional index mappings
        self._id_to_idx: dict[str, int] = {tid: idx for idx, tid in enumerate(track_ids)}
        self._idx_to_id: dict[int, str] = dict(enumerate(track_ids))

        # Index mapping for MBIDs if present
        self._mbid_to_idx: dict[str, int] = {}
        if "mbid" in self._tracks_metadata:
            for idx, mbid_val in enumerate(self._tracks_metadata["mbid"]):
                if mbid_val:
                    self._mbid_to_idx[str(mbid_val).lower()] = idx

    @classmethod
    def load(cls, bundle_path_str: str | Path) -> "CatalogStore":
        """Load and validate an immutable catalog bundle from disk."""
        path = Path(bundle_path_str)
        if not path.is_dir():
            raise CatalogNotFoundError(f"Catalog bundle directory not found at: {path}")

        manifest_file = path / "manifest.json"
        if not manifest_file.exists():
            raise CatalogNotFoundError(f"Missing manifest.json in bundle at: {path}")

        try:
            with open(manifest_file, encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as e:
            raise CatalogCorruptError(f"Failed to parse manifest.json: {e}") from e

        required_manifest_keys = {"version", "track_count", "dim_t", "dim_a", "files"}
        if not required_manifest_keys.issubset(manifest_data.keys()):
            missing = required_manifest_keys - set(manifest_data.keys())
            raise CatalogCorruptError(f"manifest.json missing required keys: {missing}")

        manifest = CatalogManifest(
            version=manifest_data["version"],
            created_at=manifest_data.get("created_at", ""),
            plan=manifest_data.get("plan", "unknown"),
            track_count=int(manifest_data["track_count"]),
            dim_t=int(manifest_data["dim_t"]),
            dim_a=int(manifest_data["dim_a"]),
            files=dict(manifest_data["files"]),
        )

        # 1. Checksum validation: Every file in manifest must match expected hash
        for rel_filename, expected_hash in manifest.files.items():
            target_file = path / rel_filename
            if not target_file.exists():
                raise CatalogCorruptError(
                    f"Bundle file declared in manifest is missing: {rel_filename}"
                )
            actual_hash = compute_sha256(target_file)
            if actual_hash.lower() != expected_hash.lower():
                raise CatalogCorruptError(
                    f"Checksum mismatch for '{rel_filename}': "
                    f"expected {expected_hash}, calculated {actual_hash}"
                )

        # 2. Load metadata from tracks.parquet
        tracks_file = path / "tracks.parquet"
        tracks_table = pq.read_table(tracks_file)
        tracks_pydict: dict[str, list[Any]] = tracks_table.to_pydict()

        track_ids: list[str] = [str(x) for x in tracks_pydict["id"]]
        n_tracks = len(track_ids)
        if n_tracks != manifest.track_count:
            raise CatalogCorruptError(
                f"tracks.parquet row count ({n_tracks}) mismatches "
                f"manifest count ({manifest.track_count})"
            )

        # 3. Load vectors as read-only memory maps
        vectors_t_file = path / "vectors_t.npy"
        vectors_a_file = path / "vectors_a.npy"

        vectors_t = np.load(vectors_t_file, mmap_mode="r")
        vectors_a = np.load(vectors_a_file, mmap_mode="r")

        if vectors_t.shape != (manifest.track_count, manifest.dim_t):
            raise CatalogCorruptError(
                f"vectors_t shape {vectors_t.shape} != "
                f"expected ({manifest.track_count}, {manifest.dim_t})"
            )
        if vectors_a.shape != (manifest.track_count, manifest.dim_a):
            raise CatalogCorruptError(
                f"vectors_a shape {vectors_a.shape} != "
                f"expected ({manifest.track_count}, {manifest.dim_a})"
            )

        # 4. Build channel masks
        mask_t = np.array(tracks_pydict.get("has_t", [True] * n_tracks), dtype=bool)
        mask_a = np.array(tracks_pydict.get("has_a", [True] * n_tracks), dtype=bool)

        # 5. Optional files
        scalars: dict[str, list[Any]] | None = None
        scalars_file = path / "scalars.parquet"
        if scalars_file.exists():
            scalars = pq.read_table(scalars_file).to_pydict()

        tag_vocab: dict[str, Any] | None = None
        tag_vocab_file = path / "tag_vocab.json"
        if tag_vocab_file.exists():
            with open(tag_vocab_file, encoding="utf-8") as f:
                tag_vocab = json.load(f)

        regions: list[dict[str, Any]] | None = None
        regions_file = path / "regions.json"
        if regions_file.exists():
            with open(regions_file, encoding="utf-8") as f:
                regions = json.load(f)

        layout3d: npt.NDArray[np.float32] | None = None
        layout3d_file = path / "layout3d.npy"
        if layout3d_file.exists():
            layout3d = np.load(layout3d_file, mmap_mode="r")

        return cls(
            bundle_path=path,
            manifest=manifest,
            track_ids=track_ids,
            tracks_metadata=tracks_pydict,
            vectors_t=vectors_t,
            vectors_a=vectors_a,
            mask_t=mask_t,
            mask_a=mask_a,
            scalars=scalars,
            tag_vocab=tag_vocab,
            regions=regions,
            layout3d=layout3d,
        )

    @property
    def track_count(self) -> int:
        return len(self.track_ids)

    def get_idx(self, track_id: str) -> int:
        """Return integer row index for a track ID."""
        try:
            return self._id_to_idx[track_id]
        except KeyError:
            raise KeyError(f"Track ID '{track_id}' not found in catalog") from None

    def get_id(self, track_idx: int) -> str:
        """Return track ID string for an integer row index."""
        try:
            return self._idx_to_id[track_idx]
        except KeyError:
            raise IndexError(
                f"Track index {track_idx} out of range [0, {self.track_count})"
            ) from None

    def contains_id(self, track_id: str) -> bool:
        return track_id in self._id_to_idx

    def contains_mbid(self, mbid: str) -> bool:
        """Check if recording MBID or track ID is present in catalog."""
        norm = mbid.lower()
        return norm in self._mbid_to_idx or norm in self._id_to_idx

    def get_idx_by_mbid(self, mbid: str) -> int:
        """Return integer row index for an MBID or track ID."""
        norm = mbid.lower()
        if norm in self._mbid_to_idx:
            return self._mbid_to_idx[norm]
        if norm in self._id_to_idx:
            return self._id_to_idx[norm]
        raise KeyError(f"MBID '{mbid}' not found in catalog")

    def get_track_dict(self, track_idx_or_id: int | str) -> dict[str, Any]:
        """Return full metadata dictionary for a track."""
        idx = track_idx_or_id if isinstance(track_idx_or_id, int) else self.get_idx(track_idx_or_id)
        record: dict[str, Any] = {}
        for col_name, col_values in self._tracks_metadata.items():
            record[col_name] = col_values[idx]

        # Attach scalar attributes if available
        if self.scalars:
            record["scalars"] = {
                col_name: col_values[idx] for col_name, col_values in self.scalars.items()
            }
        return record

    def search_tracks(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Case-insensitive search on title and artist, ranked by relevance and popularity."""
        q_lower = query.strip().lower()
        if not q_lower:
            return []

        matches: list[tuple[float, int]] = []
        titles = self._tracks_metadata.get("title", [])
        artists = self._tracks_metadata.get("artist_name", [])
        popularities = self._tracks_metadata.get("popularity_pct", [50.0] * self.track_count)

        for idx in range(self.track_count):
            title = str(titles[idx]).lower()
            artist = str(artists[idx]).lower()
            pop = float(popularities[idx])

            score = 0.0
            if title == q_lower:
                score += 100.0
            elif title.startswith(q_lower):
                score += 60.0
            elif q_lower in title:
                score += 40.0

            if artist == q_lower:
                score += 50.0
            elif artist.startswith(q_lower):
                score += 30.0
            elif q_lower in artist:
                score += 20.0

            if score > 0.0:
                # Add small popularity boost (0 to 10 points)
                total_score = score + (pop * 0.1)
                matches.append((total_score, idx))

        matches.sort(key=lambda item: item[0], reverse=True)
        top_indices = [idx for _, idx in matches[:limit]]
        return [self.get_track_dict(idx) for idx in top_indices]
