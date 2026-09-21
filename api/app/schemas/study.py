"""Pydantic schemas for blind A/B study mode (Phase 15).

Constraints:
- Response schemas for study trials must NEVER leak the recommendation arm (hybrid vs baseline).
- Strict validation on Likert ratings (1-5 range).
"""

from typing import Any

from pydantic import BaseModel, Field


class StudySeedTrack(BaseModel):
    """Seed track metadata displayed to study participants."""

    id: str
    track_idx: int
    title: str
    artist_name: str
    year: int | None = None


class StudySessionTrack(BaseModel):
    """Track item in a blind study playlist. Free of scores, ranks, and channel signals."""

    id: str
    track_idx: int
    title: str
    artist_name: str
    year: int | None = None
    popularity_pct: float = 50.0
    tags: list[Any] = Field(default_factory=list)


class StudySessionResponse(BaseModel):
    """Blind study trial session returning two anonymized candidate playlists."""

    session_id: str = Field(..., description="Unique trial session identifier")
    seed_set_id: str = Field(..., description="Identifier of the evaluation seed set")
    seed_set_name: str = Field(..., description="Human-readable seed set category")
    seed_tracks: list[StudySeedTrack] = Field(..., description="Reference seed tracks")
    playlist_a: list[StudySessionTrack] = Field(..., description="Blind Playlist A")
    playlist_b: list[StudySessionTrack] = Field(..., description="Blind Playlist B")


class StudyRatingRequest(BaseModel):
    """User evaluation submission for Playlist A and Playlist B."""

    session_id: str = Field(..., description="Session ID matching the study trial")
    relevance_a: int = Field(..., ge=1, le=5, description="Relevance rating for Playlist A (1-5)")
    discovery_a: int = Field(..., ge=1, le=5, description="Discovery rating for Playlist A (1-5)")
    flow_a: int = Field(..., ge=1, le=5, description="Flow rating for Playlist A (1-5)")
    satisfaction_a: int = Field(
        ..., ge=1, le=5, description="Satisfaction rating for Playlist A (1-5)"
    )

    relevance_b: int = Field(..., ge=1, le=5, description="Relevance rating for Playlist B (1-5)")
    discovery_b: int = Field(..., ge=1, le=5, description="Discovery rating for Playlist B (1-5)")
    flow_b: int = Field(..., ge=1, le=5, description="Flow rating for Playlist B (1-5)")
    satisfaction_b: int = Field(
        ..., ge=1, le=5, description="Satisfaction rating for Playlist B (1-5)"
    )

    preferred_overall: str = Field(
        ...,
        pattern="^(playlist_a|playlist_b|tie)$",
        description="Overall preferred playlist ('playlist_a', 'playlist_b', or 'tie')",
    )
    feedback_text: str | None = Field(
        None, max_length=1000, description="Optional qualitative impressions"
    )


class StudyRatingResponse(BaseModel):
    """Response confirmation after rating submission."""

    status: str = "ok"
    message: str
    rating_id: str


class StudyAdminExportItem(BaseModel):
    """Unblinded study record for admin research analysis."""

    rating_id: str
    session_id: str
    participant_id: str | None
    seed_set_id: str
    arm_order: str
    playlist_a_arm: str
    playlist_b_arm: str
    relevance_hybrid: int
    discovery_hybrid: int
    flow_hybrid: int
    satisfaction_hybrid: int
    relevance_baseline: int
    discovery_baseline: int
    flow_baseline: int
    satisfaction_baseline: int
    preferred_overall: str
    preferred_arm: str
    feedback_text: str | None
    created_at: str
