# Melovia Architecture Specification

## Overview

Melovia is an explainable, user-steerable music-discovery engine designed with strict modular separation, deterministic recommendation pipelines, and security-first boundaries.

---

## Architectural Boundaries

### 1. Recommendation System (`api/app/recsys/*`)
- **Pure Python**: Zero imports of FastAPI, Starlette, SQLAlchemy, or database drivers.
- **Strict Determinism**:
  - All pseudo-randomness must use explicit, seeded RNG instances.
  - Stable tie-breaking based on `track_id`.
- **Independently Testable Pipeline Stages**:
  - `taste`: Builds user taste profiles and representations.
  - `candidates`: Retrieval of candidate track sets from catalog embeddings.
  - `scoring`: Computes affinity scores between taste representation and candidates.
  - `rerank`: Applies steerability filters, novelty penalties, and diversity constraints.
  - `sequencing`: Sequences tracks into cohesive transitions.
  - `explain`: Generates attribution signals explaining why each track was chosen based strictly on ranking signals.

### 2. Large Language Models (`api/app/llm/*`)
- All LLM integration code is strictly confined to `api/app/llm/*`.
- **Structured Constraints Only**: LLM outputs must be validated against strict Pydantic schemas using controlled vocabularies (genres, descriptors, mood modifiers).
- **Prohibitions**:
  - The LLM **never** selects or ranks tracks directly.
  - The LLM **never** invents metadata or track attributes.
  - The LLM **never** writes ungrounded explanations; explanations must strictly derive from computed ranking signals.

### 3. Music Platforms (`api/app/platforms/*`)
- Confined behind `PlatformAdapter` interface:
  - `search_track(query: str) -> list[TrackMetadata]`
  - `get_metadata(platform_id: str) -> TrackMetadata`
  - `authenticate(code: str) -> AuthCredentials`
  - `create_playlist(user_id: str, title: str) -> PlaylistInfo`
  - `add_tracks(playlist_id: str, track_ids: list[str]) -> bool`
- **Zero Leakage**: No platform-specific models or types leak into `api/app/recsys/`.

### 4. Catalog & Vector Storage (`data/bundles/<version>/`)
- Stored as immutable, versioned, checksummed bundles.
- Recommendation decisions rely exclusively on high-dimensional vectors.
- 3D coordinates (e.g. UMAP / t-SNE) are strictly for visual representation in the client and never used in recommendation math.
- PostgreSQL 16 is used for relational user state and catalog metadata. **No Redis, No pgvector**.

### 5. Input Validation & Error Envelopes
- All external inputs (HTTP queries, LLM outputs, platform responses) are treated as untrusted and validated with Pydantic v2.
- No raw stack traces are returned to clients. All errors follow the uniform envelope:
  ```json
  {
    "error": {
      "code": "ERROR_CODE",
      "message": "Human-readable description",
      "request_id": "c1f7b029-478a-4952-bdae-5bf8c4bb1b59"
    }
  }
  ```
- Structured logging captures `request_id`, stage latencies, counts, and status codes while redacting sensitive tokens and personal data.

---

## Performance & Accessibility Budgets

- **Latency Budgets**:
  - `POST /recommendations`: p95 < 400 ms on the mock catalog.
  - Re-rank step: < 100 ms on the mock catalog.
- **Web Client**:
  - First-load JS: < 250 KB (excluding lazy-loaded 3D visualization chunks).
  - Accessibility: Keyboard operable, visible focus indicators, WCAG AA contrast, and universal respect for `prefers-reduced-motion`.

---

## Recommendation API & In-Memory Caching

### Endpoint: `POST /recommendations`
- **Request Body**:
  ```json
  {
    "seed_track_ids": ["track_0001", "track_0042"],
    "n": 30,
    "exclude_seed_artists": true,
    "include_signals": true
  }
  ```
- **Response**:
  ```json
  {
    "candidate_set_id": "sha256-hash-of-sorted-seeds",
    "items": [
      {
        "track": { "id": "...", "title": "...", "artist_name": "...", "popularity_pct": 82.5, "has_a": true, "has_t": true },
        "score": 0.942,
        "signals": { "raw_sim_t": 0.89, "percentile_t": 0.98, "raw_sim_a": 0.81, "percentile_a": 0.89, "has_audio": true }
      }
    ],
    "timing_ms": {
      "taste_modes_ms": 1.2,
      "candidate_gen_ms": 4.5,
      "scoring_ms": 2.1,
      "total_ms": 7.8
    }
  }
  ```

### In-Memory Candidate Pool Caching (`recsys/cache.py`)
- Candidate pools generated from identical seed sets are cached in-process using thread-safe TTL storage (30-minute expiry, max 1,000 entries).
- Subsequent steerability and reranking operations (Phase 5+) can reuse the precomputed candidate pool via `candidate_set_id`, avoiding redundant vector catalog scans.

