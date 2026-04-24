#!/usr/bin/env python3
"""
Safely wipe all application data from the database.

This script runs only DELETE statements—it does not DROP tables or modify the alembic_version migration history.
After wipe, roles and skills can be re-seeded with:
    python scripts/seed_roles.py

Usage:
    python scripts/wipe_all_data.py --yes

Or set env var:
    CONFIRM_WIPE=YES python scripts/wipe_all_data.py

Without a confirmation flag, the script will only print what it would delete (dry-run).
"""

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import delete, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal


# Tables in deletion order (children before parents, respecting FK constraints).
TABLES_TO_DELETE = [
    "week_assessment_attempts",
    "week_assessments",
    "assessment_attempts",
    "assessments",
    "learning_plan_item_sub_subtopics",
    "learning_plan_item_subtopics",
    "learning_plan_item_resources",
    "learning_plan_items",
    "learning_plans",
    "extracted_skills",
    "projects",
    "user_skill_scores",
    "skill_snapshots",
    "skill_gaps",
    "content_chunks",
    "content_items",
    "resumes",
    "role_skill_requirements",
    "skill_prerequisites",
]

# Tables with no foreign key dependencies (cleared after above).
BASE_TABLES = [
    "users",
    "roles",
    "skills",
]


def _should_confirm_wipe() -> bool:
    """Check for confirmation flag via CLI or env var."""
    if "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if os.getenv("CONFIRM_WIPE", "").upper() == "YES":
        return True
    return False


async def _get_table_row_counts(session) -> dict[str, int]:
    """Fetch current row count for each table."""
    counts = {}
    for table_name in TABLES_TO_DELETE + BASE_TABLES:
        try:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar() or 0
            counts[table_name] = count
        except Exception as e:
            print(f"⚠️  Could not count {table_name}: {e}")
            counts[table_name] = -1
    return counts


async def _print_wipe_plan(counts: dict[str, int]) -> None:
    """Display dry-run summary of tables and row counts."""
    print("\n📋 Wipe Plan (Dry-Run):\n")
    total_rows = 0
    for table in TABLES_TO_DELETE + BASE_TABLES:
        count = counts.get(table, 0)
        if count > 0:
            print(f"  {table:40s} {count:>6d} rows")
            total_rows += count
        elif count == 0:
            print(f"  {table:40s}  (empty)")
    print(f"\n  Total rows to delete: {total_rows}\n")


async def _execute_wipe(session) -> dict[str, int]:
    """Execute DELETE statements in dependency order. Returns deleted row counts."""
    deleted_counts = {}

    # Delete from dependent tables first.
    for table_name in TABLES_TO_DELETE:
        try:
            result = await session.execute(text(f"DELETE FROM {table_name}"))
            deleted_counts[table_name] = result.rowcount or 0
        except Exception as e:
            print(f"❌ Error deleting from {table_name}: {e}")
            deleted_counts[table_name] = -1
            raise

    # Clear foreign key references in users before deleting base tables.
    try:
        await session.execute(text("UPDATE users SET manager_id = NULL, target_role_id = NULL"))
    except Exception as e:
        print(f"❌ Error clearing user FK references: {e}")
        raise

    # Delete base tables (roles, skills, users).
    for table_name in BASE_TABLES:
        try:
            result = await session.execute(text(f"DELETE FROM {table_name}"))
            deleted_counts[table_name] = result.rowcount or 0
        except Exception as e:
            print(f"❌ Error deleting from {table_name}: {e}")
            deleted_counts[table_name] = -1
            raise

    await session.commit()
    return deleted_counts


async def _print_wipe_summary(deleted_counts: dict[str, int]) -> None:
    """Display final summary of deleted rows."""
    print("\n✅ Wipe Completed:\n")
    total_deleted = 0
    for table in TABLES_TO_DELETE + BASE_TABLES:
        count = deleted_counts.get(table, -1)
        if count > 0:
            print(f"  {table:40s} {count:>6d} rows deleted")
            total_deleted += count
        elif count == 0:
            pass  # Silently skip empty tables in summary.
    print(f"\n  Total rows deleted: {total_deleted}\n")


async def main():
    confirm = _should_confirm_wipe()
    async with AsyncSessionLocal() as session:
        counts = await _get_table_row_counts(session)
        await _print_wipe_plan(counts)

        if not confirm:
            print("🔒 Confirmation required to proceed.\n")
            print("   Use --yes flag or set CONFIRM_WIPE=YES to execute wipe.\n")
            return

        print("🗑️  Wiping all application data...\n")
        deleted_counts = await _execute_wipe(session)
        await _print_wipe_summary(deleted_counts)
        print("   Run 'python scripts/seed_roles.py' to re-seed roles and skills.\n")


if __name__ == "__main__":
    asyncio.run(main())
