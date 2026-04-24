"""make persisted timestamps timezone-aware

Revision ID: d9e8f7a6b5c4
Revises: b3c4d5e6f7a8
Create Date: 2026-04-14 00:00:00.000000

Assumption: existing naive timestamp values were stored as UTC and should be
treated as UTC when converting to timestamptz on PostgreSQL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9e8f7a6b5c4"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_COLUMNS: dict[str, list[tuple[str, bool]]] = {
    "users": [
        ("created_at", False),
        ("updated_at", False),
    ],
    "resumes": [
        ("created_at", False),
        ("processed_at", True),
    ],
    "skills": [
        ("created_at", False),
    ],
    "user_skill_scores": [
        ("updated_at", False),
    ],
    "skill_snapshots": [
        ("created_at", False),
    ],
    "skill_gaps": [
        ("created_at", False),
        ("resolved_at", True),
    ],
    "learning_plans": [
        ("created_at", False),
        ("updated_at", False),
        ("completed_at", True),
    ],
    "learning_plan_items": [
        ("completed_at", True),
    ],
    "content_items": [
        ("created_at", False),
    ],
    "assessments": [
        ("created_at", False),
    ],
    "assessment_attempts": [
        ("submitted_at", False),
    ],
}


def _upgrade_postgres() -> None:
    for table_name, columns in TIMESTAMP_COLUMNS.items():
        for column_name, _nullable in columns:
            op.execute(
                sa.text(
                    f'ALTER TABLE "{table_name}" '
                    f'ALTER COLUMN "{column_name}" '
                    f"TYPE TIMESTAMP WITH TIME ZONE USING \"{column_name}\" AT TIME ZONE 'UTC'"
                )
            )


def _downgrade_postgres() -> None:
    for table_name, columns in TIMESTAMP_COLUMNS.items():
        for column_name, _nullable in columns:
            op.execute(
                sa.text(
                    f'ALTER TABLE "{table_name}" '
                    f'ALTER COLUMN "{column_name}" '
                    f"TYPE TIMESTAMP WITHOUT TIME ZONE USING \"{column_name}\" AT TIME ZONE 'UTC'"
                )
            )


def _alter_sqlite_columns(target_type: sa.DateTime) -> None:
    for table_name, columns in TIMESTAMP_COLUMNS.items():
        with op.batch_alter_table(table_name) as batch_op:
            for column_name, nullable in columns:
                batch_op.alter_column(
                    column_name,
                    existing_type=sa.DateTime(),
                    type_=target_type,
                    existing_nullable=nullable,
                )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _upgrade_postgres()
        return

    _alter_sqlite_columns(sa.DateTime(timezone=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _downgrade_postgres()
        return

    _alter_sqlite_columns(sa.DateTime())