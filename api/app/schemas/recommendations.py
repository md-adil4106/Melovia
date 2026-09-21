"""Pydantic schemas for recommendation requests and responses."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.signals import RecSignals
from app.schemas.tracks import TrackDetailResponse


class RecommendationRequest(BaseModel):
    """Payload for generating recommendations from seed tracks."""

    seed_track_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="List of 1 to 10 seed track UUIDs to base recommendations on",
    )
    use_saved_taste: bool = Field(
        default=False,
        description="Whether to use the persistent profile taste modes as the initial taste",
    )
    n: int = Field(
        default=30,
        ge=1,
        le=50,
        description="Number of recommended tracks to return (1 to 50, default 30)",
    )
    excluded_artist_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Optional list of up to 50 artist UUIDs to exclude from recommendations",
    )
    include_signals: bool = Field(
        default=True,
        description="Whether to include intermediate ranking signals in the response",
    )
    discovery: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Discovery level between 0.0 (pure familiarity) and 1.0 (maximum discovery)",
    )
    region_id: int | None = Field(
        default=None,
        description="Optional region ID to explore and restrict candidates within",
    )

    @model_validator(mode="after")
    def check_seeds_or_saved_taste(self) -> "RecommendationRequest":
        if not self.use_saved_taste and not self.seed_track_ids:
            raise ValueError(
                "At least 1 seed track ID must be provided when use_saved_taste is false."
            )
        return self


class RerankRequest(BaseModel):
    """Payload for reranking a cached candidate pool using Discovery Control."""

    candidate_set_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="UUID of cached candidate pool to rerank",
    )
    discovery: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Discovery level between 0.0 (pure familiarity) and 1.0 (maximum discovery)",
    )
    n: int = Field(
        default=30,
        ge=1,
        le=50,
        description="Number of reranked tracks to return (1 to 50, default 30)",
    )
    include_signals: bool = Field(
        default=True,
        description="Whether to include intermediate reranking signals in the response",
    )


class WhyExplanationReason(BaseModel):
    """An individual signal-grounded reason explaining why a track was recommended."""

    id: str = Field(..., description="Unique rule identifier that triggered this reason")
    text: str = Field(..., description="Human-readable explanation sentence")
    signal_keys: list[str] = Field(
        ..., description="List of named RecSignals fields backing this explanation sentence"
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Concrete numeric and factual values used to evaluate the rule",
    )
    weight: float = Field(..., description="Dynamic salience weight of this reason")


class RecommendedTrackItem(BaseModel):
    """An individual recommended track item with ranking score and explanation signals."""

    track: TrackDetailResponse = Field(..., description="Complete metadata for recommended track")
    score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized multi-channel relevance score"
    )
    discovery_value: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Lightweight discovery score in [0, 1]",
    )
    signals: RecSignals | dict[str, Any] | None = Field(
        default=None,
        description="Detailed similarity and percentile signals across channels",
    )
    reasons: list[WhyExplanationReason] | None = Field(
        default=None,
        description="Optional top 3-4 reasons explaining this recommendation",
    )


class RecommendationResponse(BaseModel):
    """Response payload containing ranked track recommendations and cached candidate set ID."""

    candidate_set_id: str = Field(
        ...,
        description="UUID of cached candidate pool for fast interactive steering and re-ranking",
    )
    total_candidates: int = Field(
        ...,
        description="Total candidates retrieved before top-N truncation",
    )
    items: list[RecommendedTrackItem] = Field(
        default_factory=list,
        description="Ranked list of recommended tracks",
    )


class WhyExplanationResponse(BaseModel):
    """Full explainability payload detailing why a specific track was recommended."""

    candidate_set_id: str = Field(..., description="Candidate pool UUID")
    track_id: str = Field(..., description="Track UUID being explained")
    reasons: list[WhyExplanationReason] = Field(
        ..., description="Top 3-4 signal-backed explanation sentences"
    )
    signals: RecSignals = Field(..., description="Full numeric ranking signals")
    discovery_value: float = Field(
        ..., ge=0.0, le=1.0, description="Effective discovery level when explained"
    )
    llm_polished: bool = Field(
        default=False,
        description="True if sentence phrasing was styled by the optional verified LLM polish",
    )
