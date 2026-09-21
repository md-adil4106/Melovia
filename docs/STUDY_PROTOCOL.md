# Melovia Evaluation Study Protocol (Double-Blind A/B Evaluation)

## 1. Executive Summary & Objective

The primary objective of this empirical study is to rigorously evaluate whether the **Melovia Multi-Channel Hybrid Recommendation Engine** delivers statistically significant improvements in **Discovery Quality**, **Sequencing Flow**, and **Overall Satisfaction** compared to standard industry baseline heuristics (pure folksonomy/genre tag overlap and popularity matching), while maintaining equal or superior thematic relevance.

---

## 2. Research Questions & Hypotheses

### Primary Research Questions
1. **RQ1 (Discovery)**: Does Melovia's dual-channel latent embedding retrieval with Discovery Control discover more compelling, unfamiliar tracks than a genre/tag overlap baseline?
2. **RQ2 (Flow & Coherence)**: Does Melovia's acoustic-semantic sequencing arc produce playlists with superior transition flow compared to baseline ordering?
3. **RQ3 (Overall Preference)**: In a double-blind forced choice comparison, do listeners prefer Melovia Hybrid playlists over standard baseline playlists?

### Hypotheses
- **$H_1$ (Discovery)**: $\mu_{\text{Discovery, Hybrid}} > \mu_{\text{Discovery, Baseline}}$ ($p < 0.05$).
- **$H_2$ (Flow)**: $\mu_{\text{Flow, Hybrid}} > \mu_{\text{Flow, Baseline}}$ ($p < 0.05$).
- **$H_3$ (Relevance Non-Inferiority)**: $\mu_{\text{Relevance, Hybrid}} \ge \mu_{\text{Relevance, Baseline}} - 0.2$ ($p < 0.05$).
- **$H_4$ (Overall Win Rate)**: The proportion of participants preferring Hybrid over Baseline exceeds $60\%$.

---

## 3. Experimental Methodology

### 3.1 Design
- **Within-Subjects Paired Design**: Each participant evaluates both recommendation arms generated from the identical set of seed tracks.
- **Double-Blind Randomization**:
  - Arm A and Arm B are designated strictly as "Playlist A" and "Playlist B".
  - A fair coin flip ($P = 0.5$) determines whether Playlist A is Hybrid or Baseline.
  - The arm assignment is stored strictly server-side in the trial session cache.
  - Zero metadata, signals, or DOM indicators reveal the identity of either arm to the client or participant.

### 3.2 System Arms
1. **System Hybrid (Experimental Arm)**:
   - Orthogonal multi-channel representation: $x^t$ (semantic folksonomy & cultural embeddings, 128-d) and $x^a$ (acoustic spectral & rhythmic audio features, 128-d).
   - Dynamic masking for tracks without audio.
   - Smooth-max candidate retrieval with MMR diversification.
   - Default Discovery Control parameter $d = 0.35$.
2. **Genre & Popularity Baseline (Control Arm)**:
   - Standard baseline heuristic (`genre_baseline` from `app.recsys.baselines`).
   - Ranks catalog candidates by intersection of folksonomy tags with the seed set, broken by track popularity and deterministic ID.

---

## 4. Sample Size & Power Calculation

A priori statistical power analysis for a paired two-tailed test:
- **Significance Level ($\alpha$)**: $0.05$
- **Statistical Power ($1 - \beta$)**: $0.80$
- **Target Effect Size (Cohen's $d_z$)**: $0.40$ (medium-small effect)
- **Minimum Required Sample Size ($N$)**:
  $$N \ge \left( \frac{z_{1-\alpha/2} + z_{1-\beta}}{d_z} \right)^2 = \left( \frac{1.96 + 0.8416}{0.40} \right)^2 \approx 49.1$$
- **Target Recruitment**: $N = 50$ completed participant trials (36 fixed seed sets from `eval/seedsets.yaml` plus 14 random seed trials).

---

## 5. Questionnaire & Rating Scales

Participants listen to audio previews and examine track tracklists for both playlists before answering 5 standardized questions on 1–5 Likert scales:

### 5.1 Relevance (1–5 Likert)
> *"How well do these recommendations match the thematic and musical mood of your seed tracks?"*
- `1` = Completely unrelated
- `2` = Weak connection
- `3` = Moderately relevant
- `4` = Highly relevant
- `5` = Perfect mood match

### 5.2 Discovery (1–5 Likert)
> *"Did this playlist introduce you to compelling unfamiliar tracks and expand your musical horizons?"*
- `1` = None (only obvious/cliché choices)
- `2` = Minimal discovery
- `3` = Some pleasant surprises
- `4` = Strong discovery of exciting tracks
- `5` = Exceptional, eye-opening discoveries

### 5.3 Flow & Coherence (1–5 Likert)
> *"How smooth and musically coherent is the transition from one track to the next throughout the playlist?"*
- `1` = Jarring, erratic transitions
- `2` = Noticeably disjointed
- `3` = Acceptable transitions
- `4` = Smooth, engaging progression
- `5` = Masterful narrative and energy flow

### 5.4 Satisfaction (1–5 Likert)
> *"Overall, how satisfied are you with this playlist as a listening experience?"*
- `1` = Very dissatisfied
- `2` = Somewhat dissatisfied
- `3` = Neutral
- `4` = Satisfied
- `5` = Delighted

### 5.5 Forced-Choice Preference
> *"Which playlist did you prefer overall?"*
- `[ ] Playlist A`
- `[ ] Playlist B`
- `[ ] About Equal / No Preference`

### 5.6 Qualitative Feedback (Optional)
> *"Any thoughts on what worked well or what was missing?"* (Free text, max 1000 characters).

---

## 6. Ethics, Privacy & Consent Copy

Melovia is built upon strict privacy-by-design principles:
- **Zero Personal Data**: No email, name, IP address, or account credentials are collected.
- **Anonymous Session Identifiers**: Devices are identified only by a one-way cryptographically salted SHA-256 hash.
- **Participant Consent Notice**:
  > *"Participation in this study is completely anonymous and voluntary. Your ratings help evaluate algorithmic music discovery. No personal information is requested, stored, or shared. You may close the study at any time."*

---

## 7. Statistical Analysis Pipeline

Ratings are analyzed using `eval/study_analysis.py`:
1. **Paired Differences**: $D_i = X_{\text{Hybrid}, i} - X_{\text{Baseline}, i}$ for each participant $i$.
2. **Parametric Test**: Paired Student's t-test (`scipy.stats.ttest_rel`).
3. **Non-Parametric Test**: Wilcoxon signed-rank test (`scipy.stats.wilcoxon`) to robustly account for ordinal Likert properties.
4. **95% Bootstrap Confidence Intervals**: 1,000 resamples for the mean difference $\Delta$.
5. **Preference Ratio**: Proportions of Hybrid win, Baseline win, and Ties with binomial confidence intervals.
