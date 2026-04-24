"""app/schemas/resume.py"""
import uuid
from typing import Optional
from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    file_name: str
    status: str
    message: str


class ResumeStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    parse_confidence: Optional[float] = None
    error_message: Optional[str] = None
