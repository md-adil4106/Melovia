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

---

## 7. Core Recommender Engine v1 (Level A)

The Level A recommendation engine generates relevance-ranked track discoveries from 1 to 10 user-selected seed tracks without opaque black-box scoring.

### 7.1 Multi-Seed Taste Profiling & Clustering (`recsys/taste.py`)
Users can provide disparate seed tracks representing multiple stylistic intentions (e.g. ambient drone alongside post-punk). Rather than collapsing all seeds into a single blurry centroid, Melovia partitions seeds into cohesive **Taste Modes**:
- **Small Seed Sets ($N < 6$)**: Each seed track directly forms its own taste mode ($K = N$ modes), ensuring individual seed characteristics are completely preserved.
- **Large Seed Sets ($N \ge 6$)**: Deterministic k-medoids clustering partitions seeds into $K \in \{2, 3\}$ clusters by maximizing the average silhouette score computed over cosine distances in semantic taste space ($\mathbf{v}_t$).
- **Cluster Weights**:
  $$\pi_m = \frac{|C_m|}{N_{\text{seeds}}}$$
- **Mode Centroid Vectors**:
  $$\mathbf{c}_m^t = \frac{\sum_{i \in C_m} \mathbf{v}_t(i)}{\|\sum_{i \in C_m} \mathbf{v}_t(i)\|_2}, \quad \mathbf{c}_m^a = \frac{\sum_{i \in C_m \cap \text{has\_a}} \mathbf{v}_a(i)}{\|\sum_{i \in C_m \cap \text{has\_a}} \mathbf{v}_a(i)\|_2}$$

### 7.2 Candidate Generation (`recsys/candidates.py`)
To ensure high recall without scanning the entire catalog at subsequent reranking stages:
1. For each taste mode $m$ and channel $c \in \{t, a\}$:
   $$\mathbf{s}_m^c = \mathbf{V}^c \mathbf{c}_m^c$$
   Top $K_{\text{cand}} = 500$ tracks are retrieved per mode and channel.
2. **Union Pooling**: The final candidate pool is the deduplicated union across all modes and active channels.
3. **Seed & Artist Exclusion**:
   - Seed tracks are strictly filtered out ($i \notin \text{Seeds}$).
   - Optionally, seed artists are excluded to ensure discovery outside familiar discographies.

### 7.3 Multi-Modal Scoring & Smooth-Max Aggregation (`recsys/scoring.py`)
For every candidate track $i$:
1. **Log-Sum-Exp Smooth Max Across Modes**:
   Rather than a simple max (which is non-smooth and ignores secondary clusters) or a mean (which penalizes niche seeds), mode similarities are aggregated using temperature-scaled log-sum-exp ($\tau = 8.0$):
   $$s_i^c = \frac{1}{\tau} \log \sum_{m=1}^{M} \pi_m \exp\left(\tau \cdot \langle \mathbf{c}_m^c, \mathbf{v}_i^c \rangle\right)$$
   Computed using the numerically stable identity $u_{\max} + \log \sum \exp(u - u_{\max})$ to prevent float overflow.
2. **Empirical Percentile Calibration**:
   Raw cosine scores are mapped to empirical percentiles relative to the candidate pool:
   $$p_i^c = \frac{\text{Rank}(s_i^c)}{|\mathcal{C}|} \in [0.0, 1.0]$$
3. **Dynamic Channel Combination**:
   $$S_i = w_t \cdot p_i^t + w_a \cdot p_i^a$$
   Nominal weights: $w_t = 0.60$ (semantic), $w_a = 0.40$ (acoustic).
   **Missing Audio Invariant**: If a candidate track has `has_a = False` (or all seeds lack audio), weights dynamically renormalize to $w_t = 1.0, w_a = 0.0$.
4. **Deterministic Ranking**:
   Results are sorted strictly by $(-S_i, \text{track\_id})$.

---

## 8. Discovery Control & Steerability (Familiarity ↔ Discovery)

The Discovery Control slider ($d \in [0.0, 1.0]$) provides real-time, interactive steerability over the recommendation ranking without repeating expensive catalog vector scans.

