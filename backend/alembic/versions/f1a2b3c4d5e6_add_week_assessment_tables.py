"""add week assessment tables

Revision ID: f1a2b3c4d5e6
Revises: d9e8f7a6b5c4
Create Date: 2026-04-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d9e8f7a6b5c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "week_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("questions_json", sa.Text(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["learning_plans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "week_number", name="uq_week_assessments_plan_week"),
    )
    op.create_index("ix_week_assessments_plan_id", "week_assessments", ["plan_id"], unique=False)
    op.create_index("ix_week_assessments_user_id", "week_assessments", ["user_id"], unique=False)

    op.create_table(
        "week_assessment_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("week_assessment_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("answers_json", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["week_assessment_id"], ["week_assessments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_week_assessment_attempts_attempted_at",
        "week_assessment_attempts",
        ["attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_week_assessment_attempts_user_id",
        "week_assessment_attempts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_week_assessment_attempts_week_assessment_id",
        "week_assessment_attempts",
        ["week_assessment_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_week_assessment_attempts_week_assessment_id", table_name="week_assessment_attempts")
    op.drop_index("ix_week_assessment_attempts_user_id", table_name="week_assessment_attempts")
    op.drop_index("ix_week_assessment_attempts_attempted_at", table_name="week_assessment_attempts")
    op.drop_table("week_assessment_attempts")

    op.drop_index("ix_week_assessments_user_id", table_name="week_assessments")
    op.drop_index("ix_week_assessments_plan_id", table_name="week_assessments")
    op.drop_table("week_assessments")
