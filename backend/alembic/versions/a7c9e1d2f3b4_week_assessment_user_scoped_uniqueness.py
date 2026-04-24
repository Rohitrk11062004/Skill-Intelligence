"""scope week assessment uniqueness by user

Revision ID: a7c9e1d2f3b4
Revises: f1a2b3c4d5e6
Create Date: 2026-04-17 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c9e1d2f3b4"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_UNIQUE_NAME = "uq_week_assessments_plan_week"
NEW_UNIQUE_NAME = "uq_week_assessments_user_plan_week"


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(OLD_UNIQUE_NAME, "week_assessments", type_="unique")
        op.create_unique_constraint(
            NEW_UNIQUE_NAME,
            "week_assessments",
            ["user_id", "plan_id", "week_number"],
        )
        return

    with op.batch_alter_table("week_assessments") as batch_op:
        batch_op.drop_constraint(OLD_UNIQUE_NAME, type_="unique")
        batch_op.create_unique_constraint(
            NEW_UNIQUE_NAME,
            ["user_id", "plan_id", "week_number"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(NEW_UNIQUE_NAME, "week_assessments", type_="unique")
        op.create_unique_constraint(
            OLD_UNIQUE_NAME,
            "week_assessments",
            ["plan_id", "week_number"],
        )
        return

    with op.batch_alter_table("week_assessments") as batch_op:
        batch_op.drop_constraint(NEW_UNIQUE_NAME, type_="unique")
        batch_op.create_unique_constraint(
            OLD_UNIQUE_NAME,
            ["plan_id", "week_number"],
        )
