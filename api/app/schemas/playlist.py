"""Pydantic schemas for playlist sequencing requests and responses."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.recsys.sequencing import ArcType
from app.schemas.recommendations import RecommendedTrackItem


class PlaylistSequenceRequest(BaseModel):
    """Payload for requesting arc-aware playlist sequencing."""

    model_config = ConfigDict(extra="forbid")

    candidate_set_id: str | None = Field(
        default=None,
        description="UUID of cached candidate pool to pull tracks from",
    )
    track_ids: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Explicit list of track UUIDs to sequence",
    )
    arc: ArcType = Field(
        default=ArcType.BUILD,
        description="Target energy progression arc ('steady', 'build', 'wave', 'wind_down')",
    )
    length: int = Field(
        default=15,
        ge=2,
        le=50,
        description="Target playlist length (2 to 50 tracks)",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID to pull active steering/refinement context",
    )

    @model_validator(mode="after")
    def validate_source(self) -> "PlaylistSequenceRequest":
        if not self.candidate_set_id and not self.track_ids:
            raise ValueError(
                "Either 'candidate_set_id' or 'track_ids' must be provided for sequencing."
            )
        return self


class TransitionDetail(BaseModel):
    """Detailed transition diagnostics between consecutive tracks."""

    from_track_id: str = Field(..., description="Source track UUID")
    to_track_id: str = Field(..., description="Target track UUID")
    tempo_delta: float | None = Field(default=None, description="Absolute tempo difference")
    energy_delta: float | None = Field(default=None, description="Absolute energy difference")
    semantic_distance: float = Field(..., description="Semantic cosine distance (1 - cos_t)")
    same_artist: bool = Field(..., description="Whether both tracks share the same artist")
    cost: float = Field(..., description="Computed composite hop cost")


class ArcDataPoint(BaseModel):
    """Target and realized energy at a specific sequence position."""

    position: int = Field(..., ge=0, description="0-indexed position in playlist")
    normalized_pos: float = Field(..., ge=0.0, le=1.0, description="Normalized position in [0, 1]")
    target_energy: float = Field(..., ge=0.0, le=1.0, description="Target energy on arc curve")
    realized_energy: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Realized track energy index"
    )
    track_id: str = Field(..., description="UUID of track placed at this position")


class PlaylistSequenceResponse(BaseModel):
    """Response containing sequenced tracks, transition breakdowns, and arc points."""

    tracks: list[RecommendedTrackItem] = Field(
        default_factory=list, description="Sequenced tracks in optimal listening order"
    )
    transitions: list[TransitionDetail] = Field(
        default_factory=list, description="Per-hop transition metrics"
    )
    arc_points: list[ArcDataPoint] = Field(
        default_factory=list, description="Arc progression points for visualization"
    )
    total_cost: float = Field(..., description="Total composite playlist objective cost")
    mean_transition_cost: float = Field(..., description="Average transition cost per hop")
    arc_correlation: float = Field(
        ..., description="Pearson correlation between target arc and realized energy"
    )
    active_weights: dict[str, float] = Field(
        default_factory=dict, description="Active cost weights after auto-drop checks"
    )
    dropped_features: list[str] = Field(
        default_factory=list, description="Features excluded due to coverage < threshold"
    )
