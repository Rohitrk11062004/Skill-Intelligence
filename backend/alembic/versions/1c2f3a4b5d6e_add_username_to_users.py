"""add username to users

Revision ID: 1c2f3a4b5d6e
Revises: a161d4e95a25
Create Date: 2026-04-22

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1c2f3a4b5d6e"
down_revision = "a161d4e95a25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=60), nullable=True))
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Backfill for existing rows (including hardcoded admin)
    # - If email exists, use local-part before '@'
    # - Else fall back to "user_<id-prefix>"
    op.execute(
        """
        UPDATE users
        SET username = COALESCE(
            NULLIF(split_part(email, '@', 1), ''),
            CONCAT('user_', substring(id, 1, 8))
        )
        WHERE username IS NULL
        """
    )

    op.alter_column("users", "username", existing_type=sa.String(length=60), nullable=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "username")

