"""Pydantic schemas for recommendation ranking signals."""

from pydantic import BaseModel, Field


class SharedTag(BaseModel):
    """A folksonomy tag shared between a recommended track and seed tracks."""

    tag: str = Field(..., description="Tag name in controlled folksonomy vocabulary")
    idf: float = Field(..., description="Inverse Document Frequency of the tag in catalog")
    weight: float = Field(..., description="Relevance salience weight of the shared tag")


class RecSignals(BaseModel):
    """Complete ranking signals backing an individual recommendation item."""

    sim_t: float = Field(..., description="Raw dot-product similarity in semantic channel t")
    sim_a: float | None = Field(
        default=None, description="Raw dot-product similarity in acoustic channel a"
    )
    pct_t: float = Field(
        ..., ge=0.0, le=1.0, description="Percentile rank within candidate pool for channel t"
    )
    pct_a: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Percentile rank within candidate pool for channel a",
    )
    shared_tags: list[SharedTag] = Field(
        default_factory=list,
        description="Tags shared between recommended track and nearest seed track",
    )
    scalar_deltas: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Deltas of interpretable scalars (energy_idx, valence_idx, etc.) vs nearest seed"
        ),
    )
    nearest_seed_id: str = Field(
        ..., description="Track UUID of the nearest seed in representation space"
    )
    nearest_seed_title: str | None = Field(default=None, description="Track title of nearest seed")
    nearest_seed_artist: str | None = Field(default=None, description="Artist name of nearest seed")
    novelty: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Normalized novelty score in [0, 1]"
    )
    familiarity: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Familiarity score (1 - novelty)"
    )
    artist_new: bool = Field(
        default=True, description="True if recommended artist was not among the seed artists"
    )
    popularity_pct: float = Field(
        default=50.0, ge=0.0, le=100.0, description="Track catalog popularity percentile"
    )
    region_id: int | None = Field(
        default=None, description="Assigned genre/acoustic region cluster ID"
    )
    region_label: str | None = Field(
        default=None, description="Human-readable name of the genre/acoustic region"
    )
    mmr_penalty: float = Field(
        default=0.0, ge=0.0, description="Max similarity penalty applied during MMR reranking"
    )
    session_facets_matched: list[str] = Field(
        default_factory=list,
        description="Session context facets matched (empty until Phase 8)",
    )
    discovery_value: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Effective discovery score or level"
    )
    discovery_d: float | None = Field(
        default=None, description="Slider discovery parameter d in [0, 1]"
    )
    discovery_score: float | None = Field(
        default=None, description="Raw discovery score before combination"
    )
    relevance: float | None = Field(default=None, description="Base multi-channel relevance score")
    utility: float | None = Field(default=None, description="Blended relevance/discovery utility")
    raw_sim_t: float | None = Field(default=None, description="Raw cosine similarity in channel t")
    percentile_t: float | None = Field(default=None, description="Percentile in channel t")
    raw_sim_a: float | None = Field(default=None, description="Raw cosine similarity in channel a")
    percentile_a: float | None = Field(default=None, description="Percentile in channel a")

    model_config = {"extra": "allow"}
