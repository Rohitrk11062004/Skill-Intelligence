"""
app/schemas/users.py
Schemas for user profile and preferences.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    seniority_level: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserPreferenceSchema(BaseModel):
    email_notifications: bool
    in_app_notifications: bool
    weekly_summary: bool

    class Config:
        from_attributes = True


class UserPreferenceUpdate(BaseModel):
    email_notifications: Optional[bool] = None
    in_app_notifications: Optional[bool] = None
    weekly_summary: Optional[bool] = None


class ResumeSummaryResponse(BaseModel):
    id: str
    job_id: str
    file_name: str
    status: str
    skills_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class TrendPoint(BaseModel):
    date: str
    total_score: float


class SkillTrendResponse(BaseModel):
    cadence: str = "weekly"
    window_days: int = 28
    trend: list[TrendPoint]
