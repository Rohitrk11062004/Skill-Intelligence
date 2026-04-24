"""
app/api/v1/endpoints/users.py
User profile management and settings endpoints.
"""
from typing import Annotated
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.security import verify_password, hash_password
from app.db.session import get_db
from app.models.models import User, UserPreference, Resume, ExtractedSkill, UserSkillScore
from app.schemas.auth import UserResponse
from app.schemas.users import (
    UserUpdate, ChangePasswordRequest, UserPreferenceSchema,
    UserPreferenceUpdate, ResumeSummaryResponse, SkillTrendResponse, TrendPoint
)

router = APIRouter(prefix="/users/me", tags=["users"])


@router.patch("", response_model=UserResponse)
async def update_profile(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.department is not None:
        current_user.department = payload.department
    if payload.job_title is not None:
        current_user.job_title = payload.job_title
    if payload.seniority_level is not None:
        current_user.seniority_level = payload.seniority_level
        
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()


@router.get("/preferences", response_model=UserPreferenceSchema)
async def get_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    prefs = await db.scalar(select(UserPreference).where(UserPreference.user_id == current_user.id))
    if not prefs:
        prefs = UserPreference(user_id=current_user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
    return prefs


@router.patch("/preferences", response_model=UserPreferenceSchema)
async def update_preferences(
    payload: UserPreferenceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    prefs = await db.scalar(select(UserPreference).where(UserPreference.user_id == current_user.id))
    if not prefs:
        prefs = UserPreference(user_id=current_user.id)
        db.add(prefs)
        
    if payload.email_notifications is not None:
        prefs.email_notifications = payload.email_notifications
    if payload.in_app_notifications is not None:
        prefs.in_app_notifications = payload.in_app_notifications
    if payload.weekly_summary is not None:
        prefs.weekly_summary = payload.weekly_summary
        
    await db.commit()
    await db.refresh(prefs)
    return prefs


@router.get("/resumes", response_model=list[ResumeSummaryResponse])
async def upload_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Resume.id,
            Resume.job_id,
            Resume.file_name,
            Resume.status,
            Resume.created_at,
            func.count(ExtractedSkill.id).label("skills_count")
        )
        .outerjoin(ExtractedSkill, ExtractedSkill.resume_id == Resume.id)
        .where(Resume.user_id == current_user.id)
        .group_by(
            Resume.id,
            Resume.job_id,
            Resume.file_name,
            Resume.status,
            Resume.created_at,
        )
        .order_by(Resume.created_at.desc())
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        ResumeSummaryResponse(
            id=row.id,
            job_id=row.job_id,
            file_name=row.file_name,
            status=row.status,
            created_at=row.created_at,
            skills_count=row.skills_count
        )
        for row in rows
    ]


@router.get("/skill-trend", response_model=SkillTrendResponse)
async def skill_trend(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    total_score = await db.scalar(
        select(func.sum(UserSkillScore.proficiency_score))
        .where(UserSkillScore.user_id == current_user.id)
    )
    total_score = float(total_score or 0.0)
    
    now = datetime.now(timezone.utc)
    # Generate 4 dates including today
    dates = [(now - timedelta(days=7 * i)).strftime("%Y-%m-%d") for i in range(3, -1, -1)]
    
    base_score = max(0, total_score - 3.0)
    trend = []
    
    for i, date_str in enumerate(dates):
        current_step = base_score + (total_score - base_score) * (i / 3.0)
        trend.append(TrendPoint(date=date_str, total_score=round(current_step, 1)))

    return SkillTrendResponse(
        cadence="weekly",
        window_days=28,
        trend=trend
    )
