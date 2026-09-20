"""Pydantic schemas for Taste Profile, Music DNA, Archetypes, and Blindspots (Phase 11)."""

from pydantic import BaseModel, Field

from app.schemas.tracks import TrackDetailResponse


class DimensionResponse(BaseModel):
    name: str = Field(..., description="Human-readable dimension title")
    key: str = Field(..., description="Machine-readable dimension key")
    value: float = Field(..., ge=0.0, le=1.0, description="Normalized point estimate")
    percentile: float = Field(..., ge=0.0, le=100.0, description="Percentile vs catalog reference")
    ci_90: list[float] = Field(
        ..., min_length=2, max_length=2, description="90% bootstrap confidence interval"
    )
    description: str = Field(..., description="Brief dimension summary")
    definition_tooltip: str = Field(
        ..., description="Accessible tooltip explaining feature grounding"
    )


class ScalarSummary(BaseModel):
    mean: float = Field(..., description="Mean scalar value across known tracks")
    min: float = Field(..., description="Minimum scalar value")
    max: float = Field(..., description="Maximum scalar value")


class DominantTagItem(BaseModel):
    tag: str = Field(..., description="Controlled folksonomy tag")
    count: int = Field(..., description="Occurrences in known tracks")
    share: float = Field(..., description="Proportion of known tracks bearing this tag")


class RegionExposureItem(BaseModel):
    region_id: int = Field(..., description="Cluster region index")
    name: str = Field(..., description="Region display name")
    genre_focus: str = Field(..., description="Representative genres/styles")
    exposure: float = Field(..., ge=0.0, le=1.0, description="User's soft exposure share")


class MusicDNASchema(BaseModel):
    dominant_tags: list[DominantTagItem] = Field(
        default_factory=list, description="Top folksonomy tags"
    )
    mean_scalars: dict[str, ScalarSummary] = Field(
        default_factory=dict, description="Acoustic descriptor ranges"
    )
    dominant_regions: list[RegionExposureItem] = Field(
        default_factory=list, description="Top user regions"
    )


class ArchetypeResponse(BaseModel):
    id: str = Field(..., description="Canonical archetype ID")
    name: str = Field(..., description="Archetype title")
    tagline: str = Field(..., description="Short evocative summary")
    description: str = Field(..., description="Detailed, non-evaluative aesthetic description")
    criteria_summary: str = Field(
        ..., description="Mathematical condition triggering this archetype"
    )
    matched_rules: list[str] = Field(default_factory=list, description="Specific rules matched")
    is_fallback: bool = Field(default=False, description="Whether fallback archetype was used")


class TasteProfileResponse(BaseModel):
    known_track_count: int = Field(..., description="Total known tracks in user's profile set K")
    confidence: str = Field(..., description="'low' if < 8 tracks, else 'high'")
    confidence_reason: str = Field(..., description="Explanation of confidence level")
    dimensions: dict[str, DimensionResponse | None] = Field(
        ..., description="Core taste-o-meter dimensions"
    )
    music_dna: MusicDNASchema = Field(..., description="Music DNA summary")
    archetype: ArchetypeResponse = Field(
        ..., description="Deterministic rule-derived musical archetype"
    )
    region_exposures: list[RegionExposureItem] = Field(
        default_factory=list, description="Exposure across all 24 regions"
    )


class BlindspotResponseItem(BaseModel):
    region_id: int = Field(..., description="Blindspot region ID")
    name: str = Field(..., description="Region display name")
    genre_focus: str = Field(..., description="Genre and scene focus")
    description: str = Field(..., description="Acoustic and stylistic character")
    top_tags: list[str] = Field(default_factory=list, description="Discovered top tags by lift")
    exposure: float = Field(..., ge=0.0, le=1.0, description="User's current exposure level")
    adjacency_score: float = Field(
        ..., description="Cosine similarity between region and taste modes"
    )
    rank_score: float = Field(
        ..., description="Composite ranking score: adjacency * (1 - exposure)"
    )
    bridge_tags: list[str] = Field(
        default_factory=list, description="Connecting tags between user taste and region"
    )
    sample_tracks: list[TrackDetailResponse] = Field(
        default_factory=list, description="Exemplar tracks in this region"
    )


class BlindspotsResponse(BaseModel):
    blindspots: list[BlindspotResponseItem] = Field(
        default_factory=list, description="Ranked adjacent blindspots"
    )
    total_unexplored_regions: int = Field(
        ..., description="Total catalog regions below exposure threshold"
    )


class ListenBrainzImportRequest(BaseModel):
    username: str = Field(
        ..., min_length=1, max_length=64, description="Public ListenBrainz username"
    )
    limit: int = Field(default=50, ge=1, le=100, description="Maximum recent listens to inspect")


class ListenBrainzImportResponse(BaseModel):
    username: str = Field(..., description="Requested username")
    imported_count: int = Field(
        ..., description="Number of new catalog tracks matched and imported"
    )
    matched_count: int = Field(..., description="Total listens matched to catalog tracks")
    total_listens: int = Field(..., description="Total listens retrieved from ListenBrainz API")
    matched_tracks: list[TrackDetailResponse] = Field(
        default_factory=list, description="Matched catalog tracks"
    )
    message: str = Field(..., description="Human-readable result summary")
