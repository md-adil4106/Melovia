"""Recommendation System Core (Pure Python, Deterministic).

Architecture Constraints:
- Zero imports of FastAPI, Starlette, SQLAlchemy, or DB drivers.
- Strict determinism (seeded RNG, stable tie-breaks by track_id).
- Independent stages: taste, candidates, scoring, rerank, sequencing, explain.
"""

from app.recsys.catalog import (
    CatalogCorruptError,
    CatalogError,
    CatalogNotFoundError,
    CatalogStore,
)

__all__ = [
    "CatalogCorruptError",
    "CatalogError",
    "CatalogNotFoundError",
    "CatalogStore",
]
