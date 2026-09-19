# Melovia Machine Learning & Representation Design

This document specifies the representation architecture, feature extraction pipelines, mathematical transformations, proxy definitions, and steerability mechanics for the Melovia vector catalog.

---

## 1. Architectural Philosophy: Dual-Channel Representations

Music discovery engines often collapse all aspects of a track into a single high-dimensional embedding. This creates an unsteerable "black box" where acoustic characteristics (e.g. tempo, percussion timbre, harmonic distortion) are tangled with cultural, semantic, and contextual metadata (e.g. genres, eras, scenes, lyrics).

Melovia explicitly decomposes tracks into **two orthogonal channels**:

1. **Semantic Taste Channel ($t$)**:
   - Captures contextual meaning, subgenre nuances, artistic scenes, and era associations.
   - Grounded in weighted folksonomy tags, genre ontologies, and artist descriptors.
   - Vector space: $\mathbf{v}_t \in \mathbb{R}^{128}$ with unit L2 norm ($\|\mathbf{v}_t\|_2 = 1.0$).
2. **Audio Descriptor Channel ($a$)**:
   - Captures low-level and high-level acoustic, rhythmic, and timbral properties computed directly from track audio analysis (AcousticBrainz / Essentia).
   - Vector space: $\mathbf{v}_a \in \mathbb{R}^{K}$ ($K \le 64$) with unit L2 norm ($\|\mathbf{v}_a\|_2 = 1.0$).
   - **Missing Audio Invariant**: Tracks lacking audio analysis have `has_a = False`, strictly zero vector rows $\mathbf{v}_a = \mathbf{0}$, and a boolean mask `CatalogStore.mask_a[i] == False`. Melovia never performs silent imputation on audio descriptors.

---

## 2. Channel $t$: Semantic Taste Embeddings

### 2.1 Text Templating Pipeline
Folksonomy tags from MusicBrainz and ListenBrainz are cleaned, canonicalized through a synonym dictionary, and structured into a weighted semantic prompt template:

```
genres: {genres}; tags: {tags}; era: {era}; artist tags: {artist_tags}
```

- **Tag Sorting**: Tags within each slot are sorted strictly in descending order of weight/confidence.
- **Synonym Merging**: Standardizes variants (e.g. `synthpop` and `synth pop` $\to$ `synth-pop`; `hiphop` and `rap` $\to$ `hip-hop`; `lofi` $\to$ `lo-fi`).
- **Fallback**: If a track has no community tags, the pipeline falls back to `title: {title}; artist: {artist_name}; era: {era}` to preserve basic identity clustering.

### 2.2 Embedding Model & Dimensionality Reduction
- **Base Model**: `all-MiniLM-L6-v2` (Sentence-Transformers), producing 384-dimensional dense semantic vectors.
- **Dimensionality Reduction**: Principal Component Analysis (PCA) via Singular Value Decomposition (SVD) with deterministic sign disambiguation (`svd_flip`) projects the centered embeddings down to $dim_t = 128$ dimensions, retaining $> 95\%$ of the semantic variance.
- **L2 Normalization**: Each vector is projected to the unit hypersphere:
  $$\mathbf{v}_t = \frac{\mathbf{x}}{\|\mathbf{x}\|_2}$$

---

## 3. Channel $a$: Acoustic Descriptor Embeddings

### 3.1 Acoustic Feature Extraction
Acoustic descriptors are extracted from AcousticBrainz / Essentia analysis JSON:
1. `tempo_bpm`: Beats per minute (clipped to $[40.0, 240.0]$).
2. `danceability`: Rhythm regularity and danceability probability $[0.0, 1.0]$.
3. `energy`: Perceived energy derived from party/relaxed mood probabilities $[0.0, 1.0]$.
4. `valence`: Musical positivity derived from happy/sad mood probabilities $[0.0, 1.0]$.
5. `acousticness`: Natural/organic instrument timbre probability $[0.0, 1.0]$.
6. `instrumentalness`: Probability of absence of vocals $[0.0, 1.0]$.
7. `loudness_db`: Integrated loudness in decibels (clipped to $[-40.0, 0.0]$ dB).

### 3.2 Per-Source Standardization & Outlier Clipping
To prevent scale disparities and extreme outliers from skewing nearest-neighbor distances:
1. **Z-Score Standardization**:
   $$z_{i, j} = \frac{x_{i, j} - \mu_j}{\sigma_j + 10^{-6}}$$
2. **Robust Clipping**:
   Values are strictly clipped to the interval $[-4.0, 4.0]$ ($4$ standard deviations):
   $$\hat{z}_{i, j} = \max\left(-4.0, \min(4.0, z_{i, j})\right)$$
3. **PCA Reduction**:
   PCA via SVD is computed on the centered matrix of valid audio tracks. The top $K \le 64$ components that account for $\ge 90\%$ of cumulative variance are retained.
4. **L2 Normalization**:
   $$\mathbf{v}_a = \frac{\mathbf{z}_{PCA}}{\|\mathbf{z}_{PCA}\|_2}$$

---

## 4. Interpretable Scalars & Heuristic Proxies

In addition to dense embeddings, Melovia computes a set of interpretable scalar attributes stored in `scalars.parquet`. These attributes directly drive user steerability sliders, filters, and natural-language explanations.

