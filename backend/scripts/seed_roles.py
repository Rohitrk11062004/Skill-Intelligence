#!/usr/bin/env python3
"""
Seed roles, skills, and role skill requirements from extracted_skills_results.json.

Usage:
    python scripts/seed_roles.py

Optional env vars:
    EXTRACTED_SKILLS_JSON=Data/extracted_skills_results.json
"""

import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal
from app.models.models import Role, RoleSkillRequirement, Skill


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _infer_skill_type(category: str) -> str:
    cat = (category or "").lower()
    if cat == "behavioral skills":
        return "soft"
    if cat == "communication skills":
        return "soft"
    if cat == "people management skills":
        return "soft"
    if cat == "team management":
        return "soft"
    if cat == "domain/tools/process":
        return "tool"
    return "technical"


def _infer_min_proficiency(difficulty: Any, is_mandatory: bool) -> str:
    try:
        d = int(difficulty)
    except (TypeError, ValueError):
        d = 3

    if d >= 5:
        return "advanced" if is_mandatory else "intermediate"
    if d == 4:
        return "advanced"
    if d == 3:
        return "intermediate"
    return "beginner"


async def _ensure_skill_columns() -> None:
    """
    Legacy helper: older SQLite DBs may miss columns.
    On Postgres/Neon this is a no-op (schema is managed by Alembic).
    """
    async with AsyncSessionLocal() as session:
        db_url = os.getenv("DATABASE_URL", "")
        if "sqlite" not in db_url.lower():
            return

        result = await session.execute(text("PRAGMA table_info(skills)"))
        existing = {row[1] for row in result.fetchall()}

        alter_statements = []
        if "prerequisites" not in existing:
            alter_statements.append("ALTER TABLE skills ADD COLUMN prerequisites TEXT")
        if "difficulty" not in existing:
            alter_statements.append("ALTER TABLE skills ADD COLUMN difficulty INTEGER")
        if "time_to_learn_hours" not in existing:
            alter_statements.append("ALTER TABLE skills ADD COLUMN time_to_learn_hours INTEGER")

        for stmt in alter_statements:
            await session.execute(text(stmt))

        await session.commit()


