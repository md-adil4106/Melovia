"""Recommendation System Core (Pure Python, Deterministic).

Architecture Constraints:
- Zero imports of FastAPI, Starlette, SQLAlchemy, or DB drivers.
- Strict determinism (seeded RNG, stable tie-breaks by track_id).
- Independent stages: taste, candidates, scoring, rerank, sequencing, explain.
"""

__all__: list[str] = []
