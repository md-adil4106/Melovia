# Melovia Vector Bundle Specification (v1)

This specification defines the directory structure, file formats, array layout, checksum validation, and invariants for Melovia vector catalog bundles located at `data/bundles/<version>/`.

---

## Directory Layout

```
data/bundles/<version>/
├── manifest.json       # Version, counts, dimensions, file SHA-256 hashes
├── tracks.parquet      # Relational metadata indexed by integer track_idx
├── vectors_t.npy       # L2-normalized float32 taste/semantic vectors (N x dim_t)
├── vectors_a.npy       # L2-normalized float32 acoustic audio vectors (N x dim_a)
├── scalars.parquet     # Numeric audio & popularity attributes aligned with track_idx
├── tag_vocab.json      # Controlled tag vocabulary (tag -> index, list of tags)
├── regions.json        # Planted musical clusters / genre regions (metadata & centroids)
└── layout3d.npy        # Optional (N x 3) float32 coordinates for client 3D visualization
```

---

## File Specifications & Schemas

### 1. `manifest.json`
Contains integrity checksums and bundle dimension metadata.
```json
{
  "version": "v1",
  "created_at": "2026-09-19T12:00:00Z",
  "plan": "mock",
  "track_count": 3000,
  "dim_t": 128,
  "dim_a": 128,
  "files": {
    "tracks.parquet": "<sha256_hex>",
    "vectors_t.npy": "<sha256_hex>",
    "vectors_a.npy": "<sha256_hex>",
    "scalars.parquet": "<sha256_hex>",
    "tag_vocab.json": "<sha256_hex>",
    "regions.json": "<sha256_hex>",
    "layout3d.npy": "<sha256_hex>"
  }
}
```

### 2. `tracks.parquet`
Table with exactly $N$ rows, sorted contiguously by `track_idx` from $0$ to $N - 1$:
- `track_idx` (int64, primary contiguous index)
- `id` (string, unique Melovia track UUID)
- `mbid` (string, nullable MusicBrainz recording ID)
- `title` (string, track title)
- `artist_id` (string, artist UUID)
- `artist_name` (string, artist display name)
- `year` (int32, release year)
- `isrcs` (list of strings, ISRC codes)
- `popularity_pct` (float32, 0.0 to 100.0)
- `has_a` (bool, whether valid audio embedding exists in `vectors_a.npy`)
- `has_t` (bool, whether valid taste embedding exists in `vectors_t.npy`)
- `region_id` (int32, cluster region index 0–11)

### 3. `vectors_t.npy` (Taste / Semantic Embeddings)
- **Data Type**: `float32` (little-endian)
- **Shape**: `(N, dim_t)` where $dim_t = 128$
- **Invariant**: Row $i$ corresponds strictly to `track_idx == i`.
- **Normalization**: Each row vector $v$ satisfies $\|v\|_2 = 1.0 \pm 10^{-5}$.

### 4. `vectors_a.npy` (Acoustic Audio Embeddings)
- **Data Type**: `float32` (little-endian)
- **Shape**: `(N, dim_a)` where $dim_a = 128$
- **Invariant**: Row $i$ corresponds strictly to `track_idx == i`.
- **Missing Channel Handling**: For tracks where `has_a == False`, the row contains zeros, and `CatalogStore.mask_a[i] == False`.
- **Normalization**: For rows where `has_a == True`, $\|v\|_2 = 1.0 \pm 10^{-5}$.

### 5. `scalars.parquet`
Table with exactly $N$ rows, indexed by `track_idx`:
- `tempo_bpm` (float32)
- `energy` (float32, 0.0 to 1.0)
- `valence` (float32, 0.0 to 1.0)
- `danceability` (float32, 0.0 to 1.0)
- `acousticness` (float32, 0.0 to 1.0)
- `instrumentalness` (float32, 0.0 to 1.0)
- `loudness_db` (float32)

### 6. `tag_vocab.json`
Controlled tag vocabulary mapping:
```json
{
  "tags": ["ambient", "synthwave", "post-punk", "..."],
  "tag_to_idx": {"ambient": 0, "synthwave": 1, ...},
  "tag_categories": {"ambient": "genre", "energetic": "mood", ...}
}
```

### 7. `regions.json`
Pre-computed cluster regions for steerability:
```json
[
  {
    "region_id": 0,
    "name": "Neon Nocturne",
    "genre_focus": "Synthwave / Dark Electro",
    "description": "Driving synthesized arpeggios with nostalgic 80s aesthetics.",
    "center_t": [0.023, -0.145, ...],
    "center_a": [0.112, 0.089, ...],
    "top_tags": ["synthwave", "retrowave", "electronic", "nostalgic"]
  }
]
```

### 8. `layout3d.npy`
- **Data Type**: `float32`
- **Shape**: `(N, 3)`
- **Constraint**: Strict visualization only. Recommendation decisions must **never** compute distances on `layout3d.npy`.

---

## CatalogStore Invariants

1. **Checksum Verification**: On `CatalogStore.load(bundle_path)`, every file in `manifest.json["files"]` is hashed with SHA-256. If any file hash mismatches, a `CatalogCorruptError` is raised and the server halts startup.
2. **Memory-Mapped Arrays**: Vector arrays are loaded with `mmap_mode="r"` to minimize resident memory overhead and avoid copying large float arrays.
3. **Index Bi-directionality**:
   - `store.get_idx(track_id) -> int`
   - `store.get_id(track_idx) -> str`
4. **Channel Masks**:
   - `store.mask_a`: 1D boolean numpy array of length $N$.
   - `store.mask_t`: 1D boolean numpy array of length $N$.
