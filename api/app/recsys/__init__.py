"""Recommendation System Core (Pure Python, Deterministic).

Architecture Constraints:
- Zero imports of FastAPI, Starlette, SQLAlchemy, or DB drivers.
- Strict determinism (seeded RNG, stable tie-breaks by track_id).
- Independent stages: taste, candidates, scoring, rerank, sequencing, explain.
"""

from app.recsys.baselines import (
    genre_baseline,
    random_baseline,
    single_channel_a_baseline,
    single_channel_t_baseline,
)
from app.recsys.cache import CandidateCache, global_candidate_cache
from app.recsys.candidates import CandidateFilters, CandidatePool, generate_candidates
from app.recsys.catalog import (
    CatalogCorruptError,
    CatalogError,
    CatalogNotFoundError,
    CatalogStore,
)
from app.recsys.config import RecsysConfig
from app.recsys.explain import ExplanationBuilder, ExplanationReason
from app.recsys.rerank import rerank_candidates
from app.recsys.scoring import ScoredItem, ScoredList, score_candidates
from app.recsys.taste import Modes, RecsysError, SeedNotFoundError, build_modes

__all__ = [
    "CatalogCorruptError",
    "CatalogError",
    "CatalogNotFoundError",
    "CatalogStore",
    "RecsysConfig",
    "RecsysError",
    "SeedNotFoundError",
    "Modes",
    "build_modes",
    "CandidateFilters",
    "CandidatePool",
    "generate_candidates",
    "ScoredItem",
    "ScoredList",
    "score_candidates",
    "rerank_candidates",
    "ExplanationBuilder",
    "ExplanationReason",
    "CandidateCache",
    "global_candidate_cache",
    "random_baseline",
    "genre_baseline",
    "single_channel_t_baseline",
    "single_channel_a_baseline",
]
