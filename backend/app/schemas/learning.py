"""Schemas for learning plan endpoints."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class LearningResource(BaseModel):
    type: str
    title: str
    provider: str
    search_query: str | None = None
    url: str | None = None
    estimated_hours: int


class LearningPlanItemResponse(BaseModel):
    order: int
    skill_id: str
    skill_name: str
    skill_rationale: Optional[str] = None
    gap_type: str
    priority_score: float
    estimated_hours: int
    prerequisites: list[str] = []
    resources: list[LearningResource] = []


class LearningPlanResponse(BaseModel):
    user_id: str
    role_id: str
    role_name: str
    readiness_score: float = Field(ge=0.0, le=1.0)
    total_hours_estimate: int
    item_count: int
    items: list[LearningPlanItemResponse]


class LearningModuleProgressResponse(BaseModel):
    ok: bool
    item_id: str
    status: str
    completed_at: Optional[datetime] = None
    plan_status: str
    plan_completed_at: Optional[datetime] = None
    reranked: bool


class SubSubtopic(BaseModel):
    title: str
    estimated_hours: float



class ResourceSuggestion(BaseModel):
    title: str
    provider: str
    url: str
    resource_type: Literal["video", "article", "course", "practice", "docs"]
    estimated_hours: float
    why: str


class Subtopic(BaseModel):
    title: str
    estimated_hours: float
    sub_subtopics: list[SubSubtopic]


class WeekSkillNode(BaseModel):
    skill_id: str = ""
    item_id: str = ""
    item_status: str = "not_started"
    skill_name: str
    skill_rationale: Optional[str] = None
    gap_type: str
    priority_score: float
    skill_band: str = "Technical Skills"
    total_hours: float
    subtopics: list[Subtopic]
    resources: list[ResourceSuggestion] = []


class DaySkillBlock(BaseModel):
    skill_id: str = ""
    item_id: str = ""
    skill_name: str
    estimated_hours: float
    focus_title: str = ""


class LearningDayPlan(BaseModel):
    """Monday=0 … Sunday=6."""

    day_index: int = Field(ge=0, le=6)
    day_name: str
    capacity_hours: float = 0.0
    estimated_hours: float = 0.0
    skills: list[DaySkillBlock] = []


class LearningWeek(BaseModel):
    week_number: int
    week_title: str
    total_hours: float
    skills: list[WeekSkillNode]
    days: list[LearningDayPlan] = []


class DeferredRoadmapItem(BaseModel):
    skill_id: str
    skill_name: str
    gap_type: str
    priority_score: float
    estimated_hours: float
    is_mandatory: bool = False


class RoadmapBudgetSummary(BaseModel):
    daily_hours: Optional[float] = None
    weeks: Optional[int] = None
    weekly_hours: int
    total_budget_hours: Optional[float] = None
    scheduled_hours: float
    overflow_hours_estimate: float = 0.0


class LearningRoadmapResponse(BaseModel):
    plan_id: Optional[str] = None
    target_role: str
    readiness_score: float
    total_weeks: int
    estimated_total_weeks: int
    total_hours_estimate: float
    hours_per_week: int
    daily_hours: Optional[float] = None
    study_days_per_week: int = 7
    weeks: list[LearningWeek]
    deferred_items: list[DeferredRoadmapItem] = []
    budget: Optional[RoadmapBudgetSummary] = None


class AssessmentFeedbackRequest(BaseModel):
    skill_name: str
    score: float = Field(ge=0.0, le=1.0)
    failed_areas: list[str] = []
    passed_areas: list[str] = []


class AssessmentFeedbackResponse(BaseModel):
    action_taken: str
    updated_subtopics: list[Subtopic] | None = None
    reranked_remaining: bool
