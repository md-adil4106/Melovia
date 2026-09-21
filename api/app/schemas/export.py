"""Pydantic schemas for platform and file export operations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FileExportRequest(BaseModel):
    """Payload for exporting tracks to offline file formats."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["csv", "json", "m3u", "txt"] = Field(
        default="csv", description="Target file format ('csv', 'json', 'm3u', 'txt')"
    )
    playlist_name: str = Field(
        default="Melovia Playlist", max_length=100, description="Display name for playlist"
    )
    track_ids: list[str] | None = Field(
        default=None,
        max_length=500,
        description="List of up to 500 catalog track UUIDs to export",
    )
    tracks: list[dict[str, Any]] | None = Field(
        default=None,
        max_length=500,
        description="Explicit list of up to 500 track objects with title, artist, isrc, etc.",
    )

    @model_validator(mode="after")
    def validate_tracks_or_ids(self) -> FileExportRequest:
        if not self.track_ids and not self.tracks:
            raise ValueError("Either 'tracks' or 'track_ids' must be provided.")
        return self


class PlatformExportRequest(BaseModel):
    """Payload for exporting tracks to an external music service (Spotify)."""

    model_config = ConfigDict(extra="forbid")

    platform: Literal["spotify"] = Field(
        default="spotify", description="Target platform ('spotify')"
    )
    playlist_name: str = Field(
        default="Melovia Discoveries", max_length=100, description="Playlist title on platform"
    )
    playlist_description: str = Field(
        default="Exported from Melovia Music Discovery",
        max_length=300,
        description="Playlist description text",
    )
    track_ids: list[str] | None = Field(
        default=None,
        max_length=500,
        description="List of up to 500 catalog track UUIDs to export",
    )
    tracks: list[dict[str, Any]] | None = Field(
        default=None,
        max_length=500,
        description="Explicit list of up to 500 track objects with title, artist, isrc, etc.",
    )

    @model_validator(mode="after")
    def validate_tracks_or_ids(self) -> PlatformExportRequest:
        if not self.track_ids and not self.tracks:
            raise ValueError("Either 'tracks' or 'track_ids' must be provided.")
        return self


class TrackExportItem(BaseModel):
    """Status and matching details for a single track in an export job."""

    catalog_track_id: str = Field(..., description="Internal Melovia track UUID")
    title: str = Field(..., description="Track title")
    artist: str = Field(..., description="Artist name")
    isrc: str | None = Field(default=None, description="Associated ISRC code")
    status: Literal["matched", "ambiguous", "unmatched", "added", "failed"] = Field(
        ..., description="Resolution status on external platform"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Matching confidence score")
    platform_uri: str | None = Field(
        default=None, description="Platform track URI (e.g. spotify:track:...)"
    )
    platform_title: str | None = Field(default=None, description="Matched title on platform")
    platform_artist: str | None = Field(default=None, description="Matched artist on platform")
    match_strategy: str = Field(
        default="none", description="Strategy used ('isrc', 'fuzzy', 'none')"
    )


class ExportJobResponse(BaseModel):
    """Comprehensive details and per-track status of an export job."""

    job_id: str = Field(..., description="Unique UUID for this export job")
    status: Literal["pending", "processing", "completed", "failed"] = Field(
        ..., description="Overall job status"
    )
    platform: str = Field(..., description="Target platform identifier")
    playlist_name: str = Field(..., description="Target playlist title")
    playlist_id: str | None = Field(default=None, description="Created playlist ID on platform")
    playlist_url: str | None = Field(
        default=None, description="Web URL to open the created playlist"
    )
    total_tracks: int = Field(..., ge=0, description="Total tracks requested for export")
    matched_count: int = Field(..., ge=0, description="Number of successfully matched tracks")
    ambiguous_count: int = Field(..., ge=0, description="Tracks with uncertain matches")
    unmatched_count: int = Field(..., ge=0, description="Tracks without platform matches")
    tracks: list[TrackExportItem] = Field(
        default_factory=list, description="Detailed per-track matching report"
    )
    error: str | None = Field(default=None, description="Error message if export failed")
    created_at: str = Field(..., description="ISO 8601 UTC timestamp of export creation")


class SpotifyAuthUrlResponse(BaseModel):
    """Response containing PKCE authorization URL for Spotify login."""

    auth_url: str = Field(..., description="Spotify OAuth authorization URL")
    session_id: str = Field(..., description="Active session ID tracking this auth attempt")
    state: str = Field(..., description="CSRF state parameter")


class SpotifyStatusResponse(BaseModel):
    """Status of Spotify OAuth connection for the current session."""

    connected: bool = Field(..., description="Whether valid Spotify credentials exist for session")
    display_name: str | None = Field(default=None, description="Spotify user display name")
    user_id: str | None = Field(default=None, description="Spotify user ID")
    profile_url: str | None = Field(default=None, description="Link to user's Spotify profile")
