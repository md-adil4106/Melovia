"""Recommendation System Core (Pure Python, Deterministic).

Architecture Constraints:
- Zero imports of FastAPI, Starlette, SQLAlchemy, or DB drivers.
- Strict determinism (seeded RNG, stable tie-breaks by track_id).
- Independent stages: taste, candidates, scoring, rerank, sequencing, explain.
"""

from app.recsys.archetypes import (
    ARCHETYPE_CATALOG,
    ArchetypeDefinition,
    ArchetypeMatchResult,
    determine_archetype,
)
from app.recsys.baselines import (
    genre_baseline,
    random_baseline,
    single_channel_a_baseline,
    single_channel_t_baseline,
)
from app.recsys.blindspots import BlindspotRegion, detect_blindspots
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
from app.recsys.feedback import (
    FeedbackResult,
    apply_feedback,
    merge_modes,
    modes_from_dict,
    modes_to_dict,
)
from app.recsys.profile_metrics import (
    DimensionScore,
    MusicDNA,
    TasteProfileResult,
    compute_taste_profile,
)
from app.recsys.rerank import rerank_candidates
from app.recsys.scoring import ScoredItem, ScoredList, score_candidates
from app.recsys.sequencing import (
    ArcPoint,
    ArcType,
    PlaylistSequenceResult,
    TransitionCostItem,
    generate_arc_target,
    sequence_playlist,
)
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
    "FeedbackResult",
    "apply_feedback",
    "merge_modes",
    "modes_from_dict",
    "modes_to_dict",
    "ArcType",
    "ArcPoint",
    "PlaylistSequenceResult",
    "TransitionCostItem",
    "generate_arc_target",
    "sequence_playlist",
    "DimensionScore",
    "MusicDNA",
    "TasteProfileResult",
    "compute_taste_profile",
    "ArchetypeDefinition",
    "ArchetypeMatchResult",
    "determine_archetype",
    "ARCHETYPE_CATALOG",
    "BlindspotRegion",
    "detect_blindspots",
]
