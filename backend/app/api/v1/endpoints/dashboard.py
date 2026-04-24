"""Dashboard analytics endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.db.session import get_db
from app.models.models import ExtractedSkill, Resume, Role, Skill, User
from app.services.gap.gap_detector import detect_and_store_gaps
from app.services.learning.path_generator import build_learning_plan

router = APIRouter(prefix="/users/me", tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    detected_skills_count = 0
    recent_skills: list[str] = []

    latest_resume = await db.scalar(
        select(Resume)
        .where(Resume.user_id == current_user.id, Resume.status == "complete")
        .order_by(Resume.created_at.desc())
    )

    if latest_resume:
        detected_skills_count = int(
            await db.scalar(
                select(func.count(ExtractedSkill.id)).where(ExtractedSkill.resume_id == latest_resume.id)
            )
            or 0
        )

        rows = await db.execute(
            select(ExtractedSkill.raw_text, Skill.name)
            .outerjoin(Skill, ExtractedSkill.skill_id == Skill.id)
            .where(ExtractedSkill.resume_id == latest_resume.id)
            .order_by(ExtractedSkill.confidence.desc())
            .limit(12)
        )

        seen: set[str] = set()
        for raw_text, skill_name in rows.fetchall():
            label = (skill_name or raw_text or "").strip()
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            recent_skills.append(label)
            if len(recent_skills) >= 6:
                break

    gap_summary = {
        "readiness_score": 0.0,
        "total_gaps": 0,
        "missing_skills": 0,
        "weak_skills": 0,
    }
    priority_gaps: list[dict] = []
    active_paths_count = 0
    overall_progress = {"done": 0, "pending": 0, "total": 0}

    role = None
    if current_user.target_role_id:
        role = await db.scalar(select(Role).where(Role.id == current_user.target_role_id))

    if role:
        gap_result = await detect_and_store_gaps(db, current_user, role)
        gap_summary = {
            "readiness_score": gap_result.readiness_score,
            "total_gaps": gap_result.total_gaps,
            "missing_skills": gap_result.missing_skills,
            "weak_skills": gap_result.weak_skills,
        }

        priority_gaps = [
            {
                "skill_name": g.skill_name,
                "gap_type": g.gap_type,
                "priority_score": g.priority_score,
                "time_to_learn_hours": g.time_to_learn_hours,
            }
            for g in sorted(gap_result.gaps, key=lambda x: x.priority_score, reverse=True)[:6]
        ]

        _, plan_items = build_learning_plan(gap_result)
        total_items = len(plan_items)
        active_paths_count = 1 if total_items > 0 else 0
        overall_progress = {
            "done": 0,
            "pending": total_items,
            "total": total_items,
        }

    return {
        "detected_skills_count": detected_skills_count,
        "skill_gaps_count": gap_summary["total_gaps"],
        "active_paths_count": active_paths_count,
        "avg_mastery": gap_summary["readiness_score"],
        "your_learning_paths": {
            "count": active_paths_count,
            "total_items": overall_progress["total"],
        },
        "overall_progress": overall_progress,
        "recent_skills": recent_skills,
        "priority_gaps": priority_gaps,
    }
