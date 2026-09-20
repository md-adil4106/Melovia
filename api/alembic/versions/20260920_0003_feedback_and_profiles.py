"""Create profiles and feedback_events tables for Phase 9.

Revision ID: 20260920_0003
Revises: 20260919_0002
Create Date: 2026-09-20 11:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260920_0003"
down_revision: str | None = "20260919_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. profiles table
    op.create_table(
        "profiles",
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("persistent_modes", sa.JSON(), nullable=False),
        sa.Column("known_track_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("device_id"),
    )

    # 2. feedback_events table
    op.create_table(
        "feedback_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("track_id", sa.String(length=36), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_feedback_events_device_id"), "feedback_events", ["device_id"], unique=False
    )
    op.create_index(
        op.f("ix_feedback_events_session_id"), "feedback_events", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_feedback_events_track_id"), "feedback_events", ["track_id"], unique=False
    )
    op.create_index(
        op.f("ix_feedback_events_created_at"), "feedback_events", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_feedback_events_created_at"), table_name="feedback_events")
    op.drop_index(op.f("ix_feedback_events_track_id"), table_name="feedback_events")
    op.drop_index(op.f("ix_feedback_events_session_id"), table_name="feedback_events")
    op.drop_index(op.f("ix_feedback_events_device_id"), table_name="feedback_events")
    op.drop_table("feedback_events")
    op.drop_table("profiles")