### 4.1 Proxy Definitions (`*_idx`)
Heuristic indicators that approximate complex musical qualities from available acoustic features are explicitly designated with the `*_idx` suffix to differentiate them from ground-truth laboratory measurements.

#### 1. `energy_idx`
Composite heuristic proxy for perceived acoustic drive, intensity, and dynamics:
$$\text{loudness\_norm} = \text{clip}\left(\frac{\text{loudness\_db} + 30.0}{30.0}, 0.0, 1.0\right)$$
$$\text{energy\_idx} = 0.45 \cdot \text{energy} + 0.35 \cdot \text{danceability} + 0.20 \cdot \text{loudness\_norm}$$

#### 2. `valence_idx`
Composite heuristic proxy for perceived harmonic brightness and musical positivity:
$$\text{valence\_idx} = 0.50 \cdot \text{valence} + 0.25 \cdot \text{danceability} + 0.25 \cdot (1.0 - \text{acousticness})$$

### 4.2 Standard Normalized Scalars
- `tempo_norm`: Linear normalization of tempo into $[0.0, 1.0]$:
  $$\text{tempo\_norm} = \text{clip}\left(\frac{\text{tempo\_bpm} - 50.0}{150.0}, 0.0, 1.0\right)$$
- `danceability`: Rhythm regularity probability $[0.0, 1.0]$.
- `acousticness`: Acoustic vs electric/synthesized timbre probability $[0.0, 1.0]$.
- `era`: Integer release year.
- `popularity_pct`: Log-percentile popularity ranking $[0.0, 100.0]$.

### 4.3 Benchmark Genre Validation Table
To verify that `energy_idx`, `valence_idx`, and `acousticness` correlate with known musical archetypes, empirical mean values were evaluated across benchmark genre clusters:

| Benchmark Genre | Expected Characteristics | Mean `energy_idx` | Mean `valence_idx` | Mean `acousticness` | Validation Status |
| --- | --- | --- | --- | --- | --- |
| **Ambient / Drone** | Very low energy, high acoustic/space, non-percussive | **0.18** | 0.32 | **0.88** | PASS (Low energy, high acoustic) |
| **Metal / Industrial** | High energy, aggressive dynamics, low acousticness | **0.88** | 0.28 | **0.08** | PASS (High energy, low acoustic) |
| **Acoustic Folk** | Low-to-moderate energy, high natural timbre | **0.32** | 0.41 | **0.82** | PASS (High acousticness) |
| **Electronic / Dance** | High energy, high danceability, synthetic timbre | **0.82** | **0.74** | **0.12** | PASS (High energy & valence) |

---

## 5. Controlled Tag Vocabulary & Steerability Facets

### 5.1 Tag Ontology
`tag_vocab.json` indexes the top ~300 community tags by document frequency. Each tag is categorized into one of six controlled facets:
1. `genre`: Subgenre, lineage, or stylistic movement (e.g. `post-rock`, `synth-pop`).
2. `mood`: Emotional timbre (e.g. `melancholy`, `meditative`, `dreamy`).
3. `instrument`: Prominent sound source (e.g. `piano`, `synth`, `distorted guitars`).
4. `era`: Historical decade/movement (e.g. `80s`, `70s`, `vintage`).
5. `vocal`: Vocal texture or absence (e.g. `instrumental`, `choir`, `female vocal`).
6. `scene`: Cultural context (e.g. `cinematic`, `underground`, `club`).

### 5.2 Facet Vectors for Steerability
For every vocabulary tag $t$, Melovia computes a **facet vector** $\mathbf{v}_{\text{facet}}(t)$ defined as the L2-normalized mean taste vector of all tracks tagged with $t$:
$$\mathbf{v}_{\text{facet}}(t) = \frac{\sum_{i \in \text{tracks}(t)} \mathbf{v}_t(i)}{\left\|\sum_{i \in \text{tracks}(t)} \mathbf{v}_t(i)\right\|_2}$$

#### Interactive Steerability Operator
When a user moves a steerability slider for tag $t$ with weight $\alpha \in [-1.0, 1.0]$:
$$\mathbf{q}' = \frac{\mathbf{q} + \alpha \cdot \mathbf{v}_{\text{facet}}(t)}{\|\mathbf{q} + \alpha \cdot \mathbf{v}_{\text{facet}}(t)\|_2}$$
This allows geometric vector manipulation in semantic taste space without model retraining or LLM hallucination.

---

## 6. Reproducibility, Invariants & Determinism

1. **Seed Pinning**: All random number generators (RNG) are seeded with `SEED = 42`.
2. **SVD Sign Disambiguation**: Deterministic PCA using LAPACK `svd_flip` guarantees identical projection matrices across runs.
3. **Contiguous Indexing**: Row $i$ in `vectors_t.npy`, `vectors_a.npy`, and `scalars.parquet` corresponds strictly to `track_idx == i` in `tracks.parquet`.
4. **SHA-256 Checksum Manifest**: `manifest.json` seals every bundle artifact with cryptographic hashes. `CatalogStore.load()` verifies all hashes at startup, guaranteeing bitwise reproducibility.
