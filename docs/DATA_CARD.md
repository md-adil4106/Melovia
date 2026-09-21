# Melovia Data Card

## 1. Dataset Overview

The Melovia catalog provides dual-channel semantic and acoustic representations paired with relational metadata and interpretable musical scalars. It is distributed as an immutable, versioned, checksummed bundle (`data/bundles/<version>/`) designed for deterministic, privacy-first recommendation research and interactive discovery.

---

## 2. Data Sources & Provenance

| Source | Role in Melovia | Provenance & Extraction | License |
| :--- | :--- | :--- | :--- |
| **MusicBrainz** | Core Entities, MBIDs, Titles, Artists, Years, ISRCs, Folksonomy Tags | Extracted via MusicBrainz Database Dumps and public REST API. Recording and release-group tags aggregated with artist-level fallback. | [CC0 / ODbL 1.0](https://musicbrainz.org/doc/MusicBrainz_Database/Download) |
| **ListenBrainz** | Popularity Signals & Scrobble Frequency | Scrobble counts aggregated per recording MBID from public ListenBrainz data dumps. Normalized into logarithmic popularity percentiles ($[0.0, 100.0]$). | [CC0 1.0 Universal](https://listenbrainz.org/data/) |
| **AcousticBrainz** | Acoustic Descriptors & Essentia Features | Pre-computed low-level spectral and high-level mood/genre probability scalars extracted via Essentia 2.1. | [CC0 1.0 Universal](https://acousticbrainz.org/download) |
| **Deterministic Mock Catalog** | Deterministic Test & Local Offline Bundle | Synthesized via `fixtures/make_mock_catalog.py` ($N=3,000$ tracks, $400$ artists, $24$ planted clusters, Pareto popularity, exactly $5\%$ missing audio). | MIT (Melovia Source) |

---

## 3. Bundle Structure & File Specifications

Every versioned bundle complies with [`docs/BUNDLE_SPEC.md`](BUNDLE_SPEC.md):

```
data/bundles/v1/
├── tracks.parquet     # Relational metadata, IDs, flags, primary region assignments
├── scalars.parquet    # Interpretable musical attributes (tempo, energy, valence, etc.)
├── vectors_t.npy      # Semantic taste embeddings (N x 128, float32, L2-normalized)
├── vectors_a.npy      # Acoustic descriptor embeddings (N x 128, float32, L2-normalized)
├── layout3d.npy       # 3D visualization coordinates via PCA (N x 3, float32)
├── regions.json       # Discovered musical regions, centroids, and top tags
├── tag_vocab.json     # Controlled tag vocabulary (genres, moods, instruments)
└── manifest.json      # Cryptographic SHA-256 manifest and validation metadata
```

### Schema: `tracks.parquet`
- `track_idx` (`int64`): Zero-based matrix index.
- `id` (`string`): Melovia UUID5 identifier.
- `mbid` (`string`): MusicBrainz recording UUID.
- `title` (`string`): Recording title.
- `artist_id` (`string`): Artist UUID.
- `artist_name` (`string`): Canonical artist name.
- `year` (`int32`): Release year (1950–2026).
- `isrc` (`string`, optional): International Standard Recording Code.
- `popularity_pct` (`float32`): Popularity percentile $[0.0, 100.0]$.
- `has_a` (`bool`): True if valid acoustic descriptors are present.
- `has_t` (`bool`): True if valid semantic taste embedding is present.
- `region_id` (`int32`): Primary assigned musical region cluster.

### Schema: `scalars.parquet`
- `track_idx` (`int64`): Matrix row identifier.
- `bpm` / `tempo_bpm` (`float32`): Beats per minute $[40.0, 240.0]$.
- `tempo_norm` (`float32`): Linearly normalized tempo $[0.0, 1.0]$.
- `energy` / `energy_idx` (`float32`): Perceived acoustic drive proxy $[0.0, 1.0]$.
- `valence` / `valence_idx` (`float32`): Perceived harmonic positivity proxy $[0.0, 1.0]$.
- `danceability` (`float32`): Rhythm regularity probability $[0.0, 1.0]$.
- `acousticness` (`float32`): Acoustic timbre probability $[0.0, 1.0]$.
- `instrumentalness` (`float32`): Absence-of-vocals probability $[0.0, 1.0]$.
- `loudness_db` (`float32`): Integrated loudness in decibels $[-40.0, 0.0]$.

---

## 4. Preprocessing & Quality Invariants

1. **Missing Audio Descriptor Invariant**:
   - Tracks without AcousticBrainz data are flagged with `has_a = False`.
   - Their row in `vectors_a.npy` is **strictly zeroed** ($\mathbf{0} \in \mathbb{R}^{128}$).
   - They are tracked via boolean mask `mask_a` in memory.
   - **Zero Silent Imputation**: Melovia never replaces missing acoustic vectors with dataset means, preventing hallucinated sonic similarities.
2. **Robust Standardization & Clipping**:
   - Continuous audio features are z-score standardized and strictly clipped to $[-4.0, +4.0]$ ($4\sigma$) to neutralize recording anomalies.
3. **Controlled Vocabulary Filtering**:
   - Folksonomy tags are normalized (lowercased, punctuation standardized), mapped through a synonym dictionary, and restricted to verified genres, moods, and instrumental descriptors.

---

## 5. Known Biases & Ethical Limitations

1. **AcousticBrainz Temporal Cutoff (2022)**:
   - AcousticBrainz permanently ceased accepting crowdsourced submissions in 2022. Consequently, recordings released after 2022 have $0\%$ coverage in public acoustic dumps, requiring fallback to Plan B (local feature extraction) or semantic-only retrieval (`has_a = False`).
2. **Western & Anglophone Genre Bias**:
   - MusicBrainz and ListenBrainz tagging heavily reflects English-language pop, rock, indie, electronic, and hip-hop. Non-Western traditions (e.g., Carnatic, Gamelan, Highlife, Andean folk) have significantly sparser tags and coarser categorization.
3. **ListenBrainz Demographic Skew**:
   - ListenBrainz users are disproportionately open-source and tech-enthusiast demographics, resulting in higher representation of electronic, metal, and avant-garde genres compared to global streaming consumption.
4. **Proxy Approximation**:
   - `energy_idx` and `valence_idx` are heuristic proxies derived from algorithmic models, not subjective listener ground truth. They must be interpreted as acoustic tendencies rather than emotional certainties.
