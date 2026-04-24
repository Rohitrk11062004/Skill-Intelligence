"""
app/schemas/auth.py
Request / response schemas for auth endpoints.
"""
import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    username: str
    account_role: Optional[str] = None  # employee | hr | admin
    email: EmailStr
    password: str
    full_name: str
    department: Optional[str] = None
    job_title: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    email: str
    full_name: str
    department: Optional[str]
    job_title: Optional[str]
    seniority_level: Optional[str]
    is_manager: bool
    account_role: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
