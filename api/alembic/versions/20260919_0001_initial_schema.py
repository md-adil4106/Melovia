"""Initial relational schema for Melovia.

Revision ID: 20260919_0001
Revises:
Create Date: 2026-09-19 21:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260919_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. artists
    op.create_table(
        "artists",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mbid", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artists_name"), "artists", ["name"], unique=False)
    op.create_index(op.f("ix_artists_mbid"), "artists", ["mbid"], unique=False)

    # 2. tracks
    op.create_table(
        "tracks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mbid", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("artist_id", sa.String(length=36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("isrcs", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("popularity_pct", sa.Float(), nullable=False),
        sa.Column("has_a", sa.Boolean(), nullable=False),
        sa.Column("has_t", sa.Boolean(), nullable=False),
        sa.Column("track_idx", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tracks_title"), "tracks", ["title"], unique=False)
    op.create_index(op.f("ix_tracks_mbid"), "tracks", ["mbid"], unique=False)
    op.create_index(op.f("ix_tracks_artist_id"), "tracks", ["artist_id"], unique=False)
    op.create_index(op.f("ix_tracks_track_idx"), "tracks", ["track_idx"], unique=True)

    # 3. tags
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tags_name"), "tags", ["name"], unique=True)

    # 4. track_tags
    op.create_table(
        "track_tags",
        sa.Column("track_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("track_id", "tag_id"),
    )

    # 5. catalog_versions
    op.create_table(
        "catalog_versions",
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=False),
        sa.Column("track_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("version"),
    )

    # 6. placeholders
    op.create_table(
        "sessions_placeholder",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "feedback_events_placeholder",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "profiles_placeholder",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("profiles_placeholder")
    op.drop_table("feedback_events_placeholder")
    op.drop_table("sessions_placeholder")
    op.drop_table("catalog_versions")
    op.drop_table("track_tags")
    op.drop_table("tags")
    op.drop_table("tracks")
    op.drop_table("artists")