async def seed_from_file(source_file: Path) -> None:
    """
    Seed roles, skills, and role-skill requirements from JSON.
    
    Optimization: Preload all existing skills, roles, and requirements into in-memory dicts
    to minimize N+1 queries over high-latency connections (Neon). This reduces thousands of
    round trips to just a few bulk queries at startup.
    """
    payload = json.loads(source_file.read_text(encoding="utf-8"))

    created_roles = 0
    reused_roles = 0
    created_skills = 0
    reused_skills = 0
    created_reqs = 0
    updated_reqs = 0

    async with AsyncSessionLocal() as session:
        # ─ Preload all existing data to avoid N+1 queries ─────────────────────
        all_skills_rows = (await session.execute(select(Skill))).scalars().all()
        skill_by_name_lower: dict[str, Skill] = {
            s.name.strip().lower(): s for s in all_skills_rows if s.name
        }

        all_roles_rows = (await session.execute(select(Role))).scalars().all()
        role_by_name_lower: dict[str, Role] = {
            r.name.strip().lower(): r for r in all_roles_rows if r.name
        }

        all_reqs_rows = (await session.execute(select(RoleSkillRequirement))).scalars().all()
        req_by_role_skill: dict[tuple[str, str], RoleSkillRequirement] = {
            (req.role_id, req.skill_id): req for req in all_reqs_rows
        }

        # ─ Process payload in memory, batch updates at end ───────────────────
        for role_item in payload:
            role_name = str(role_item.get("role") or "").strip()
            if not role_name:
                continue

            role_name_lower = role_name.lower()
            metadata = role_item.get("metadata") or {}
            seniority = metadata.get("seniority")

            if role_name_lower in role_by_name_lower:
                role_obj = role_by_name_lower[role_name_lower]
                reused_roles += 1
                if role_obj.department is not None:
                    role_obj.department = None
                    session.add(role_obj)
            else:
                role_obj = Role(
                    name=role_name,
                    description=f"Seeded from extracted JD skills ({role_item.get('folder_category', 'unknown')})",
                    department=None,
                    seniority_level=seniority,
                    is_custom=False,
                )
                session.add(role_obj)
                await session.flush()  # Assign primary key before creating requirements
                role_by_name_lower[role_name_lower] = role_obj
                created_roles += 1

            for skill_item in role_item.get("skills", []):
                skill_name = str(skill_item.get("name") or "").strip()
                if not skill_name:
                    continue

                skill_name_lower = skill_name.lower()
                category = str(skill_item.get("category") or "Technical Skills")
                prerequisites = skill_item.get("prerequisites") or []
                examples = skill_item.get("examples") or []
                aliases = [x for x in examples if isinstance(x, str) and x.strip()]

                if skill_name_lower in skill_by_name_lower:
                    skill_obj = skill_by_name_lower[skill_name_lower]
                    reused_skills += 1
                    changed = False

                    if not skill_obj.category and category:
                        skill_obj.category = category
                        changed = True

                    if not skill_obj.skill_type:
                        skill_obj.skill_type = _infer_skill_type(category)
                        changed = True

                    if hasattr(skill_obj, "prerequisites") and not skill_obj.prerequisites:
                        skill_obj.prerequisites = json.dumps(prerequisites, ensure_ascii=False)
                        changed = True

                    if hasattr(skill_obj, "difficulty") and skill_obj.difficulty is None:
                        skill_obj.difficulty = int(skill_item.get("difficulty") or 3)
                        changed = True

                    if hasattr(skill_obj, "time_to_learn_hours") and skill_obj.time_to_learn_hours is None:
                        skill_obj.time_to_learn_hours = int(skill_item.get("time_to_learn_hours") or 120)
                        changed = True

                    if aliases and not skill_obj.aliases:
                        skill_obj.aliases = json.dumps(aliases, ensure_ascii=False)
                        changed = True

                    if changed:
                        session.add(skill_obj)
                else:
                    skill_obj = Skill(
                        name=skill_name,
                        description=str(skill_item.get("context") or "").strip() or None,
                        skill_type=_infer_skill_type(category),
                        category=category,
                        aliases=json.dumps(aliases, ensure_ascii=False) if aliases else None,
                        prerequisites=json.dumps(prerequisites, ensure_ascii=False),
                        difficulty=int(skill_item.get("difficulty") or 3),
                        time_to_learn_hours=int(skill_item.get("time_to_learn_hours") or 120),
                        source_role=role_name,
                    )
                    session.add(skill_obj)
                    await session.flush()  # Assign primary key before creating requirements
                    skill_by_name_lower[skill_name_lower] = skill_obj
                    created_skills += 1

                importance = _clamp(_safe_float(skill_item.get("importance"), 0.6), 0.0, 1.0)
                is_mandatory = bool(skill_item.get("is_mandatory", False))
                min_prof = _infer_min_proficiency(skill_item.get("difficulty"), is_mandatory)

                req_key = (role_obj.id, skill_obj.id)
                if req_key in req_by_role_skill:
                    req_obj = req_by_role_skill[req_key]
                    req_obj.importance = max(req_obj.importance or 0.0, importance)
                    req_obj.is_mandatory = bool(req_obj.is_mandatory) or is_mandatory
                    req_obj.min_proficiency = min_prof if req_obj.min_proficiency == "beginner" else req_obj.min_proficiency
                    session.add(req_obj)
                    updated_reqs += 1
                else:
                    req_obj = RoleSkillRequirement(
                        role_id=role_obj.id,
                        skill_id=skill_obj.id,
                        importance=importance,
                        is_mandatory=is_mandatory,
                        min_proficiency=min_prof,
                    )
                    session.add(req_obj)
                    req_by_role_skill[req_key] = req_obj
                    created_reqs += 1

        await session.commit()

    print("=" * 72)
    print("Role seeding complete")
    print("=" * 72)
    print(f"Created roles:      {created_roles}")
    print(f"Reused roles:       {reused_roles}")
    print(f"Created skills:     {created_skills}")
    print(f"Reused skills:      {reused_skills}")
    print(f"Created reqs:       {created_reqs}")
    print(f"Updated reqs:       {updated_reqs}")
    print("=" * 72)


async def main() -> None:
    source = Path(os.getenv("EXTRACTED_SKILLS_JSON", "Data/extracted_skills_results.json")).resolve()
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    from app.core.config import settings
    print(f"Seeding from: {source}")
    print(f"DATABASE_URL kind: {'sqlite' if 'sqlite' in (settings.database_url or '').lower() else 'postgres'}")

    await _ensure_skill_columns()
    await seed_from_file(source)


if __name__ == "__main__":
    asyncio.run(main())
