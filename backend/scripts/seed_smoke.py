import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select, func

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal
from app.models.models import Role, Skill, RoleSkillRequirement


async def main() -> None:
    data_path = PROJECT_ROOT / "Data" / "extracted_skills_results.json"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    first_role = payload[0]
    role_name = first_role["role"]
    skill_name = first_role["skills"][0]["name"]

    async with AsyncSessionLocal() as session:
        role = await session.scalar(select(Role).where(func.lower(Role.name) == role_name.lower()))
        if not role:
            role = Role(name=role_name, description="smoke seed", department=None, seniority_level=None, is_custom=False)
            session.add(role)
            await session.flush()

        skill = await session.scalar(select(Skill).where(func.lower(Skill.name) == skill_name.lower()))
        if not skill:
            skill = Skill(name=skill_name, description="smoke seed", skill_type="technical", category="Technical Skills", prerequisites="[]")
            session.add(skill)
            await session.flush()

        req = await session.scalar(
            select(RoleSkillRequirement).where(
                RoleSkillRequirement.role_id == role.id,
                RoleSkillRequirement.skill_id == skill.id,
            )
        )
        if not req:
            req = RoleSkillRequirement(role_id=role.id, skill_id=skill.id, importance=0.6, is_mandatory=False, min_proficiency="intermediate")
            session.add(req)

        await session.commit()

    print({"ok": True, "role": role_name, "skill": skill_name})


if __name__ == "__main__":
    asyncio.run(main())

