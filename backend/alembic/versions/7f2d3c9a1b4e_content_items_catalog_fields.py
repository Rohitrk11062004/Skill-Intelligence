"""add content catalog fields to content_items

Revision ID: 7f2d3c9a1b4e
Revises: 4eeda4bf7f98
Create Date: 2026-04-14 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f2d3c9a1b4e"
down_revision: Union[str, Sequence[str], None] = "4eeda4bf7f98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("content_items") as batch_op:
        batch_op.add_column(sa.Column("provider", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("resource_format", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("content_items") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("duration_minutes")
        batch_op.drop_column("resource_format")
        batch_op.drop_column("provider")
