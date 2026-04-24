"""Schemas for skill gap analysis."""
from pydantic import BaseModel, Field


class SetTargetRoleRequest(BaseModel):
    role_id: str | None = None
    role_name: str | None = None


class SetTargetRoleResponse(BaseModel):
    user_id: str
    role_id: str
    role_name: str


class TargetRoleResponse(BaseModel):
    user_id: str
    role_id: str | None = None
    role_name: str | None = None


class GapItemResponse(BaseModel):
    skill_id: str
    skill_name: str
    gap_type: str
    priority_score: float
    current_proficiency: str | None = None
    required_proficiency: str
    time_to_learn_hours: int
    importance: float = Field(ge=0.0, le=1.0)
    is_mandatory: bool
    prerequisites: list[str] = []
    prerequisite_coverage: float = Field(ge=0.0, le=1.0)


class GapListResponse(BaseModel):
    user_id: str
    role_id: str
    role_name: str
    readiness_score: float = Field(ge=0.0, le=1.0)
    missing_skills: int
    weak_skills: int
    total_gaps: int
    gaps: list[GapItemResponse]


class GapSummaryResponse(BaseModel):
    user_id: str
    role_id: str
    role_name: str
    readiness_score: float = Field(ge=0.0, le=1.0)
    missing_skills: int
    weak_skills: int
    total_gaps: int
    total_learning_hours: int
