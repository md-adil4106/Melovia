"""Create staging_tracks table for real catalog ingestion.

Revision ID: 20260919_0002
Revises: 20260919_0001
Create Date: 2026-09-19 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260919_0002"
down_revision: str | None = "20260919_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staging_tracks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mbid", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("artist_name", sa.String(length=255), nullable=False),
        sa.Column("artist_mbid", sa.String(length=36), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("isrcs", sa.JSON(), nullable=False),
        sa.Column("popularity_pct", sa.Float(), nullable=False),
        sa.Column("has_a", sa.Boolean(), nullable=False),
        sa.Column("has_t", sa.Boolean(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("scalars", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_staging_tracks_mbid"), "staging_tracks", ["mbid"], unique=True)
    op.create_index(op.f("ix_staging_tracks_title"), "staging_tracks", ["title"], unique=False)
    op.create_index(
        op.f("ix_staging_tracks_artist_name"), "staging_tracks", ["artist_name"], unique=False
    )
    op.create_index(
        op.f("ix_staging_tracks_artist_mbid"), "staging_tracks", ["artist_mbid"], unique=False
    )
    op.create_index(
        "ix_staging_tracks_title_artist", "staging_tracks", ["title", "artist_name"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_staging_tracks_title_artist", table_name="staging_tracks")
    op.drop_index(op.f("ix_staging_tracks_artist_mbid"), table_name="staging_tracks")
    op.drop_index(op.f("ix_staging_tracks_artist_name"), table_name="staging_tracks")
    op.drop_index(op.f("ix_staging_tracks_title"), table_name="staging_tracks")
    op.drop_index(op.f("ix_staging_tracks_mbid"), table_name="staging_tracks")
    op.drop_table("staging_tracks")
