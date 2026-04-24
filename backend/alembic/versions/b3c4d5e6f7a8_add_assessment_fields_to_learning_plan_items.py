"""add assessment fields to learning_plan_items

Revision ID: b3c4d5e6f7a8
Revises: 9b1c2d3e4f5a
Create Date: 2026-04-14 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "9b1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("learning_plan_items") as batch_op:
        batch_op.add_column(sa.Column("assessment_questions", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("assessment_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("assessment_attempts", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("learning_plan_items") as batch_op:
        batch_op.drop_column("assessment_attempts")
        batch_op.drop_column("assessment_score")
        batch_op.drop_column("assessment_questions")
