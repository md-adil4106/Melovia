# ADR 001: Catalog Architecture Plan (Plan A vs Plan B Gate)

## Status
Accepted (Defaulting to Deterministic Mock Catalog for Phase 1 development; Plan B path selected for real-world fallback).

## Date
2026-09-19

---

## Context

Melovia requires a music catalog with three key representations:
1. **Relational Metadata**: Track title, artist, release year, ISRCs, source platform identifiers, and popularity metrics.
2. **Taste & Tag Embeddings ($t$-space)**: High-dimensional semantic vectors encoding genre, style, and acoustic mood descriptors derived from controlled tag vocabularies.
3. **Acoustic Audio Embeddings ($a$-space)**: High-dimensional audio spectral and timbral vectors extracted from actual audio waveforms.

Two primary architectural options were evaluated:

### Plan A: Open Music Ecosystem (MusicBrainz + ListenBrainz + AcousticBrainz)
- **Entities & Metadata**: MusicBrainz Core (CC0).
- **Popularity Signals**: ListenBrainz API / Listen dumps (CC0).
- **Acoustic Features**: AcousticBrainz archive dump (~900–1000 GB, CC0).
- **Strengths**: 100% open identifiers (MBIDs), extensive track catalog, zero platform lock-in.
- **Vulnerabilities**:
  - AcousticBrainz permanently ceased accepting new submissions in 2022. Any tracks released after 2022 have 0% coverage.
  - The raw AcousticBrainz dump is ~1 TB compressed, creating substantial infrastructure overhead.
  - MusicBrainz live API rate limit is strictly 1 req/s, necessitating local replication.

### Plan B: Open Audio Feature Extraction (Free Music Archive + Essentia Extraction)
- **Audio & Metadata**: Free Music Archive (FMA `fma_medium` or `fma_small`, CC BY 4.0).
- **Features**: Local offline feature extraction using Essentia / librosa (tempo, MFCCs, spectral contrast, chroma, tonnetz) directly from audio.
- **Strengths**: 100% guaranteed audio availability, full control over feature extraction pipelines, completely consistent embedding dimensionality.
- **Vulnerabilities**: Catalog limited to independent/CC-licensed tracks; commercial chart recordings cannot be hosted directly.

---

## Decision Gate Criteria

Plan A proceeds to production ingestion **only if** a sample of popular recordings meets the following quantitative thresholds:
- **AcousticBrainz Audio Coverage**: $\ge 40.0\%$
- **Tag / Folksonomy Genre Coverage**: $\ge 70.0\%$ (recording-level tags with artist/release-group fallback)
- **ISRC Presence**: Recorded for streaming platform cross-referencing.

If these thresholds are not satisfied, or if dump acquisition is blocked by bandwidth/infrastructure constraints, the system activates **Plan B** for open audio and defaults to the **Deterministic Mock Catalog** (`data/bundles/v1`) for core recsys algorithm verification.

---

## Probe Analysis & Measurements

Using `pipelines/probe_coverage.py` on a sample of popular historical and contemporary recordings (representing chart-toppers across decades):

| Metric | Sample Value | Required Gate Threshold | Gate Status |
| --- | --- | --- | --- |
| **AcousticBrainz Coverage** | **35.0%** | $\ge 40.0\%$ | **FAILED** |
| **Tag / Genre Coverage (with fallback)** | **85.0%** | $\ge 70.0\%$ | **PASSED** |
| **ISRC Coverage** | **90.0%** | Informational | Informational |

### Key Observations
1. **AcousticBrainz Recency Drop-off**: For pre-2020 classics (e.g., Pink Floyd, Daft Punk, Radiohead), AcousticBrainz coverage was ~75%. For post-2020 tracks (e.g., Dua Lipa, recent Kendrick Lamar), coverage dropped to **0%**, pulling the overall sample average down to 35.0%.
2. **Tag Fallback Efficacy**: While recording-level folksonomy tags are sparse on newer entries (~45%), falling back to artist-level tags boosted total genre/tag coverage to 85.0%.
3. **Dump Prohibitive Size**: The 900+ GB AcousticBrainz archive cannot be feasibly downloaded or synchronized in rapid development environments.

---

## Decision

1. **Gate Outcome**: Plan A fails the $\ge 40\%$ AcousticBrainz coverage threshold due to the post-2022 submission freeze.
2. **Execution Strategy**:
   - **Phase 1 Baseline**: Build and lock the **Deterministic Mock Catalog** (`data/bundles/v1`) with 3,000 tracks, 12 planted musical regions, realistic tags, and long-tail popularity.
   - **Missing-Channel Invariant**: Implement missing-channel masks (`mask_a`, `mask_t`) so the recommender engine is mathematically resilient to tracks lacking audio or taste vectors (e.g., exactly 5% missing audio in the mock bundle).
   - **Long-term Real-Data Path**: Adopt **Plan B** principles (local feature extraction via Essentia on openly accessible datasets or audio previews) rather than relying on legacy AcousticBrainz dumps.

---

## Consequences

### Positive
- Recommendation engine algorithms can be tested with 100% deterministic reproducibility without downloading gigabytes of external data.
- The pipeline architecture natively handles missing audio vectors via `has_a` masks, ensuring graceful degradation across heterogeneous catalogs.
- Zero risk of rate-limiting or service disruptions during automated CI test suites.

### Negative
- Real-world popular track audio vectors require a dedicated feature extraction pipeline in later phases.
- Real-world MusicBrainz tag usage remains under CC BY-NC-SA 3.0 license terms, requiring proper attribution.
