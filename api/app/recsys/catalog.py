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
    layout_metrics: dict[str, Any] | None = None


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
        layout2d: npt.NDArray[np.float32] | None = None,
        render_sample: list[int] | None = None,
    ) -> None:
        self.bundle_path = bundle_path
        self.manifest = manifest
        self.track_ids = list(track_ids)
        self._tracks_metadata = {k: list(v) for k, v in tracks_metadata.items()}
        self.vectors_t = np.array(vectors_t, dtype=np.float32, copy=True)
        self.vectors_a = np.array(vectors_a, dtype=np.float32, copy=True)
        self.mask_t = np.array(mask_t, dtype=bool, copy=True)
        self.mask_a = np.array(mask_a, dtype=bool, copy=True)
        self.scalars = {k: list(v) for k, v in (scalars or {}).items()}
        self.tag_vocab = tag_vocab or {}
        self.regions = regions or []
        self.layout3d = layout3d
        self.layout2d = layout2d
        self.render_sample = render_sample

        for opt_col in ("artwork_url", "preview_url", "album_name"):
            if opt_col not in self._tracks_metadata:
                self._tracks_metadata[opt_col] = [None] * len(self.track_ids)

        # Bidirectional index mappings
        self._id_to_idx: dict[str, int] = {tid: idx for idx, tid in enumerate(self.track_ids)}
        self._idx_to_id: dict[int, str] = dict(enumerate(self.track_ids))

        # Dynamic external tracks registry
        self._dynamic_tracks: dict[str, dict[str, Any]] = {}
        self._dynamic_vectors_t: dict[str, npt.NDArray[np.float32]] = {}

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
            layout_metrics=manifest_data.get("layout_metrics"),
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

        layout2d: npt.NDArray[np.float32] | None = None
        layout2d_file = path / "layout2d.npy"
        if layout2d_file.exists():
            layout2d = np.load(layout2d_file, mmap_mode="r")

        render_sample: list[int] | None = None
        sample_file = path / "render_sample.json"
        if sample_file.exists():
            with open(sample_file, encoding="utf-8") as f:
                s_data = json.load(f)
                render_sample = s_data.get("sample_indices")

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
            layout2d=layout2d,
            render_sample=render_sample,
        )

    @property
    def track_count(self) -> int:
        return len(self.track_ids)

    @property
    def dim_t(self) -> int:
        return self.manifest.dim_t

    @property
    def dim_a(self) -> int:
        return self.manifest.dim_a

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
        return track_id in self._id_to_idx or track_id in self._dynamic_tracks

    def has_idx(self, track_id: str) -> bool:
        """Check if track ID exists as a physical row index in the catalog bundle matrix."""
        return track_id in self._id_to_idx

    def get_vector_t(self, track_id: str) -> npt.NDArray[np.float32]:
        """Return 128-d semantic vector t for any known catalog or dynamic track."""
        if track_id in self._id_to_idx:
            return np.asarray(self.vectors_t[self._id_to_idx[track_id]], dtype=np.float32)
        if track_id in self._dynamic_vectors_t:
            return np.asarray(self._dynamic_vectors_t[track_id], dtype=np.float32)
        raise KeyError(f"Track ID '{track_id}' not found in catalog or dynamic tracks")

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

    def register_dynamic_track(
        self,
        raw_track: dict[str, Any],
        vector_t: npt.NDArray[np.float32] | None = None,
    ) -> str:
        """Register a dynamic external track into the in-memory catalog index."""
        track_id = str(raw_track["id"])
        if track_id in self._id_to_idx:
            idx = self._id_to_idx[track_id]
            existing_dict = self._dynamic_tracks.get(track_id)
            if existing_dict is not None:
                for k in ("artwork_url", "preview_url", "album_name"):
                    if not existing_dict.get(k) and raw_track.get(k):
                        existing_dict[k] = raw_track[k]
                        if k in self._tracks_metadata and idx < len(self._tracks_metadata[k]):
                            self._tracks_metadata[k][idx] = raw_track[k]
            return track_id

        if vector_t is None:
            # Generate a semantic vector using tag facets or title/artist hash projection
            tags = list(raw_track.get("tags") or [])
            tag_vectors: list[npt.NDArray[np.float32]] = []
            for t in tags:
                tag_str = str(t).lower().strip()
                fv = self.get_tag_facet_vector(tag_str)
                # Map rap/urban/hip-hop/rap to hip-hop if 0 norm
                if np.linalg.norm(fv) <= 1e-6 and any(
                    sub in tag_str for sub in ("rap", "urban", "hip-hop", "hip hop")
                ):
                    fv = self.get_tag_facet_vector("hip-hop")
                if np.linalg.norm(fv) > 1e-6:
                    tag_vectors.append(fv)

            title_str = str(raw_track.get("title", ""))
            artist_str = str(raw_track.get("artist_name", ""))
            track_seed_str = f"{track_id} {title_str} {artist_str}"
            h_int = int(hashlib.md5(track_seed_str.lower().encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(h_int % (2**31))
            track_jitter = rng.normal(0.0, 1.0, size=self.dim_t).astype(np.float32)
            track_jitter_norm = track_jitter / (float(np.linalg.norm(track_jitter)) + 1e-12)

            if tag_vectors:
                mean_v = np.mean(tag_vectors, axis=0)
                norm = float(np.linalg.norm(mean_v))
                genre_v = (
                    np.asarray(mean_v / norm, dtype=np.float32)
                    if norm > 1e-6
                    else np.zeros(self.dim_t, dtype=np.float32)
                )
                combined = 0.83 * genre_v + 0.55 * track_jitter_norm
                norm_comb = float(np.linalg.norm(combined))
                vector_t = (
                    np.asarray(combined / norm_comb, dtype=np.float32)
                    if norm_comb > 1e-6
                    else genre_v
                )
            else:
                vector_t = np.asarray(track_jitter_norm, dtype=np.float32)

        vec_t = np.asarray(vector_t, dtype=np.float32)

        # 1. Append to index arrays
        new_idx = len(self.track_ids)
        self.track_ids.append(track_id)
        self._id_to_idx[track_id] = new_idx
        self._idx_to_id[new_idx] = track_id

        # 2. Append to vector matrices
        self.vectors_t = np.vstack([self.vectors_t, vec_t.reshape(1, self.dim_t)])
        self.vectors_a = np.vstack([self.vectors_a, np.zeros((1, self.dim_a), dtype=np.float32)])
        self.mask_t = np.append(self.mask_t, True)
        self.mask_a = np.append(self.mask_a, False)

        # 3. Append to metadata columns
        meta = self._tracks_metadata
        for col_name in meta:
            if col_name == "id":
                meta[col_name].append(track_id)
            elif col_name == "track_idx":
                meta[col_name].append(new_idx)
            elif col_name == "title":
                meta[col_name].append(str(raw_track.get("title", "")))
            elif col_name == "artist_name":
                meta[col_name].append(str(raw_track.get("artist_name", "")))
            elif col_name == "artist_id":
                meta[col_name].append(str(raw_track.get("artist_id", "")))
            elif col_name == "year":
                meta[col_name].append(raw_track.get("year"))
            elif col_name == "popularity_pct":
                meta[col_name].append(float(raw_track.get("popularity_pct", 75.0)))
            elif col_name == "has_a":
                meta[col_name].append(False)
            elif col_name == "has_t":
                meta[col_name].append(True)
            elif col_name == "tags":
                meta[col_name].append(list(raw_track.get("tags") or []))
            elif col_name == "artwork_url":
                meta[col_name].append(raw_track.get("artwork_url"))
            elif col_name == "preview_url":
                meta[col_name].append(raw_track.get("preview_url"))
            elif col_name == "album_name":
                meta[col_name].append(raw_track.get("album_name"))
            else:
                meta[col_name].append(raw_track.get(col_name))

        # 4. Append to scalar columns
        raw_scalars = raw_track.get("scalars") or {}
        for s_key in self.scalars:
            v = raw_scalars.get(s_key, 0.5)
            self.scalars[s_key].append(float(v) if v is not None else 0.5)

        # 5. Store in dynamic registry with assigned track_idx
        track_dict = dict(raw_track)
        track_dict["track_idx"] = new_idx
        self._dynamic_tracks[track_id] = track_dict
        self._dynamic_vectors_t[track_id] = vec_t
        return track_id

    def get_dynamic_vector_t(self, track_id: str) -> npt.NDArray[np.float32] | None:
        """Retrieve dynamic vector t for an external track."""
        return self._dynamic_vectors_t.get(track_id)

    def get_track_dict(self, track_idx_or_id: int | str) -> dict[str, Any]:
        """Return full metadata dictionary for a track."""
        if isinstance(track_idx_or_id, str) and track_idx_or_id in self._dynamic_tracks:
            return dict(self._dynamic_tracks[track_idx_or_id])

        idx = track_idx_or_id if isinstance(track_idx_or_id, int) else self.get_idx(track_idx_or_id)
        record: dict[str, Any] = {}
        for col_name, col_values in self._tracks_metadata.items():
            if idx < len(col_values):
                record[col_name] = col_values[idx]
            else:
                record[col_name] = None
        record["track_idx"] = idx

        # Attach scalar attributes if available
        if self.scalars:
            record["scalars"] = {
                col_name: col_values[idx]
                for col_name, col_values in self.scalars.items()
                if idx < len(col_values)
            }

        # If dynamic track has extra fields (artwork_url, preview_url), merge them
        tid = self.get_id(idx)
        if tid in self._dynamic_tracks:
            record.update(self._dynamic_tracks[tid])

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

    def get_tag_facet_vector(self, tag: str) -> npt.NDArray[np.float32]:
        """Return 128-d unit facet vector for a tag from tag_vocab or mean track vectors."""
        tag_lower = tag.strip().lower()

        # 1. Direct lookup from precomputed facet_vectors in tag_vocab
        cached_vectors = self.tag_vocab.get("facet_vectors", {})
        if tag_lower in cached_vectors:
            vec = np.array(cached_vectors[tag_lower], dtype=np.float32)
            norm = float(np.linalg.norm(vec))
            if norm > 1e-12:
                return np.asarray(vec / norm, dtype=np.float32)
            return vec

        # 2. On-the-fly mean of t-vectors across tracks carrying this tag
        matching_indices: list[int] = []
        tags_col = self._tracks_metadata.get("tags", [])
        for idx in range(min(self.track_count, len(tags_col))):
            track_tags = tags_col[idx] or []
            tag_names: list[str] = []
            for t_item in track_tags:
                if isinstance(t_item, str):
                    tag_names.append(t_item.lower())
                elif isinstance(t_item, dict) and "name" in t_item:
                    tag_names.append(str(t_item["name"]).lower())
                elif hasattr(t_item, "name"):
                    tag_names.append(str(t_item.name).lower())

            if tag_lower in tag_names:
                matching_indices.append(idx)

        if matching_indices:
            sub_vecs = self.vectors_t[matching_indices]
            mean_vec = np.mean(sub_vecs, axis=0)
            norm = float(np.linalg.norm(mean_vec))
            if norm > 1e-12:
                mean_vec = mean_vec / norm
            return np.asarray(mean_vec, dtype=np.float32)

        # 3. Fallback: zero vector
        return np.zeros(self.dim_t, dtype=np.float32)
