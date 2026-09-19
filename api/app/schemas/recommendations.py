"""Pydantic schemas for recommendation requests and responses."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.tracks import TrackDetailResponse


class RecommendationRequest(BaseModel):
    """Payload for generating recommendations from seed tracks."""

    seed_track_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of 1 to 10 seed track UUIDs to base recommendations on",
    )
    n: int = Field(
        default=30,
        ge=1,
        le=50,
        description="Number of recommended tracks to return (1 to 50, default 30)",
    )
    excluded_artist_ids: list[str] = Field(
        default_factory=list,
        description="Optional list of artist UUIDs to exclude from recommendations",
    )
    include_signals: bool = Field(
        default=True,
        description="Whether to include intermediate ranking signals in the response",
    )


class RecommendedTrackItem(BaseModel):
    """An individual recommended track item with ranking score and explanation signals."""

    track: TrackDetailResponse = Field(..., description="Complete metadata for recommended track")
    score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized multi-channel relevance score"
    )
    signals: dict[str, Any] | None = Field(
        default=None,
        description="Detailed similarity and percentile signals across channels",
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
