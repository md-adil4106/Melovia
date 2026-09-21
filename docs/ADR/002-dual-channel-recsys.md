# ADR 002: Dual-Channel Orthogonal Representations (Semantic vs Acoustic)

## Status
Accepted

## Date
2026-09-19

---

## Context
Commercial music recommenders typically project all metadata, audio, and user co-listen signals into a single uninterpretable latent vector space. This single-embedding paradigm suffers from several fatal flaws in steerable discovery:
1. **Conflation of Sonic and Cultural Properties**: A fast-tempo metal track and a slow folk track might cluster together simply because they share an underground scene tag or overlapping listener demographic.
2. **Loss of Fine-Grained Steerability**: Users cannot adjust their desire for sonic familiarity independently from their appetite for lyrical or subcultural novelty.
3. **Imputation Hazards**: Tracks lacking audio analysis cannot participate fairly unless unmeasured audio features are synthetically imputed, creating hallucinated acoustic recommendations.

## Decision
We decouple track representation into **two orthogonal channels**:
1. **Semantic Taste Space ($t \in \mathbb{R}^{128}$)**: Derived from folksonomy tags, genre ontologies, and artist descriptors via Sentence-Transformers (`all-MiniLM-L6-v2`) and PCA reduction.
2. **Acoustic Descriptor Space ($a \in \mathbb{R}^{K}$)**: Derived from standardized low- and high-level audio features (tempo, energy, valence, danceability, acousticness, instrumentalness, loudness).

### Invariants Enforced:
- Tracks lacking audio analysis have `has_a = False`, strictly zero vector rows $\mathbf{v}_a = \mathbf{0}$, and a boolean mask `mask_a[i] == False`.
- Zero silent imputation: missing audio is never fabricated.
- Multi-modal scoring uses smooth-max aggregation with dynamic channel gating ($\gamma$).

## Consequences
### Positive
- Users can steer familiarity vs discovery with predictable mathematical responses.
- Explanations can cleanly attribute recommendations to tag affinity vs acoustic similarity.
- Missing audio tracks participate gracefully in semantic retrieval without corrupting acoustic neighbors.

### Negative
- Requires maintaining two separate vector matrices and indexing structures.
- Multi-modal scoring requires calibration weighting between disparate vector spaces.
