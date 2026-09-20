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

---

## 5. Explainability Framework (Signal-True Explanations)

### 5.1 Architectural Principles
Melovia enforces strict signal-grounding for every recommendation explanation (WOW #3):
1. **Signal-True Invariant**: Every explanation sentence maps to $\ge 1$ named ranking signal in `RecSignals`. No sentence is ever emitted without quantifiable numerical evidence.
2. **Proxy Qualification Invariant**: Heuristic proxies (`energy_idx`, `valence_idx`) are explicitly qualified with `(approx.)` in all user-facing copy to prevent misleading scientific claims.
3. **Dynamic Salience Weighting**: Reasons are dynamically weighted by relevance and the Discovery Control parameter $d \in [0.0, 1.0]$. When $d \to 0.0$, familiarity, tag overlap, and acoustic texture are emphasized; when $d \to 1.0$, novelty, underground status, and exploratory aesthetic clusters take precedence.
4. **Deterministic Rule Table**: The pure Python `ExplanationBuilder` maps ranking signals to natural-language explanations deterministically with zero external API dependencies.

### 5.2 Rule Table Specification

| Rule ID | Name | Trigger Condition / Threshold | Signal Keys | Salience Weight Function | Output Format / Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `RULE_SHARED_TAGS` | Shared Folksonomy Tags | Shared tags $\ge 1$ between candidate and seeds | `shared_tags` | $w = 1.0 + 0.3 \cdot \min(N, 3)$ | *"Shares alternative rock and post-punk with your seed tracks."* |
| `RULE_ENERGY_MATCH` | Energy Match (Approx.) | $|\Delta\text{energy\_idx}| \le 0.12$ | `scalar_deltas`, `nearest_seed_id` | $w = (1 - |\Delta|) \cdot (1.0 - 0.3d)$ | *"Close to your preferred energy range (94% match) (approx.)."* |
| `RULE_VALENCE_MATCH` | Mood Match (Approx.) | $|\Delta\text{valence\_idx}| \le 0.12$ | `scalar_deltas`, `nearest_seed_id` | $w = (1 - |\Delta|) \cdot (0.9 - 0.2d)$ | *"Matches the emotional mood of your seeds (92% match) (approx.)."* |
| `RULE_NEW_ARTIST` | Artist Discovery | $\text{artist\_new} = \text{True}$ | `artist_new` | $w = 0.5 + 0.8d$ | *"Introduces [Artist], a new artist for your listening profile."* |
| `RULE_SAME_ARTIST` | Catalog Familiarity | $\text{artist\_new} = \text{False}$ | `artist_new` | $w = 0.9 \cdot (1.0 - d)$ | *"From [Artist], expanding on your seed selection."* |
| `RULE_HIGH_NOVELTY` | Exploratory Discovery | $\text{novelty} \ge 0.55$ | `novelty` | $w = \text{nov} \cdot (0.5 + 1.2d)$ | *"Expands into a less familiar sound within this genre space."* |
| `RULE_LOW_NOVELTY` | Stylistic Anchor | $\text{novelty} \le 0.20$ | `novelty`, `familiarity` | $w = (1 - \text{nov}) \cdot (1.2 - 0.8d)$ | *"Solidifies familiar territory with core stylistic anchors."* |
| `RULE_LESSER_KNOWN` | Underground Track | $\text{popularity\_pct} \le 35.0$ | `popularity_pct` | $w = \frac{35 - \text{pop}}{35} \cdot (0.6 + 0.9d)$ | *"Lesser-known underground track (18% popularity)."* |
| `RULE_MAINSTREAM` | Mainstream Track | $\text{popularity\_pct} \ge 75.0$ | `popularity_pct` | $w = \frac{\text{pop}}{100} \cdot (1.0 - 0.5d)$ | *"Well-known staple within this musical realm (84% popularity)."* |
| `RULE_SEMANTIC_MATCH` | High Semantic Similarity | $pct_t \ge 0.80$ | `pct_t`, `sim_t`, `nearest_seed_id` | $w = pct_t \cdot (1.2 - 0.4d)$ | *"Strong stylistic match with [Nearest Seed] (96% match)."* |
| `RULE_ACOUSTIC_MATCH` | High Acoustic Texture Match | $pct_a \ge 0.70$ | `pct_a`, `sim_a` | $w = pct_a \cdot 1.1$ | *"Shares similar acoustic and rhythmic texture with your seeds (88% acoustic match)."* |
| `RULE_REGION_ALIGNMENT` | Aesthetic Cluster / Region | Region label present | `region_id`, `region_label` | $w = 0.8 + 0.5d$ (exp) / $0.9(1-0.3d)$ | *"Anchored in the [Region] soundscape."* or *"Explores the [Region] aesthetic cluster."* |

### 5.3 Verifier-Guarded LLM Polish Architecture

Melovia includes an optional editorial polish interface (`api/app/llm/polish.py`) behind the setting flag `EXPLAIN_LLM_POLISH=false` (default disabled):
- **Input Restricted**: The LLM receives strictly structured reason JSON (rule ID, text, signal keys, and numeric evidence). It never accesses the vector index or catalog directly.
- **Output Invariants Enforced by `verify_polished_reason`**:
  1. **Numeric Integrity**: Every integer or floating-point percentage in the output must match a value in the structured evidence dictionary within $\pm 0.5$ tolerance. Hallucinated numbers are rejected.
  2. **Vocabulary & Entity Integrity**: Any named entities (artists, seeds) must exist in the source reason. Words resembling instrument solos, genres, or stylistic adjectives not grounded in evidence or the original template are rejected.
  3. **Mandatory Fallback**: If verification fails for any reason, the system silently and safely falls back to the deterministic template reason. No user ever receives an ungrounded explanation.

---

## 6. Session Context & Conversational Refinement (WOW #4)

### 6.1 Architectural Objective & Threat Model
Natural-language discovery allows listeners to express nuanced, fluid musical intentions (e.g., *"more energetic"*, *"keep the vibe but add rock"*, *"night drive at 2 AM"*, *"less mainstream"*). In conventional systems, natural-language prompts are passed to LLMs that hallucinate track titles, invent non-existent metadata, or introduce severe popularity and recency biases.

Melovia enforces an **untrusted LLM boundary**:
1. **Zero Direct Track Selection**: The LLM never sees track IDs, never queries the database, and never emits track lists.
2. **Schema Confinement**: The LLM parses free-form text strictly into a validated Pydantic `Refinement` object (`knobs`, `popularity_ceiling`, `boost_tags`, `suppress_tags`, `arc`, `unsupported`, `clarify`).
3. **Controlled Vocabulary Confinement**: Any tag not present in the catalog's immutable `tag_vocab.json` is discarded and returned under `unsupported`.
4. **Temporary Session Isolation**: Steering constraints are stored in an ephemeral in-memory `SessionStore` (2-hour TTL) associated with a signed session cookie. The persistent database profile (`ProfilePlaceholder`) is **never mutated**.

### 6.2 Mathematical Formulation of Session Context Steering

#### 1. Context Vector Shift ($\mathbf{C}$)
Boosted and suppressed tags are converted to centroid vectors in semantic taste space ($\mathbb{R}^{128}$):
$$\mathbf{C} = \sum_{t \in \text{boost}} w_t \cdot \mathbf{v}_t - \sum_{s \in \text{suppress}} w_s \cdot \mathbf{v}_s$$
where $\mathbf{v}_t$ is the average embedding vector of tracks tagged with $t$. The multi-modal seed taste centroid $\mathbf{T}_m$ is dynamically shifted:
$$\mathbf{Q}_m = \frac{\mathbf{T}_m + 0.50 \cdot \mathbf{C}}{\|\mathbf{T}_m + 0.50 \cdot \mathbf{C}\|_2}$$

#### 2. Interpretable Scalar Target Matching
For each active scalar knob $k \in \{\text{energy}, \text{valence}, \text{tempo}, \text{acousticness}, \text{danceability}\}$ with delta $\Delta_k \in [-1.0, 1.0]$, a soft target value is established relative to the seed tracks' mean baseline:
$$\text{target}_k = \text{clip}\left(\mu_{\text{seed}, k} + 0.35 \cdot \Delta_k, 0.0, 1.0\right)$$
For each candidate track $i$, closeness to the target is scored:
$$\text{match}_{i, k} = 1.0 - |s_{i, k} - \text{target}_k|$$
The mean match across active knobs blends into base relevance with weight $\gamma = 0.35$:
$$R_i \leftarrow (1.0 - \gamma) \cdot R_i + \gamma \cdot \left( \frac{1}{|K|} \sum_{k \in K} \text{match}_{i, k} \right)$$

#### 3. Suppress Tag Soft Penalty
Candidates possessing tags explicitly suppressed by the user receive a multiplicative penalty:
$$R_i \leftarrow R_i \cdot (1.0 - 0.50 \cdot w_s)$$
where $w_s \in [0.0, 1.0]$ is the suppression weight.

#### 4. Popularity Ceiling Penalty
If a constraint imposes a popularity ceiling $P_{\text{ceil}} \in [0.0, 1.0]$ (e.g. underground / hidden gems intent):
$$R_i \leftarrow R_i \cdot \max\left(0.10, 1.0 - 2.50 \cdot \max(0, P_i - P_{\text{ceil}})\right)$$

#### 5. Novelty Gaussian Mean Shift
When the novelty knob delta $\Delta_{\text{novelty}}$ is active:
$$\mu \leftarrow \text{clip}\left(\mu + 0.25 \cdot \Delta_{\text{novelty}}, 0.05, 0.95\right)$$
shifting the target novelty curve in the Discovery Control formula.

### 6.3 Reversibility & Rate Limiting
- **Deterministic Replay**: When a constraint is deleted (`DELETE /refine/{id}`), the session context is rebuilt from the remaining active constraints and re-applied to the cached candidate pool.
- **Token Bucket Rate Limiting**: Every session is protected by a token bucket rate limiter (capacity 20 tokens, refill rate 0.5 tokens/second). Rapid automated requests exceeding the quota receive `HTTP 429 Too Many Requests`.

---

## 7. Feedback Dynamics & Persistent Profile Architecture (Phase 9)

### 7.1 Separation of Session Adaptation vs. Persistent Profile

Melovia enforces strict separation between **in-session fluid adaptation** and the **durable persistent profile**:
1. **Live Session Adaptation**: Micro-interactions (like, dislike, skip, save) immediately adjust active session taste modes in-memory and re-score cached candidate tracks in sub-100ms. They do **not** write to the long-term profile database table.
2. **Explicit User Consent for Permanence**: Persistent long-term taste is updated only when the listener explicitly triggers `"Remember this vibe"` (`POST /profile/remember`).
3. **Anonymous Device Identity**: Profiles are keyed by an anonymous UUID stored in an `httpOnly`, `SameSite=Lax` cookie (`melovia_device_id`). No user accounts, passwords, email addresses, or personal data exist in Melovia. In all application logs, the device ID is strictly one-way hashed (SHA-256 prefix) to guarantee anonymity.

### 7.2 Mathematical Formulation of In-Session Feedback

For each feedback event on track $k$ with vector $\mathbf{v}_k \in \mathbb{R}^D$:

#### 1. Nearest Mode Identification
The system finds the closest active taste mode $m^*$ to track $k$ using cosine similarity:
$$m^* = \arg\max_m \cos(\mathbf{T}_m, \mathbf{v}_k)$$

#### 2. Positive Feedback Dynamics (Like, Save, Replay, Add)
The nearest taste mode is shifted toward the track representation across all orthogonal channels ($t$ and $a$):
$$\mathbf{T}_{m^*} \leftarrow \frac{\mathbf{T}_{m^*} + \eta \cdot \mathbf{v}_k}{\|\mathbf{T}_{m^*} + \eta \cdot \mathbf{v}_k\|_2}$$
where learning rate $\eta = 0.15$. The track ID is recorded in session known tracks and liked tracks.

#### 3. Negative Feedback Dynamics (Dislike, Skip, Remove)
The nearest taste mode is shifted away from the track representation:
$$\mathbf{T}_{m^*} \leftarrow \frac{\mathbf{T}_{m^*} - (\text{factor} \cdot \eta) \cdot \mathbf{v}_k}{\|\mathbf{T}_{m^*} - (\text{factor} \cdot \eta) \cdot \mathbf{v}_k\|_2}$$
where:
- For `dislike`: $\text{factor} = 0.50$. The track ID is added to `negative_track_ids`, and its artist ID is added to `negative_artist_ids`.
- For `skip`: $\text{factor} = 0.125$ (mild dampening). No hard exclusions are added.
- For `remove`: $\text{factor} = 0.25$. Track ID is added to negative exclusions.

#### 4. Candidate Pool Exclusion
During candidate retrieval and reranking, any track where $\text{track\_id} \in \text{negative\_track\_ids}$ or $\text{artist\_id} \in \text{negative\_artist\_ids}$ is strictly excluded ($R_i = 0$).

### 7.3 Persistent Profile Merging & Drift Capping

When the listener explicitly clicks `"Remember this vibe"` (`POST /profile/remember`), session modes are merged into persistent modes using an exponential moving average with bounded Euclidean drift:

#### 1. Convex Combination
For each persistent mode $\mathbf{p}$ paired with its nearest session mode $\mathbf{s}$:
$$\mathbf{u} = (1 - \alpha) \cdot \mathbf{p} + \alpha \cdot \mathbf{s}$$
where $\alpha = 0.30$.

#### 2. Euclidean Drift Capping ($\delta_{\max} = 0.25$)
To prevent rapid mode collapse or single-session overfitting, the displacement vector $\mathbf{d} = \mathbf{u} - \mathbf{p}$ is strictly bounded by maximum drift radius $\delta_{\max} = 0.25$:
$$\text{drift} = \|\mathbf{u} - \mathbf{p}\|_2$$
$$\mathbf{u}_{\text{capped}} = \begin{cases}
\mathbf{u}, & \text{if } \text{drift} \le \delta_{\max} \\
\mathbf{p} + \delta_{\max} \cdot \frac{\mathbf{u} - \mathbf{p}}{\|\mathbf{u} - \mathbf{p}\|_2}, & \text{otherwise}
\end{cases}$$
$$\mathbf{p}_{\text{merged}} = \frac{\mathbf{u}_{\text{capped}}}{\|\mathbf{u}_{\text{capped}}\|_2}$$

### 7.4 Explainability Integration (Rule 14)

When user feedback shifts recommendations, recommended tracks exhibiting high semantic affinity ($\ge 70\%$) to liked tracks trigger Rule 14 (`RULE_FEEDBACK_LIKED`):
- Explanation: *"Moves toward [Liked Track Title] which you liked (88% match)."*
- Grounded strictly in calculated dot-product similarity to session liked track vectors.

### 7.5 Portability & Complete Erasure

Under Melovia's data sovereignty principles:
- **Portable JSON Export** (`GET /profile/export`): Serializes all multi-modal channel vectors, weights, member seeds, and known tracks in a self-contained, versioned JSON schema.
- **Complete Erasure** (`DELETE /profile`): Purges the device profile row from the database, deletes all recorded interaction events for that device, and flushes ephemeral in-memory session caches.