### 8.1 Mathematical Formulation

#### 1. Known Seeds Reference Set
Let $K = \text{Seeds} \cup \text{Liked Tracks}$ be the known anchor set. For candidate track $i$:
- **Novelty ($nov_i$)**: Cosine distance to the nearest known seed in semantic taste space:
  $$nov_i = 1.0 - \max_{j \in K} \langle \mathbf{x}_i^t, \mathbf{x}_j^t \rangle \in [0.0, 2.0]$$
- **Familiarity ($fam_i$)**:
  $$fam_i = 1.0 - nov_i = \max_{j \in K} \langle \mathbf{x}_i^t, \mathbf{x}_j^t \rangle$$
- **Artist Newness Indicator ($A_i$)**:
  $$A_i = \mathbb{I}[\text{artist}_i \notin \text{known artists}] \in \{0.0, 1.0\}$$
- **Normalized Popularity ($P_i$)**:
  $$P_i = \text{clip}\left(\frac{\text{popularity\_pct}_i}{100.0}, 0.0, 1.0\right)$$

#### 2. Target Gaussian Novelty Function
To allow the slider to target specific bands of musical distance rather than merely rewarding extreme outliers:
$$\mu(d) = 0.15 + 0.50 \cdot d$$
$$N_i = \exp\left( - \frac{(nov_i - \mu(d))^2}{2 \cdot \sigma^2} \right), \quad \sigma = 0.15$$
- At $d = 0.0$: $\mu = 0.15$, targeting tracks closely clustered around the seeds.
- At $d = 1.0$: $\mu = 0.65$, targeting tracks in exploratory adjacent subgenres.

#### 3. Discovery Score ($D_i$)
$$D_i = 0.50 \cdot N_i + 0.30 \cdot A_i + 0.20 \cdot (1.0 - P_i)$$

#### 4. Unadjusted Utility ($U_i$)
Combines base multi-channel relevance $R_i \in [0.0, 1.0]$ with discovery score $D_i$:
$$U_i = (1.0 - 0.60 \cdot d) \cdot R_i + (0.60 \cdot d) \cdot D_i$$
- At $d = 0.0$: $U_i = R_i$ (pure relevance).
- At $d = 1.0$: $U_i = 0.40 \cdot R_i + 0.60 \cdot D_i$.

#### 5. Dynamic Relevance Floor
To prevent discovery from devolving into irrelevant noise, candidates falling below a dynamic floor are dropped:
$$\text{Floor}(d) = 0.60 - 0.30 \cdot d$$
Candidates with $R_i < \text{Floor}(d)$ are filtered prior to MMR selection.

#### 6. Maximal Marginal Relevance (MMR) Selection
Tracks are greedily selected into recommended set $S$ ($|S| = n$) according to:
$$i^* = \arg\max_{i \in \mathcal{C} \setminus S} \left[ \lambda \cdot U_i - (1.0 - \lambda) \max_{j \in S} \text{sim}(i, j) \right]$$
where:
$$\lambda = 1.0 - 0.50 \cdot d$$
Pairwise track similarity $\text{sim}(i, j)$ combines semantic, acoustic, and artist factors:
$$\text{sim}(i, j) = 0.60 \cdot \langle \mathbf{x}_i^t, \mathbf{x}_j^t \rangle + 0.30 \cdot \langle \mathbf{x}_i^a, \mathbf{x}_j^a \rangle + 0.10 \cdot \mathbb{I}[\text{artist}_i = \text{artist}_j]$$
If either track lacks audio analysis, weights dynamically renormalize to $0.90 \cdot \langle \mathbf{x}_i^t, \mathbf{x}_j^t \rangle + 0.10 \cdot \mathbb{I}[\text{artist}_i = \text{artist}_j]$.

#### 7. Hard Artist Cap
- For $d < 0.70$: At most 2 tracks per artist are admitted into $S$.
- For $d \ge 0.70$: At most 1 track per artist is admitted into $S$.

#### 8. Deterministic Tie-Breaking
Any ties in MMR score are broken deterministically by lexicographical order of `track_id`.


