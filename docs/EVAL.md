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

In continuous integration (`.github/workflows/ci.yml`), `make eval-ci` runs a deterministic evaluation pass against the mock catalog and verifies six hard regression gates:

1. **Gate 1 — Discovery Monotonicity**:
   Mean novelty at $d = 0.75$ must be strictly greater than or equal to mean novelty at $d = 0.0$ ($\text{Nov}_{0.75} \ge \text{Nov}_{0.0} - 0.05$).
2. **Gate 2 — Diversity Guard**:
   The full hybrid recommender ($d = 0.35$) must maintain intra-list diversity comparable to or exceeding pure cosine-t ($\text{ILD}_{\text{hybrid}} \ge \text{ILD}_{\text{cosine}} - 0.05$).
3. **Gate 3 — Acoustic Ablation Efficacy**:
   Disabling the acoustic channel (`-audio`) must measurably alter recommendations and diversity ($\text{ILD}_{\text{with\_audio}} \ge \text{ILD}_{\text{no\_audio}} - 0.02$).
4. **Gate 4 — MMR Ablation Efficacy**:
   Disabling MMR re-ranking (`-MMR`) must measurably drop intra-list diversity ($\text{ILD}_{\text{with\_mmr}} > \text{ILD}_{\text{no\_mmr}}$).
5. **Gate 5 — Feedback Adaptation Guard**:
   In-session likes must increase hit-rate to the target preference region by at least $+0.15$.
6. **Gate 6 — Sequencing Flow Guard**:
   TSP 2-opt playlist sequencing must reduce pairwise acoustic jump costs by $\ge 15\%$ compared to random ordering, maintain energy arc correlation $\ge 0.70$, and enforce artist adjacency $= 0.00$.

---

## 8. Empirical Benchmark Results (Real Numbers)

Evaluation run across $N=36$ standardized seed sets (3–4 anchor tracks each) on the 3,000-track catalog bundle:

| System / Config | ILD | $\Delta$ vs Hybrid (95% CI) | Novelty | Entropy | Hit-Rate | Artist Cov | Catalog Cov | Gini |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `random` | 0.985 ± 0.000 | [-0.791, -0.756] | 12.37 | 3.95 | 0.05 | 7.5% | 1.0% | 0.990 |
| `genre_only` | 0.204 ± 0.088 | [-0.018, +0.028] | 11.40 | 0.18 | 0.92 | 59.2% | 20.8% | 0.829 |
| `cosine_t` | 0.155 ± 0.036 | [+0.043, +0.067] | 11.90 | 0.12 | 0.93 | 67.9% | 26.1% | 0.788 |
| `cosine_a` | 0.180 ± 0.047 | [+0.009, +0.048] | 11.91 | 0.13 | 0.94 | 68.5% | 26.0% | 0.788 |
| `hybrid_d00` | 0.158 ± 0.033 | [+0.040, +0.064] | 11.88 | 0.13 | 0.94 | 69.1% | 26.6% | 0.783 |
| `hybrid_d35` | 0.210 ± 0.057 | Ref (0.00) | 12.41 | 0.30 | 0.92 | 75.1% | 26.4% | 0.786 |
| `hybrid_d75` | 0.831 ± 0.060 | [-0.644, -0.597] | 12.50 | 3.41 | 0.36 | 69.4% | 25.6% | 0.801 |
| `hybrid_no_audio` | 0.168 ± 0.061 | [+0.029, +0.054] | 12.15 | 0.14 | 0.93 | 73.6% | 26.3% | 0.785 |
| `hybrid_no_mmr` | 0.166 ± 0.047 | [+0.032, +0.055] | 12.40 | 0.13 | 0.94 | 70.9% | 26.3% | 0.785 |
| `hybrid_no_pop_corr` | 0.194 ± 0.055 | [+0.008, +0.023] | 11.90 | 0.23 | 0.92 | 76.6% | 27.8% | 0.769 |

---

## 9. Double-Blind A/B User-Study Framework (Phase 15 Implementation)

Because offline representation metrics cannot replace human subjective perception, Melovia implements an interactive, double-blind evaluation module (`/study`) and analysis script (`eval/study_analysis.py`):

1. **Experimental Design**:
   - Within-subjects, counterbalanced double-blind trial comparing **System Hybrid** (Melovia multi-modal engine) against **Baseline Control** (popularity-weighted genre/tag matcher).
   - Arm identities (`Playlist A` vs `Playlist B`) are cryptographically randomized on the server; all algorithm scores, explanation tags, and track ranking signals are completely stripped from client payloads.
2. **Evaluation Instruments (1–5 Likert Scales)**:
   - **Perceived Relevance**: Harmonic and aesthetic alignment with anchor seeds.
   - **Perceived Discovery / Serendipity**: Exposure to novel tracks the listener would not have found independently.
   - **Acoustic Flow**: Cohesion and smoothness of transitions between adjacent tracks.
   - **Overall Satisfaction**: Holistic listener preference.
   - **Forced-Choice Preference**: Direct choice between Playlist A, Playlist B, or Equal.
3. **Statistical Analysis Protocol (`eval/study_analysis.py`)**:
   - Computes paired parametric differences ($t$-test via `scipy.stats.ttest_rel`) and non-parametric rank differences (Wilcoxon signed-rank test via `scipy.stats.wilcoxon`).
   - Reports 95% bootstrap confidence intervals ($B=1,000$) for each perceptual dimension.
   - Exports zero PII; token-authenticated admin export (`GET /study/export`).
   - Full protocol specification: [`docs/STUDY_PROTOCOL.md`](STUDY_PROTOCOL.md).

