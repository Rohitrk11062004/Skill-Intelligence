"""
app/models/models.py
All ORM models — SQLite compatible version.
Embeddings stored as JSON instead of pgvector.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2.5 — Auth & User System
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    department: Mapped[Optional[str]] = mapped_column(String(100))
    job_title: Mapped[Optional[str]] = mapped_column(String(150))
    seniority_level: Mapped[Optional[str]] = mapped_column(String(20))
    manager_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    target_role_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("roles.id"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    resumes: Mapped[list["Resume"]] = relationship("Resume", back_populates="user")
    skill_scores: Mapped[list["UserSkillScore"]] = relationship("UserSkillScore", back_populates="user")
    skill_snapshots: Mapped[list["SkillSnapshot"]] = relationship("SkillSnapshot", back_populates="user")
    learning_plans: Mapped[list["LearningPlan"]] = relationship("LearningPlan", back_populates="user")
    preferences: Mapped[Optional["UserPreference"]] = relationship("UserPreference", back_populates="user", uselist=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    in_app_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user: Mapped["User"] = relationship("User", back_populates="preferences")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Data Ingestion
# ══════════════════════════════════════════════════════════════════════════════

class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    job_id: Mapped[str] = mapped_column(String(36), default=gen_uuid, index=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    parsed_sections: Mapped[Optional[str]] = mapped_column(Text)   # JSON string
    parse_confidence: Mapped[Optional[float]] = mapped_column(Float)
    layout_type: Mapped[Optional[str]] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User", back_populates="resumes")
    extracted_skills: Mapped[list["ExtractedSkill"]] = relationship("ExtractedSkill", back_populates="resume")


# ══════════════════════════════════════════════════════════════════════════════
# ESCO Skill Taxonomy
# ══════════════════════════════════════════════════════════════════════════════

class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    skill_type: Mapped[str] = mapped_column(String(20), default="technical")
    # technical | soft | domain | tool | language
    category: Mapped[Optional[str]] = mapped_column(String(100))
    skill_band: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # e.g. "Backend", "Frontend", "DevOps", "Soft Skills"
    aliases: Mapped[Optional[str]] = mapped_column(Text)
    # JSON list of alternate names — ["JS", "javascript", "ECMAScript"]
    prerequisites: Mapped[Optional[str]] = mapped_column(Text)
    # JSON list — ["Python", "REST API"]
    difficulty: Mapped[Optional[int]] = mapped_column(Integer)
    # 1..5
    time_to_learn_hours: Mapped[Optional[int]] = mapped_column(Integer)
    # Estimated hours to learn
    source_role: Mapped[Optional[str]] = mapped_column(String(255))
    # which JD this skill was first seen in
    embedding: Mapped[Optional[str]] = mapped_column(Text)
    # JSON float list — for similarity matching
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    def get_aliases(self) -> list:
        if not self.aliases:
            return []
        try:
            import json
            return json.loads(self.aliases)
        except Exception:
            return []

    def get_embedding(self) -> Optional[list]:
        if not self.embedding:
            return None
        try:
            import json
            return json.loads(self.embedding)
        except Exception:
            return None


class SkillPrerequisite(Base):
    __tablename__ = "skill_prerequisites"
    __table_args__ = (UniqueConstraint("skill_id", "prerequisite_skill_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id"), nullable=False, index=True)
    prerequisite_skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id"), nullable=False, index=True)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    department: Mapped[Optional[str]] = mapped_column(String(100))
    seniority_level: Mapped[Optional[str]] = mapped_column(String(50))
    esco_occupation_id: Mapped[Optional[str]] = mapped_column(String(100))
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)

    skill_requirements: Mapped[list["RoleSkillRequirement"]] = relationship("RoleSkillRequirement")


class RoleSkillRequirement(Base):
    __tablename__ = "role_skill_requirements"
    __table_args__ = (UniqueConstraint("role_id", "skill_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id"), nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=1.0)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    min_proficiency: Mapped[str] = mapped_column(String(20), default="intermediate")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Skill Extraction
# ══════════════════════════════════════════════════════════════════════════════

class ExtractedSkill(Base):
    __tablename__ = "extracted_skills"
    __table_args__ = (UniqueConstraint("resume_id", "skill_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    resume_id: Mapped[str] = mapped_column(String(36), ForeignKey("resumes.id"), nullable=False)
    skill_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("skills.id"))
    raw_text: Mapped[str] = mapped_column(String(255))
    extractor: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_section: Mapped[Optional[str]] = mapped_column(String(50))
    source_text: Mapped[Optional[str]] = mapped_column(Text)
    frequency: Mapped[int] = mapped_column(Integer, default=1)

    resume: Mapped["Resume"] = relationship("Resume", back_populates="extracted_skills")
    skill: Mapped[Optional["Skill"]] = relationship("Skill")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Project Analysis
# ══════════════════════════════════════════════════════════════════════════════

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    resume_id: Mapped[str] = mapped_column(String(36), ForeignKey("resumes.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    tech_stack: Mapped[Optional[str]] = mapped_column(Text)   # JSON string
    complexity_score: Mapped[Optional[int]] = mapped_column(Integer)
    is_team_project: Mapped[Optional[bool]] = mapped_column(Boolean)
    team_size_signal: Mapped[Optional[str]] = mapped_column(String(50))
    start_date: Mapped[Optional[str]] = mapped_column(String(20))
    end_date: Mapped[Optional[str]] = mapped_column(String(20))


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 5/6 — Feature Engineering + Proficiency
# ══════════════════════════════════════════════════════════════════════════════

class UserSkillScore(Base):
    __tablename__ = "user_skill_scores"
    __table_args__ = (UniqueConstraint("user_id", "skill_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id"), nullable=False)

    proficiency: Mapped[str] = mapped_column(String(20), default="beginner")
    proficiency_score: Mapped[float] = mapped_column(Float, default=0.0)

    years_of_experience: Mapped[Optional[float]] = mapped_column(Float)
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    recency_months: Mapped[Optional[int]] = mapped_column(Integer)
    project_complexity_max: Mapped[Optional[int]] = mapped_column(Integer)
    context_strength: Mapped[float] = mapped_column(Float, default=0.5)

    user_override: Mapped[Optional[str]] = mapped_column(String(20))
    manager_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    manager_override: Mapped[Optional[str]] = mapped_column(String(20))

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user: Mapped["User"] = relationship("User", back_populates="skill_scores")
    skill: Mapped["Skill"] = relationship("Skill")


class SkillSnapshot(Base):
    __tablename__ = "skill_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    snapshot_data: Mapped[str] = mapped_column(Text)   # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped["User"] = relationship("User", back_populates="skill_snapshots")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 7 — Skill Gap
# ══════════════════════════════════════════════════════════════════════════════

class SkillGap(Base):
    __tablename__ = "skill_gaps"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", "role_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id"), nullable=False)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), nullable=False)

    gap_type: Mapped[str] = mapped_column(String(20), nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    time_to_learn_hours: Mapped[Optional[int]] = mapped_column(Integer)
    current_proficiency: Mapped[Optional[str]] = mapped_column(String(20))
    required_proficiency: Mapped[str] = mapped_column(String(20), default="intermediate")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 8 — Learning Path
# ══════════════════════════════════════════════════════════════════════════════

class LearningPlan(Base):
    __tablename__ = "learning_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), nullable=False)
    total_hours_estimate: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="learning_plans")
    items: Mapped[list["LearningPlanItem"]] = relationship("LearningPlanItem", back_populates="plan")


class LearningPlanItem(Base):
    __tablename__ = "learning_plan_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_plans.id"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    resource_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1000))
    provider: Mapped[Optional[str]] = mapped_column(String(100))
    skill_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assessment_questions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assessment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    assessment_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skill_band: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subtopics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_hours: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="not_started")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped["LearningPlan"] = relationship("LearningPlan", back_populates="items")
    skill: Mapped["Skill"] = relationship("Skill")


class LearningPlanItemSubtopic(Base):
    __tablename__ = "learning_plan_item_subtopics"
    __table_args__ = (UniqueConstraint("item_id", "order_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_plan_items.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0)
    focus: Mapped[bool] = mapped_column(Boolean, default=False)


class LearningPlanItemSubSubtopic(Base):
    __tablename__ = "learning_plan_item_sub_subtopics"
    __table_args__ = (UniqueConstraint("subtopic_id", "order_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    subtopic_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_plan_item_subtopics.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0)


class LearningPlanItemResource(Base):
    __tablename__ = "learning_plan_item_resources"
    __table_args__ = (UniqueConstraint("item_id", "rank"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_plan_items.id"), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0)
    why: Mapped[str] = mapped_column(Text, nullable=False)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 9 — Content + Assessments
# ══════════════════════════════════════════════════════════════════════════════

class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    title: Mapped[str] = mapped_column(String(255), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    difficulty_level: Mapped[str] = mapped_column(String(20), default="intermediate")
    # JSON list of skill names, e.g. ["Python", "FastAPI"]
    skill_tags: Mapped[Optional[list[str]]] = mapped_column(JSON)
    provider: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    resource_format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    chunks: Mapped[list["ContentChunk"]] = relationship(
        "ContentChunk",
        back_populates="content_item",
        cascade="all, delete-orphan",
    )


class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    content_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("content_items.id"), nullable=False, index=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    content_item: Mapped["ContentItem"] = relationship("ContentItem", back_populates="chunks")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    skill_name: Mapped[str] = mapped_column(String(255), index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate")
    question_type: Mapped[str] = mapped_column(String(20), default="mcq")
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON)
    correct_option: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        "AssessmentAttempt",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assessment_id: Mapped[str] = mapped_column(String(36), ForeignKey("assessments.id"), nullable=False, index=True)
    answer: Mapped[str] = mapped_column(String(255))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    max_score: Mapped[int] = mapped_column(Integer, default=1)
    time_taken_seconds: Mapped[int] = mapped_column(Integer, default=0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="attempts")
    user: Mapped["User"] = relationship("User")


class WeekAssessment(Base):
    __tablename__ = "week_assessments"
    __table_args__ = (UniqueConstraint("user_id", "plan_id", "week_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_plans.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    questions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    attempts: Mapped[list["WeekAssessmentAttempt"]] = relationship(
        "WeekAssessmentAttempt",
        back_populates="week_assessment",
        cascade="all, delete-orphan",
    )


class WeekAssessmentAttempt(Base):
    __tablename__ = "week_assessment_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    week_assessment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("week_assessments.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    # Stored report for the attempt (JSON string). Generated when passing (>=70%).
    report_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    week_assessment: Mapped["WeekAssessment"] = relationship("WeekAssessment", back_populates="attempts")
    user: Mapped["User"] = relationship("User")