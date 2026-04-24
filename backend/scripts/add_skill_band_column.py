#!/usr/bin/env python3
"""Add the skills.skill_band column if it is missing.

This is an idempotent additive schema update for environments that do not use
Alembic migrations. It works with both SQLite and PostgreSQL.

Usage:
    python scripts/add_skill_band_column.py
"""
import asyncio
import sys
from pathlib import Path

from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import engine  # noqa: E402


async def main() -> None:
    async with engine.begin() as conn:
        def _get_skill_columns(sync_conn):
            inspector = inspect(sync_conn)
            return [column["name"] for column in inspector.get_columns("skills")]

        try:
            columns = await conn.run_sync(_get_skill_columns)
        except Exception as exc:
            raise RuntimeError(f"Could not inspect skills table: {exc}") from exc

        if "skill_band" in columns:
            print("skills.skill_band already exists; no changes made.")
            return

        await conn.execute(text("ALTER TABLE skills ADD COLUMN skill_band VARCHAR(50)"))
        print("Added skills.skill_band column.")


if __name__ == "__main__":
    asyncio.run(main())