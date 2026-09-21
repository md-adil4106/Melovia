"""Create study_ratings table for Phase 15.

Revision ID: 20260921_0004
Revises: 20260920_0003
Create Date: 2026-09-21 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260921_0004"
down_revision: str | None = "20260920_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_ratings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("participant_id", sa.String(length=64), nullable=True),
        sa.Column("seed_set_id", sa.String(length=32), nullable=False),
        sa.Column("arm_order", sa.String(length=16), nullable=False),
        sa.Column("playlist_a_arm", sa.String(length=16), nullable=False),
        sa.Column("playlist_b_arm", sa.String(length=16), nullable=False),
        sa.Column("relevance_a", sa.Integer(), nullable=False),
        sa.Column("discovery_a", sa.Integer(), nullable=False),
        sa.Column("flow_a", sa.Integer(), nullable=False),
        sa.Column("satisfaction_a", sa.Integer(), nullable=False),
        sa.Column("relevance_b", sa.Integer(), nullable=False),
        sa.Column("discovery_b", sa.Integer(), nullable=False),
        sa.Column("flow_b", sa.Integer(), nullable=False),
        sa.Column("satisfaction_b", sa.Integer(), nullable=False),
        sa.Column("preferred_overall", sa.String(length=16), nullable=False),
        sa.Column("feedback_text", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_study_ratings_session_id"), "study_ratings", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_study_ratings_participant_id"), "study_ratings", ["participant_id"], unique=False
    )
    op.create_index(
        op.f("ix_study_ratings_seed_set_id"), "study_ratings", ["seed_set_id"], unique=False
    )
    op.create_index(
        op.f("ix_study_ratings_created_at"), "study_ratings", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_study_ratings_created_at"), table_name="study_ratings")
    op.drop_index(op.f("ix_study_ratings_seed_set_id"), table_name="study_ratings")
    op.drop_index(op.f("ix_study_ratings_participant_id"), table_name="study_ratings")
    op.drop_index(op.f("ix_study_ratings_session_id"), table_name="study_ratings")
    op.drop_table("study_ratings")
