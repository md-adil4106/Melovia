# Melovia — Evaluation Framework & Methodology

## 1. Evaluation Philosophy

Recommendation systems for music discovery face a fundamental measurement dilemma:
**Offline representations cannot measure subjective human discovery without ground-truth interaction logs, and evaluating vector models against their own embeddings is inherently circular.**

In Melovia, we reject fake rigor:
1. **No Unearned Accuracy Claims**: We never claim "Precision@K" or "NDCG@K" against synthetic or representation-derived targets.
2. **Representation Space Honesty**: Intra-list diversity, neighborhood hit-rates, and cluster dispersion measure geometric characteristics of the vector space, not listener satisfaction.
3. **Statistical Rigor**: All system comparisons report paired bootstrap confidence intervals (95% CI) across diverse, repeatable seed sets.
4. **Honest Evaluation Proxies**: Playlist continuation on public listen data (e.g. ListenBrainz JSPF) is supported, but catalog coverage must be reported alongside every result.

---

## 2. Evaluation Suite Architecture

Melovia's evaluation framework is housed in `eval/` and callable via `make eval` (full suite) or `make eval-ci` (regression guard):

```
eval/
├── metrics.py               # Pure mathematical definitions of offline metrics
├── runner.py                # Comparative evaluation matrix, bootstrap CIs, report generator
├── generate_seedsets.py     # Deterministic generator for coherent evaluation seed sets
├── playlist_continuation.py # JSPF playlist continuation evaluator with MBID matching
├── seedsets.yaml            # 36 auto-generated tag/region-coherent seed sets (SEED=42)
├── seedsets_manual.yaml     # Hand-curated template covering 30 canonical genres/eras
└── reports/                 # Output directory for markdown reports and results.csv (gitignored)
```

---

## 3. Evaluated Systems & Ablations

Every evaluation run executes a matrix of reference baselines, hybrid configurations, and algorithmic ablations:

| System Name | Type | Description |
| :--- | :--- | :--- |
| `random` | Reference Baseline | Uniform random selection from the catalog, seed-excluded. |
| `genre_only` | Reference Baseline | Random selection restricted to tracks sharing seeds' dominant tags/regions. |
| `cosine_t` | Reference Baseline | Nearest neighbors in semantic tag vector space ($t$), no audio or MMR. |
| `cosine_a` | Reference Baseline | Nearest neighbors in acoustic descriptor vector space ($a$), no semantic tags or MMR. |
| `hybrid_d00` | Full Recommender | Multi-channel scoring with discovery slider set to $d = 0.0$ (maximum familiarity). |
| `hybrid_d35` | Full Recommender | Multi-channel scoring with default discovery slider ($d = 0.35$, reference configuration). |
| `hybrid_d75` | Full Recommender | Multi-channel scoring with discovery slider set to $d = 0.75$ (high exploration). |
| `hybrid_no_audio` | Algorithmic Ablation | Full hybrid engine with acoustic channel disabled (`use_audio=False`). |
| `hybrid_no_mmr` | Algorithmic Ablation | Full hybrid engine with diversity re-ranking disabled (`use_mmr=False`). |
| `hybrid_no_pop_corr`| Algorithmic Ablation | Full hybrid engine with popularity dampening disabled (`popularity_correction=False`). |

---

## 4. Metric Formulations

### 4.1 Intra-List Diversity (ILD)

Measures the average pairwise distance between recommended tracks in the semantic vector space ($t$). Given recommended track set $S$ with $|S| = K$:

$$\text{ILD}(S) = 1 - \frac{1}{|S|(|S| - 1)} \sum_{i \in S} \sum_{j \in S, j \neq i} \cos(v_i^{(t)}, v_j^{(t)})$$

Because vectors are $L_2$-normalized, $\cos(v_i, v_j) = v_i \cdot v_j \in [-1, 1]$, yielding $\text{ILD} \in [0.0, 2.0]$ (typically $[0.0, 1.0]$). Higher values signify greater acoustic and stylistic dispersion within the recommended list.

### 4.2 Item Novelty (Self-Information Bits)

Quantifies inverse-popularity exposure in information-theoretic bits:

$$\text{Nov}(S) = \frac{1}{|S|} \sum_{i \in S} -\log_2(p_i), \quad \text{where } p_i = \frac{P_i}{\sum_{j \in \mathcal{C}} P_j}$$

- $P_i$: Popularity score of track $i$.
- $\mathcal{C}$: Entire catalog.
- Higher bit values denote deeper exploration of the long tail.

### 4.3 Region / Cluster Entropy

Measures whether recommendations disperse across diverse musical regions or collapse into a single sub-genre:

$$H(S) = -\sum_{r \in \mathcal{R}} p(r) \log_2 p(r)$$

where $p(r)$ is the empirical proportion of recommendations belonging to region $r$.

### 4.4 Gini Coefficient of Item Exposure

Evaluates recommendation fairness and catalog starvation across all evaluation trials:

$$G = \frac{\sum_{i=1}^N (2i - N - 1) \, y_{(i)}}{N \sum_{i=1}^N y_{(i)}}$$

