"""Admin endpoints for dashboard and user management."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.db.session import get_db
from app.models.models import (
    AssessmentAttempt,
    ContentChunk,
    LearningPlan,
    LearningPlanItem,
    Skill,
    SkillGap,
    User,
    UserSkillScore,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_role(user: User) -> str:
    return "admin" if user.is_manager else "employee"


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_manager:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


class UpdateUserRolePayload(BaseModel):
    role: str


@router.get("/overview")
async def admin_overview(
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    total_users = int(await db.scalar(select(func.count(User.id))) or 0)
    active_users = int(await db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0)
    total_skills = int(await db.scalar(select(func.count(Skill.id))) or 0)
    total_learning_paths = int(await db.scalar(select(func.count(LearningPlan.id))) or 0)
    total_content_chunks = int(await db.scalar(select(func.count(ContentChunk.id))) or 0)
    total_assessment_attempts = int(await db.scalar(select(func.count(AssessmentAttempt.id))) or 0)

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_skills": total_skills,
        "total_learning_paths": total_learning_paths,
        "total_content_chunks": total_content_chunks,
        "total_assessment_attempts": total_assessment_attempts,
    }


@router.get("/users")
async def admin_list_users(
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
    query: str = Query(default=""),
    role: str = Query(default=""),
):
    stmt = select(User)

    q = query.strip().lower()
    if q:
        stmt = stmt.where(
            or_(
                func.lower(User.full_name).contains(q),
                func.lower(User.email).contains(q),
            )
        )

    role_filter = role.strip().lower()
    if role_filter:
        if role_filter in {"admin", "manager"}:
            stmt = stmt.where(User.is_manager.is_(True))
        elif role_filter == "employee":
            stmt = stmt.where(User.is_manager.is_(False))

    rows = (await db.execute(stmt.order_by(User.created_at.desc()))).scalars().all()

    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": _user_role(u),
            "department": u.department,
            "is_active": u.is_active,
        }
        for u in rows
    ]


@router.post("/users/{user_id}/toggle-active")
async def admin_toggle_user_active(
    user_id: str,
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    db.add(user)
    await db.flush()
    return {"is_active": user.is_active}


@router.post("/users/{user_id}/role")
async def admin_update_user_role(
    user_id: str,
    payload: UpdateUserRolePayload,
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = payload.role.strip().lower()
    user.is_manager = role in {"admin", "manager"}
    db.add(user)
    await db.flush()

    return {"id": user.id, "role": _user_role(user)}


@router.get("/users/{user_id}/progress")
async def admin_user_progress(
    user_id: str,
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    skill_rows = (
        await db.execute(
            select(UserSkillScore, Skill)
            .join(Skill, Skill.id == UserSkillScore.skill_id)
            .where(UserSkillScore.user_id == user_id)
        )
    ).all()

    skills = [
        {
            "skill_name": skill.name,
            "proficiency": score.proficiency,
            "proficiency_score": score.proficiency_score,
        }
        for score, skill in skill_rows
    ]

    gap_rows = (
        await db.execute(
            select(SkillGap, Skill)
            .join(Skill, Skill.id == SkillGap.skill_id)
            .where(SkillGap.user_id == user_id)
            .order_by(SkillGap.priority_score.desc())
        )
    ).all()

    skill_gaps = [
        {
            "skill_name": skill.name,
            "gap_type": gap.gap_type,
            "gap_score": min(1.0, max(0.0, float(gap.priority_score or 0.0))),
        }
        for gap, skill in gap_rows
    ]

    plan_rows = (
        await db.execute(
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id)
            .order_by(LearningPlan.created_at.desc())
        )
    ).scalars().all()

    learning_paths = []
    for plan in plan_rows:
        total_modules = int(
            await db.scalar(
                select(func.count(LearningPlanItem.id)).where(LearningPlanItem.plan_id == plan.id)
            )
            or 0
        )
        completed_modules = int(
            await db.scalar(
                select(func.count(LearningPlanItem.id)).where(
                    LearningPlanItem.plan_id == plan.id,
                    LearningPlanItem.status == "completed",
                )
            )
            or 0
        )
        progress = int(round((completed_modules / total_modules) * 100)) if total_modules else 0
        learning_paths.append(
            {
                "id": plan.id,
                "title": f"Learning Path {plan.id[:8]}",
                "status": plan.status,
                "total_modules": total_modules,
                "completed_modules": completed_modules,
                "progress": progress,
            }
        )

    mastery_scores = {s["skill_name"]: s["proficiency_score"] for s in skills}

    return {
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": _user_role(user),
            "department": user.department,
        },
        "skills": skills,
        "skill_gaps": skill_gaps,
        "learning_paths": learning_paths,
        "mastery_scores": mastery_scores,
    }
