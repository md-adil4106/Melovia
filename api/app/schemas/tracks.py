"""Pydantic schemas for tracks and catalog querying."""

from pydantic import BaseModel, Field


class AudioScalars(BaseModel):
    bpm: float | None = Field(default=None, description="Beats per minute")
    tempo_bpm: float | None = Field(default=None, description="Alternate BPM field")
    energy: float | None = Field(default=None, ge=0.0, le=1.0, description="Perceptual energy")
    valence: float | None = Field(default=None, ge=0.0, le=1.0, description="Musical positiveness")
    danceability: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Danceability score"
    )
    acousticness: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Acousticness score"
    )
    instrumentalness: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Instrumentalness score"
    )
    loudness_db: float | None = Field(default=None, description="Overall loudness in decibels")


class TrackDetailResponse(BaseModel):
    id: str = Field(..., description="Canonical track UUID")
    track_idx: int = Field(..., description="Contiguous 0-indexed catalog position")
    mbid: str | None = Field(default=None, description="MusicBrainz recording ID")
    title: str = Field(..., description="Track title")
    artist_id: str = Field(..., description="Canonical artist UUID")
    artist_name: str = Field(..., description="Artist display name")
    year: int | None = Field(default=None, description="Release year")
    isrcs: list[str] = Field(default_factory=list, description="Associated ISRC codes")
    popularity_pct: float = Field(..., ge=0.0, le=100.0, description="Popularity percentile")
    has_a: bool = Field(..., description="Whether acoustic vector channel 'a' exists")
    has_t: bool = Field(..., description="Whether taste vector channel 't' exists")
    region_id: int | None = Field(default=None, description="Planted region/cluster ID")
    scalars: AudioScalars | None = Field(default=None, description="Numeric audio descriptors")
    tags: list[str] = Field(
        default_factory=list, description="Associated genre and folksonomy tags"
    )
    artwork_url: str | None = Field(default=None, description="Album artwork image URL")
    preview_url: str | None = Field(default=None, description="Audio preview clip URL")
    album_name: str | None = Field(default=None, description="Album or collection name")


class TrackSearchResponse(BaseModel):
    query: str = Field(..., description="Normalized search term")
    total: int = Field(..., description="Total matches found")
    limit: int = Field(..., description="Maximum items requested")
    items: list[TrackDetailResponse] = Field(default_factory=list, description="Matched tracks")
