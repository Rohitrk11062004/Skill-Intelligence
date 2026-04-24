#!/usr/bin/env python3
"""Assign skill bands to existing skill rows based on skill.category."""
import asyncio
from collections import Counter
from typing import Optional

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.models import Skill

BAND_MAP = {
    "Technical Skills": [
        "programming_language", "framework", "database", "cloud",
        "devops", "testing", "architecture", "algorithms",
        "data_structures", "backend", "frontend", "mobile", "ml_ai",
        "data_engineering", "infrastructure",
    ],
    "Domain/Tools/Process": [
        "tool", "methodology", "domain", "process", "platform",
        "security", "analytics", "design", "networking", "hardware",
    ],
    "Team Management": [
        "project_management", "agile", "scrum", "planning",
        "delivery", "coordination", "tracking",
    ],
    "People Management Skills": [
        "leadership", "mentoring", "hiring", "performance_management",
        "coaching", "management",
    ],
    "Communication Skills": [
        "communication", "documentation", "presentation",
        "writing", "reporting", "stakeholder",
    ],
    "Behavioral Skills": [
        "soft_skill", "behavioral", "problem_solving", "adaptability",
        "critical_thinking", "creativity", "collaboration",
    ],
}

DEFAULT_BAND = "Technical Skills"


def _normalize_category(category: Optional[str]) -> str:
    if not category:
        return ""
    return category.strip().lower().replace("-", "_").replace(" ", "_")


def _resolve_band(category: Optional[str]) -> str:
    normalized = _normalize_category(category)
    if not normalized:
        return DEFAULT_BAND

    for band, category_keys in BAND_MAP.items():
        if normalized in category_keys:
            return band

    return DEFAULT_BAND


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Skill))
        skills = result.scalars().all()

        band_distribution: Counter[str] = Counter()
        updated_count = 0

        for skill in skills:
            new_band = _resolve_band(skill.category)
            band_distribution[new_band] += 1

            if skill.skill_band != new_band:
                skill.skill_band = new_band
                updated_count += 1
                db.add(skill)

        await db.flush()
        await db.commit()

    print(f"Updated {updated_count} skills → band distribution: {dict(band_distribution)}")


if __name__ == "__main__":
    asyncio.run(main())
