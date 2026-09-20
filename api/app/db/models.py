"""SQLAlchemy 2 Relational Models for Melovia.

Tables:
- artists: Canonical artist metadata
- tracks: Core track metadata aligned with bundle track_idx
- tags: Controlled folksonomy and genre tags
- track_tags: Weighted associations between tracks and tags
- catalog_versions: Registered immutable vector bundle versions
- Placeholders: sessions, feedback_events, profiles (stubs for later phases)
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    mbid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    tracks: Mapped[list["Track"]] = relationship(
        back_populates="artist", cascade="all, delete-orphan"
    )


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mbid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    isrcs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="mock", nullable=False)
    popularity_pct: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    has_a: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    has_t: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_idx: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    artist: Mapped["Artist"] = relationship(back_populates="tracks")
    track_tags: Mapped[list["TrackTag"]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)

    track_tags: Mapped[list["TrackTag"]] = relationship(back_populates="tag")


class TrackTag(Base):
    __tablename__ = "track_tags"

    track_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    track: Mapped["Track"] = relationship(back_populates="track_tags")
    tag: Mapped["Tag"] = relationship(back_populates="track_tags")


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"

    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="mock", nullable=False)
    track_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class StagingTrack(Base):
    """Staging table for ingested, cleaned, and deduplicated catalog recordings."""

    __tablename__ = "staging_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mbid: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_mbid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    isrcs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    popularity_pct: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    has_a: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_t: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    scalars: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="real_staging", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Profile(Base):
    """Anonymous device taste profile stored persistently with explicit user consent."""

    __tablename__ = "profiles"

    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    persistent_modes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    known_track_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class FeedbackEvent(Base):
    """Individual interaction event (like, dislike, skip, save) logged anonymously."""

    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    track_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


# ==============================================================================
# Placeholder Stubs (Preserved for initial migration compatibility)
# ==============================================================================


class UserSessionPlaceholder(Base):
    """Placeholder table for future steerable recommendation sessions."""

    __tablename__ = "sessions_placeholder"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class FeedbackEventPlaceholder(Base):
    """Placeholder table for future feedback and implicit interaction events."""

    __tablename__ = "feedback_events_placeholder"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ProfilePlaceholder(Base):
    """Placeholder table for future user taste representation profiles."""

    __tablename__ = "profiles_placeholder"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
