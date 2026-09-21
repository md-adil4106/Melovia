# ADR 004: Framework-Agnostic Deterministic Recsys Core (`api/app/recsys/*`)

## Status
Accepted

## Date
2026-09-18

---

## Context
Recommendation logic in web services is frequently coupled with database models, HTTP request handlers, and caching frameworks. This leads to:
1. Sluggish test suites that require spinning up databases or mock HTTP contexts just to test matrix multiplications.
2. Nondeterministic recommendation outputs caused by unseeded RNG calls or undefined database ordering.
3. Difficulties in offline scientific evaluation, benchmarking, and cross-platform verification.

## Decision
All recommendation algorithms (`taste`, `candidates`, `scoring`, `rerank`, `sequencing`, `explain`, `blindspots`) are confined to `api/app/recsys/*` under strict rules:
1. **Pure Python**: Zero imports of FastAPI, Starlette, SQLAlchemy, psycopg, or database drivers. Only scientific computing libraries (NumPy, SciPy) and standard library modules are permitted.
2. **Strict Determinism**:
   - Every pseudo-random operation must accept an explicit, seeded `np.random.Generator` instance (default SEED=42).
   - Tie-breaking must be strictly stable based on `track_id`.
3. **Stage Independence**: Each pipeline stage is independently runnable and testable in isolation using unit tests and fixed fixtures.

## Consequences
### Positive
- Sub-millisecond unit test execution: over 200 tests complete in seconds without external services.
- Deterministic reproducibility: every CI build produces bit-for-bit identical recommendation rankings given the same seed.
- High portability: algorithms can be reused in offline batch evaluation scripts (`eval/runner.py`) without modifying code.

### Negative
- Database records must be converted into plain dictionaries or NumPy arrays before passing them into recsys functions.
- Developers must maintain disciplined separation and avoid shortcut imports from the FastAPI app layer.
