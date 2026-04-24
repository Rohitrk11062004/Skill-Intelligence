#!/usr/bin/env python3
"""Ad-hoc spot check for catalog_service.get_resources_for_skill."""

import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal
from app.services.catalog_service import get_resources_for_skill


async def main() -> None:
    async with AsyncSessionLocal() as db:
        print("Case 1: Python / beginner")
        results = await get_resources_for_skill(db, "Python", "beginner")
        print(results)
        print()

        print("Case 2: python / beginner (case-insensitive)")
        results = await get_resources_for_skill(db, "python", "beginner")
        print(results)
        print()

        print("Case 3: NonExistentSkill / beginner")
        results = await get_resources_for_skill(db, "NonExistentSkill", "beginner")
        print(results)
        print()

        print("Case 4: PyTorch / advanced (fallback check if needed)")
        results = await get_resources_for_skill(db, "PyTorch", "advanced")
        print(results)
        print()

        print("Case 5: FastAPI / advanced (forces advanced -> intermediate fallback)")
        results = await get_resources_for_skill(db, "FastAPI", "advanced")
        print(results)


if __name__ == "__main__":
    asyncio.run(main())
