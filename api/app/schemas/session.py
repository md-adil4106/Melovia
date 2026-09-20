"""Session schemas for conversational refinement and constraint tracking.

Architecture Constraints:
- Applied constraints are user-visible, human-readable chips.
- Utterances are strictly capped at 300 characters.
- Anonymous session identification via cookie or header.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.recommendations import RecommendedTrackItem


class AppliedConstraint(BaseModel):
    """User-facing active constraint representation for chips UI."""

    id: str = Field(..., description="Unique identifier for undo operations")
    label: str = Field(..., description="Short human-readable label (e.g., 'Energy +50%')")
    type: str = Field(
        ...,
        description=(
            "Constraint category ('knob', 'boost_tag', 'suppress_tag', 'popularity_ceiling', 'arc')"
        ),
    )
    value: Any = Field(..., description="Underlying constraint value")
    utterance: str = Field(..., description="User utterance that triggered this constraint")
    created_at: float = Field(..., description="Unix timestamp of creation")


class RefineRequest(BaseModel):
    """Request payload for conversational refinement."""

    session_id: str | None = Field(
        default=None, description="Active session ID (if omitted, created from cookie/new UUID)"
    )
    candidate_set_id: str = Field(
        ..., description="ID of the cached candidate set to refine and re-rank"
    )
    utterance: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Natural language refinement intent (max 300 characters)",
    )


class RefineResponse(BaseModel):
    """Response payload containing re-ranked recommendations and applied constraint chips."""

    session_id: str = Field(..., description="Current session ID")
    candidate_set_id: str = Field(..., description="Candidate set ID")
    applied: list[AppliedConstraint] = Field(
        default_factory=list,
        description="All currently active applied constraints for this session",
    )
    unsupported: list[str] = Field(
        default_factory=list, description="Unsupported aspects or vocabulary gaps in plain language"
    )
    items: list[RecommendedTrackItem] = Field(
        default_factory=list, description="Re-ranked recommended tracks"
    )
    clarify: str | None = Field(
        default=None, description="Optional clarification guidance or message"
    )


class SessionResetResponse(BaseModel):
    """Response payload for resetting session context."""

    status: str = Field(default="ok")
    session_id: str = Field(..., description="Reset session ID")
