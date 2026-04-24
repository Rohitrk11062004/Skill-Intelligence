"""app/schemas/roles.py"""
from typing import List, Optional

from pydantic import BaseModel, Field


class RoleListItem(BaseModel):
    id: str
    name: str
    department: Optional[str] = None
    seniority_level: Optional[str] = None
    skill_count: int


class RoleSkillItem(BaseModel):
    skill_id: str
    skill_name: str
    category: Optional[str] = None
    importance: float
    is_mandatory: bool
    min_proficiency: str


class RoleSkillsResponse(BaseModel):
    role_id: str
    role_name: str
    department: Optional[str] = None
    seniority_level: Optional[str] = None
    skills: List[RoleSkillItem]


class RoleSkillUpdateItem(BaseModel):
    skill_id: Optional[str] = None
    skill_name: Optional[str] = None
    category: Optional[str] = None
    importance: float = Field(default=0.6, ge=0.0, le=1.0)
    is_mandatory: bool = False
    min_proficiency: str = "intermediate"


class RoleSkillsUpdateRequest(BaseModel):
    skills: List[RoleSkillUpdateItem]
