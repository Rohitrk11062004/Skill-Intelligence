import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal
from app.models.models import Role, RoleSkillRequirement, Skill


async def main() -> None:
    async with AsyncSessionLocal() as session:
        roles = await session.scalar(select(func.count()).select_from(Role))
        skills = await session.scalar(select(func.count()).select_from(Skill))
        reqs = await session.scalar(select(func.count()).select_from(RoleSkillRequirement))
        print({"roles": int(roles or 0), "skills": int(skills or 0), "role_skill_requirements": int(reqs or 0)})


if __name__ == "__main__":
    asyncio.run(main())

