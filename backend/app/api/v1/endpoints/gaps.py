"""Gap analysis endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.db.session import get_db
from app.models.models import Role, User
from app.schemas.gaps import (
    GapItemResponse,
    GapListResponse,
    GapSummaryResponse,
    SetTargetRoleRequest,
    SetTargetRoleResponse,
    TargetRoleResponse,
)
from app.services.gap.gap_detector import detect_and_store_gaps

router = APIRouter(prefix="/users/me", tags=["gaps"])


@router.get("/target-role", response_model=TargetRoleResponse)
async def get_target_role(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    if not current_user.target_role_id:
        return TargetRoleResponse(user_id=current_user.id, role_id=None, role_name=None)

    role = await db.scalar(select(Role).where(Role.id == current_user.target_role_id))
    if not role:
        # Keep API resilient even if roles were wiped/changed.
        return TargetRoleResponse(user_id=current_user.id, role_id=None, role_name=None)

    return TargetRoleResponse(user_id=current_user.id, role_id=role.id, role_name=role.name)


@router.post("/target-role", response_model=SetTargetRoleResponse)
async def set_target_role(
    payload: SetTargetRoleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    role = None

    if payload.role_id:
        role = await db.scalar(select(Role).where(Role.id == payload.role_id))

    if not role and payload.role_name:
        role = await db.scalar(select(Role).where(func.lower(Role.name) == payload.role_name.lower()))

    # Compatibility path: many clients pass role name into role_id field.
    if not role and payload.role_id:
        role = await db.scalar(select(Role).where(func.lower(Role.name) == payload.role_id.lower()))

    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found. Provide a valid role_id or exact role_name.",
        )

    current_user.target_role_id = role.id
    db.add(current_user)
    await db.flush()
    await db.refresh(current_user)

    return SetTargetRoleResponse(user_id=current_user.id, role_id=role.id, role_name=role.name)


async def _resolve_target_role(current_user: User, db: AsyncSession) -> Role:
    if not current_user.target_role_id:
        raise HTTPException(status_code=400, detail="Target role not set. Use POST /api/v1/users/me/target-role")

    role = await db.scalar(select(Role).where(Role.id == current_user.target_role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Target role not found")
    return role


@router.get("/gaps", response_model=GapListResponse)
async def get_gaps(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    role = await _resolve_target_role(current_user, db)
    result = await detect_and_store_gaps(db, current_user, role)

    return GapListResponse(
        user_id=result.user_id,
        role_id=result.role_id,
        role_name=result.role_name,
        readiness_score=result.readiness_score,
        missing_skills=result.missing_skills,
        weak_skills=result.weak_skills,
        total_gaps=result.total_gaps,
        gaps=[
            GapItemResponse(
                skill_id=g.skill_id,
                skill_name=g.skill_name,
                gap_type=g.gap_type,
                priority_score=g.priority_score,
                current_proficiency=g.current_proficiency,
                required_proficiency=g.required_proficiency,
                time_to_learn_hours=g.time_to_learn_hours,
                importance=g.importance,
                is_mandatory=g.is_mandatory,
                prerequisites=g.prerequisites,
                prerequisite_coverage=g.prerequisite_coverage,
            )
            for g in result.gaps
        ],
    )


@router.get("/gaps/summary", response_model=GapSummaryResponse)
async def get_gaps_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    role = await _resolve_target_role(current_user, db)
    result = await detect_and_store_gaps(db, current_user, role)

    return GapSummaryResponse(
        user_id=result.user_id,
        role_id=result.role_id,
        role_name=result.role_name,
        readiness_score=result.readiness_score,
        missing_skills=result.missing_skills,
        weak_skills=result.weak_skills,
        total_gaps=result.total_gaps,
        total_learning_hours=result.total_learning_hours,
    )
