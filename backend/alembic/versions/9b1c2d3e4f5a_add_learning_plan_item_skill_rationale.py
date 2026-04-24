"""add skill_rationale to learning_plan_items

Revision ID: 9b1c2d3e4f5a
Revises: 7f2d3c9a1b4e
Create Date: 2026-04-14 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b1c2d3e4f5a"
down_revision: Union[str, Sequence[str], None] = "7f2d3c9a1b4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("learning_plan_items") as batch_op:
        batch_op.add_column(sa.Column("skill_rationale", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("learning_plan_items") as batch_op:
        batch_op.drop_column("skill_rationale")
