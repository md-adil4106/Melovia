# Changelog

All notable changes to the Melovia project are documented in this file.
The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and [Conventional Commits](https://www.conventionalcommits.org/).

---

## [1.0.0] — 2026-09-21

### Portfolio-Grade Release & Phase 16 Complete
- **Documentation & Open Source Polish**:
  - Authored comprehensive [`README.md`](README.md) with architectural diagrams, feature tours, quickstarts, and honest limitation disclosures.
  - Published [`docs/DATA_CARD.md`](docs/DATA_CARD.md) and [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) detailing dataset provenance, heuristic proxy definitions, and known biases.
  - Created [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) detailing a rehearsed 5-minute walkthrough across all 6 WOW moments with 3 tested seed sets and multi-tier fallbacks.
  - Published [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) and [`docker-compose.prod.yml`](docker-compose.prod.yml) covering Vercel, Render/Fly.io, and self-hosted production setups with startup bundle checksum verification.
  - Established formal Architectural Decision Records in [`docs/ADR/`](docs/ADR/).
  - Added MIT [`LICENSE`](LICENSE), [`CONTRIBUTING.md`](CONTRIBUTING.md), and GitHub issue templates.

---

## [0.15.0] — 2026-09-21

### Phase 15 — UX Polish, Onboarding & Study Mode
- **Design System**: Reusable primitives in `web/src/app/components/ui/` (`Button`, `Card`, `Chip`, `Slider`, `Drawer`, `Tooltip`, `Skeleton`, `EmptyState`, `ErrorState`, `Toast`) adhering to dark ink palette (`#090b10`) and motion tokens ($\le 300\text{ ms}$).
- **Landing & Onboarding**: Ambient 2D point-field canvas background (`HeroParticleField.tsx`, respecting `prefers-reduced-motion`); dismissible and remembered 3-step first-run hint; curated seed presets ("Night Drive", "Ambient Focus", "Cosmic Drift").
- **Taste-o-meter Polish**: "Describes, never ranks" philosophy; pure client-side HTML5 canvas "Share as Image" high-res PNG export ($1200\times 630\text{ px}$, zero server upload, zero telemetry, zero PII).
- **Double-Blind Study Mode (`/study`)**: Randomized A/B evaluation trial (System Hybrid vs Baseline); 1–5 Likert scales for Relevance, Discovery, Flow, Satisfaction + forced choice preference; token-protected CSV export (`STUDY_ADMIN_TOKEN`); statistical analysis script (`eval/study_analysis.py`); scientific protocol doc (`docs/STUDY_PROTOCOL.md`).

---

## [0.14.0] — 2026-09-21

### Phase 14 — Hardening (Security, Performance, Reliability)
- **Security & Validation**: Strict Pydantic input bounds, standardized token-bucket rate limiting on search/feedback/refine/export, security headers middleware (CSP, nosniff, DENY, strict-origin), and dynamic production cookie security.
- **Reliability & Resilience**: Database failure resilience with graceful fallback to in-memory session mode; WebGL context crash protection via `UniverseErrorBoundary`. Uniform error envelope `{error: {code, message, request_id}}`.
- **Observability**: Request metrics tracker with p50/p95 latency and memory monitoring under `GET /health/details`.
- **Load Testing**: 20 concurrent user load harness (`scripts/load_test.py`) with 700 transactions and 0.00% error rate. Zero-secret verification via full Git history scanner (`scripts/scan_secrets_history.py`).

---

## [0.13.0] — 2026-09-21

### Phase 13 — Platform Export
- **File Export**: 100% offline generation of CSV, JSPF JSON, Extended M3U, and Plain Text track lists.
- **Spotify Platform Adapter**: OAuth 2.0 PKCE flow with loopback redirect (`127.0.0.1`), batch track insertion, rate limit handling, and session-only token storage.
- **Track Matching Pipeline**: Two-stage cascade matching (exact ISRC search $\to$ fuzzy title + artist fallback) with result caching.

---

## [0.12.0] — 2026-09-21

### Phase 12 — Blindspot Detection & Musical Horizons (WOW #5)
- **Blindspot Analyzer**: Mathematical detection of unrepresented catalog regions with soft Gaussian coverage decay ($e^{-d^2 / (2\sigma^2)}$).
- **Bridging Recommendations**: Discovery of transitional tracks linking user taste centroids to uncharted musical horizons.
- **Frontend Horizon Explorer**: Interactive UI visualizing unexplored clusters and sample gateway tracks.

---

## [0.11.0] — 2026-09-21

### Phase 11 — Dynamic Taste Profile & Visual DNA
- **Multi-Centroid Taste Profile**: Incremental taste modeling aggregating user interactions into weighted Gaussian centroids.
- **Acoustic Radar & Genre DNA**: Polar visualization of energy, valence, acousticness, danceability, and dominant folksonomy tags.
- **Cookie-Based Anonymous Persistence**: Pure client-driven profile synchronization across sessions without mandatory user registration.

---

## [0.10.0] — 2026-09-20

### Phase 10 — Conversational Refinement & Steering (WOW #4)
- **Session Context Steering**: Natural language prompt parsing converting user requests into structured vector shifts and scalar target modifiers.
- **Verifier Guard**: Validation pipeline guaranteeing LLM constraints use only catalog-grounded tags and achievable scalar ranges.
- **Reversible History**: In-memory session steering stack allowing step-by-step undo and reset.

---

## [0.9.0] — 2026-09-20

### Phase 9 — In-Session Feedback Adaptation
- **Real-Time Taste Steering**: Lightweight weight adjustments ($\eta=0.08$) and dampening ($\delta=0.15$) for in-session likes, dislikes, and skips.
- **Candidate Pool Recalibration**: Instant re-ranking of active playlists reflecting real-time listener feedback without re-fetching entire catalogs.

---

## [0.8.0] — 2026-09-20

### Phase 8 — Explainability Engine & "Why This Track?" (WOW #3)
- **Signal-True Explanations**: Attribution engine extracting mathematical ranking contributions (cosine similarity, audio alignment, novelty boost, MMR diversity).
- **Explanation Rule Table**: Deterministic template engine mapping ranking signals to human-readable explanations.
- **Why Drawer**: Interactive UI slide-out showing exact feature radar, signal breakdowns, and anchor seeds.

---

## [0.7.0] — 2026-09-20

### Phase 7 — Playlist Sequencing & Cohesion
- **Smooth Audio Transitions**: Traveling Salesperson Problem (TSP) 2-opt trajectory solver minimizing pairwise acoustic jump distances.
- **Energy Arc Shaping**: Dynamic curve matching (Rising, Peaking, Storyteller, Chill Plateau) with hard artist adjacency caps ($k \ge 2$).

---

## [0.6.0] — 2026-09-20

### Phase 6 — 3D Interactive Taste Universe (WOW #2)
- **Three.js / React Three Fiber Constellation**: 3D interactive particle cloud visualizing catalog tracks.
- **Strict Architectural Invariant**: *"3D map visualizes, high-dimensional vectors decide."* True 256d vector nearest neighbors shown in inspection cards.
- **Inverse-Distance Weighted Embedding**: Deterministic $k=10$ interpolation for placing arbitrary user taste modes in 3D space.

---

## [0.5.0] — 2026-09-20

### Phase 5 — Steerable Discovery Slider (WOW #1)
- **Gaussian Novelty Shaping**: Discovery parameter $d \in [0.0, 1.0]$ governing target similarity radius, dynamic relevance floors, and MMR penalties.
- **Sub-100ms Re-Ranking**: Instant client-side slider response utilizing in-memory candidate pool caches.

---

## [0.4.0] — 2026-09-19

### Phase 4 — Core Recommender Engine v1 (Level A)
- **Dual-Channel Multi-Modal Scoring**: Weighted combination of semantic tag space ($t$) and acoustic descriptor space ($a$).
- **Multi-Seed Taste Profiling**: K-means clustering of seed tracks with inverse-inertia weight assignment.
- **Missing Audio Handling**: Strict zero-vector invariant with boolean mask; zero silent imputation.

---

## [0.3.0] — 2026-09-19

### Phase 3 — Evaluation Framework & Methodology
- **Offline Evaluation Suite**: `eval/metrics.py` and `eval/runner.py` computing Intra-List Diversity (ILD), Novelty, Region Entropy, Coverage, and Gini coefficient.
- **Statistical Significance**: Paired bootstrap confidence intervals ($B=1,000$).
- **CI Regression Guards**: Deterministic automated quality gates verifying discovery monotonicity, diversity preservation, and ablation efficacy.

---

## [0.2.0] — 2026-09-19

### Phase 2 — Catalog Pipeline & Vector Bundles
- **Data Ingestion**: Multi-source ETL pipelines ingesting MusicBrainz, ListenBrainz, and AcousticBrainz datasets.
- **Vector Bundle Specification**: Versioned, immutable, checksummed artifacts (`tracks.parquet`, `scalars.parquet`, `vectors_t.npy`, `vectors_a.npy`, `manifest.json`).

---

## [0.1.0] — 2026-09-18

### Phase 0 & 1 — Foundation & Architecture
- Initial repository setup, FastAPI backend, Next.js 14 frontend, PostgreSQL 16 schema, Alembic migrations, unified Makefile, and standing rules in `AGENTS.md`.