where $y_{(1)} \le y_{(2)} \le \dots \le y_{(N)}$ is the sorted vector of recommendation impression counts across the entire catalog of $N$ tracks.
- $G = 0.0$: Perfectly uniform catalog exposure.
- $G = 1.0$: Complete monopoly (all impressions concentrated on a single item).

### 4.5 Artist & Catalog Coverage

- **Artist Coverage**: $\frac{|\bigcup_S \text{Artists}(S)|}{|\text{Total Catalog Artists}|}$
- **Catalog Coverage**: $\frac{|\bigcup_S \text{Tracks}(S)|}{|\text{Total Catalog Tracks}|}$

### 4.6 Seed-Region Hit-Rate (Sanity Check)

The fraction of recommended tracks that belong to the seed tracks' planted cluster regions:

$$\text{HitRate}(S) = \frac{1}{|S|} \sum_{i \in S} \mathbf{1}[\text{region}(i) \in \text{regions}(\text{Seeds})]$$

> [!WARNING]
> **Circularity Notice**: Seed-Region Hit-Rate is labeled strictly as a **SANITY CHECK** (circular for channel $t$). Because embeddings are constructed to group stylistically related tracks together, high hit-rate is an expected geometric consequence of vector retrieval, **not proof of user satisfaction or true relevance**.

---

## 5. Statistical Significance & Paired Bootstrap

To evaluate whether algorithmic differences are statistically meaningful rather than artifacts of seed selection:
1. For each seed set $s \in \{1, \dots, M\}$, we compute the metric difference $\Delta_s = \text{Metric}_{\text{target}}(s) - \text{Metric}_{\text{reference}}(s)$, where the reference is `hybrid_d35`.
2. We perform $B = 1,000$ bootstrap resamples with replacement of the seed sets.
3. We report the empirical mean difference and the 95% percentile confidence interval: $[\Delta_{0.025}, \Delta_{0.975}]$.

---

## 6. Playlist Continuation Proxy (ListenBrainz JSPF)

To measure proxy relevance on human-curated music, Melovia includes `eval/playlist_continuation.py`:
- Parses open-data playlists in JSPF (JSON Shareable Playlist Format) from ListenBrainz.
- Maps playlist tracks to Melovia catalog entries via MusicBrainz Recording IDs (MBID).
- For playlists with $\ge 8$ catalog-covered tracks, the first 4 serve as seeds, and the remaining tracks serve as the ground-truth relevant set.
- Evaluates $\text{Recall}@K$ and $\text{NDCG}@K$.

> [!IMPORTANT]
> **Catalog Coverage Reporting Rule**: Playlist continuation results MUST ALWAYS be reported alongside the catalog coverage percentage. When catalog coverage is low ($< 20\%$), Recall and NDCG reflect catalog overlap rather than recommender quality. If zero playlists meet the threshold, the tool cleanly reports catalog coverage and exits without fabricating scores.

---

## 7. CI Regression Guard (`make eval-ci`)

In continuous integration (`.github/workflows/ci.yml`), `make eval-ci` runs a deterministic evaluation pass against the mock catalog and verifies four hard regression gates:

1. **Gate 1 — Discovery Monotonicity**:
   Mean novelty at $d = 0.75$ must be strictly greater than or equal to mean novelty at $d = 0.0$ ($\text{Nov}_{0.75} \ge \text{Nov}_{0.0} - 0.05$).
2. **Gate 2 — Diversity Guard**:
   The full hybrid recommender ($d = 0.35$) must maintain intra-list diversity comparable to or exceeding pure cosine-t ($\text{ILD}_{\text{hybrid}} \ge \text{ILD}_{\text{cosine}} - 0.05$).
3. **Gate 3 — Acoustic Ablation Efficacy**:
   Disabling the acoustic channel (`-audio`) must measurably alter recommendations and diversity.
4. **Gate 4 — MMR Ablation Efficacy**:
   Disabling MMR re-ranking (`-MMR`) must measurably drop intra-list diversity ($\text{ILD}_{\text{with\_mmr}} > \text{ILD}_{\text{no\_mmr}}$).

---

## 8. User-Study Protocol Outline (Phase 15 Roadmap Placeholder)

Because offline metrics cannot substitute for human experience, Phase 15 will implement a formal user evaluation protocol:

1. **Participants**: $N = 30$ active music discovery listeners.
2. **Design**: Within-subjects, double-blinded comparison between:
   - System A: Melovia Hybrid with Steerable Discovery Slider.
   - System B: Static Single-Channel Cosine Baseline.
   - System C: Popularity-Weighted Genre Baseline.
3. **Tasks**:
   - *Target Aesthetic Discovery*: Find 5 unfamiliar tracks that evoke a specific mood/era.
   - *Dynamic Steering*: Adjust the discovery slider from 0.0 to 1.0 and evaluate perceptual responsiveness.
4. **Quantitative Measures (5-point Likert)**:
   - *Perceived Relevance*: "The recommendations matched my aesthetic intent."
   - *Perceived Discovery / Serendipity*: "I discovered tracks I would not have encountered otherwise."
   - *Perceived Transparency*: "I understood why these tracks were recommended."
   - *Perceived Control*: "Adjusting the discovery control gave me meaningful steering over the results."
5. **Behavioral Logging**:
   - Session duration, slider interaction frequency, preview play rates, and playlist export completion.
