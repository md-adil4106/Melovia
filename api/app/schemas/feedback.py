"""Pydantic schemas for feedback, profile persistence, and portable export."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendations import RecommendedTrackItem


class FeedbackEventRequest(BaseModel):
    """Payload for submitting user interaction feedback."""

    track_id: str = Field(
        ..., min_length=1, max_length=50, description="Catalog track ID that received feedback"
    )
    event: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "Interaction type: 'like', 'dislike', 'skip', 'save', 'replay', 'add', 'remove'"
        ),
    )
    candidate_set_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional active candidate set ID to rerank immediately",
    )

    model_config = ConfigDict(extra="forbid")


class FeedbackResponse(BaseModel):
    """Response returned after applying feedback to live taste modes."""

    status: str = Field("ok", description="Status string")
    event: str = Field(..., description="Applied interaction event type")
    track_id: str = Field(..., description="Target track ID")
    mode_shifted: bool = Field(..., description="Whether a taste mode was shifted")
    nearest_mode_idx: int | None = Field(None, description="Index of nearest mode that was updated")
    cosine_shift: float | None = Field(
        None, description="Cosine similarity of mode before and after update"
    )
    candidate_set_id: str | None = Field(None, description="Active candidate set ID if reranked")
    items: list[RecommendedTrackItem] = Field(
        default_factory=list, description="Updated recommendations list"
    )
    applied_negatives_count: int = Field(
        0, description="Total number of actively excluded negative tracks"
    )

    model_config = ConfigDict(extra="forbid")


class ProfileStatusResponse(BaseModel):
    """Summary status of whether an anonymous persistent profile exists."""

    has_profile: bool = Field(..., description="Whether persistent profile exists on device")
    device_id_hash: str = Field(..., description="Hashed device ID (truncated SHA-256)")
    num_modes: int = Field(0, description="Number of persistent taste modes")
    known_tracks_count: int = Field(0, description="Number of tracks in known history")
    updated_at: datetime | None = Field(None, description="Timestamp of last profile update")

    model_config = ConfigDict(extra="forbid")


class ProfileRememberResponse(BaseModel):
    """Response returned when session modes are merged into persistent profile."""

    status: str = Field("ok", description="Status confirmation")
    device_id_hash: str = Field(..., description="Hashed device ID (truncated SHA-256)")
    num_modes: int = Field(..., description="Number of persistent taste modes after merge")
    known_tracks_count: int = Field(..., description="Number of tracks in known history")
    updated_at: datetime = Field(..., description="Timestamp of profile merge")

    model_config = ConfigDict(extra="forbid")


class ProfileExportResponse(BaseModel):
    """Portable JSON schema representation of the user's taste profile."""

    schema_version: str = Field("1.0.0", description="Portable taste profile schema version")
    device_id_hash: str = Field(..., description="Hashed anonymous device ID")
    persistent_modes: dict[str, Any] = Field(
        ..., description="Serialized multi-modal taste representations"
    )
    known_track_ids: list[str] = Field(
        default_factory=list, description="List of track IDs known to profile"
    )
    created_at: datetime = Field(..., description="Profile creation timestamp")
    updated_at: datetime = Field(..., description="Profile update timestamp")

    model_config = ConfigDict(extra="forbid")
