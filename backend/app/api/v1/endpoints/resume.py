"""
app/api/v1/endpoints/resume.py
Resume upload endpoint.
Returns a job_id immediately — processing happens asynchronously.
"""
import hashlib
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.models import Resume, User
from app.schemas.resume import ResumeResponse, ResumeStatusResponse
import json
from app.models.models import Skill

router = APIRouter(prefix="/resumes", tags=["resumes"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def normalize_uuid(value: str) -> str:
    """Accept UUID with or without dashes, always return with dashes."""
    clean = value.replace("-", "")
    if len(clean) == 32:
        return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"
    return value

def compute_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


async def save_file(content: bytes, filename: str) -> str:
    """Save uploaded file to upload dir and return the path."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{filename}"
    path = os.path.join(settings.upload_dir, safe_name)
    with open(path, "wb") as f:
        f.write(content)
    return path


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(
    file: Annotated[UploadFile, File(description="PDF or DOCX resume")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a resume for processing.

    Returns immediately with a job_id.
    Poll /resumes/{job_id}/status to check progress.
    Full result available at /resumes/{job_id}/results once status = complete.

    Duplicate detection: same user + identical file bytes (MD5 ``file_hash``) returns the
    existing row and ``job_id`` instead of creating a new upload.
    """
    # ── Validate file type ────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Upload PDF or DOCX.",
        )

    content = await file.read()

    # ── Validate file size ────────────────────────────────────────────────────
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )

    # ── Dedup check ───────────────────────────────────────────────────────────
    file_hash = compute_hash(content)
    existing = await db.execute(
        select(Resume).where(
            Resume.file_hash == file_hash,
            Resume.user_id == current_user.id,
        )
    )
    duplicate = existing.scalar_one_or_none()
    if duplicate:
        # Return the existing record instead of re-processing
        return ResumeResponse(
            id=duplicate.id,
            job_id=duplicate.job_id,
            file_name=duplicate.file_name,
            status=duplicate.status,
            message="Duplicate resume — returning existing processing result",
        )

    # ── Save file ─────────────────────────────────────────────────────────────
    file_path = await save_file(content, file.filename or "resume")
    file_type = ALLOWED_TYPES[file.content_type]

    # ── Create DB record ──────────────────────────────────────────────────────
    resume = Resume(
        user_id   = current_user.id,
        file_name = file.filename or "resume",
        file_type = file_type,
        file_hash = file_hash,
        file_path = file_path,
        status    = "uploaded",
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)

    # TODO Week 2: dispatch async processing job here
    # await job_queue.enqueue("process_resume", resume_id=str(resume.id))

    return ResumeResponse(
        id       = resume.id,
        job_id   = resume.job_id,
        file_name= resume.file_name,
        status   = resume.status,
        message  = "Resume uploaded successfully. Processing will begin shortly.",
    )


@router.get("/{job_id}/status", response_model=ResumeStatusResponse)
async def get_status(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Poll processing status for a resume job."""
    normalized = normalize_uuid(job_id)
    raw = job_id.replace("-", "")

    result = await db.execute(
        select(Resume).where(
            Resume.job_id.in_([job_id, normalized, raw]),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Job not found")

    return ResumeStatusResponse(
        job_id          = resume.job_id,
        status          = resume.status,
        parse_confidence= resume.parse_confidence,
        error_message   = resume.error_message,
    )


@router.post("/{job_id}/process", status_code=status.HTTP_200_OK)
async def process_resume(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    ):
    """
    Trigger full processing pipeline for an uploaded resume.
    Runs: parse → quality check → skill extraction → normalize → save

    If this resume is already ``complete``, returns 200 with ``already_processed: true``
    (no re-run) so clients can continue with status poll and GET /results.
    """
    from app.services.parsing.resume_processor import process_resume as run_pipeline

    normalized = normalize_uuid(job_id)
    raw = job_id.replace("-", "")

    result = await db.execute(
        select(Resume).where(
            Resume.job_id.in_([job_id, normalized, raw]),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.status == "complete":
        # Idempotent: re-uploading the same file returns the same job_id (see upload dedup);
        # calling process again should succeed so clients can run the same flow (poll → results).
        return {
            "resume_id": resume.id,
            "job_id": resume.job_id,
            "status": "complete",
            "parse_confidence": resume.parse_confidence,
            "already_processed": True,
            "message": "Resume was already processed; stored extraction is unchanged.",
        }

    summary = await run_pipeline(resume.id, db)
    return summary


@router.get("/{job_id}/results")
async def get_results(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Get full extraction results for a processed resume.
    Returns skill list with proficiency, confidence, source section.
    """
    normalized = normalize_uuid(job_id)
    raw = job_id.replace("-", "")

    result = await db.execute(
        select(Resume).where(
            Resume.job_id.in_([job_id, normalized, raw]),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.status != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Resume not yet processed. Current status: {resume.status}"
        )

    # Fetch all extracted skills with skill details
    from app.models.models import ExtractedSkill as ESModel
    from app.models.models import UserSkillScore

    skills_result = await db.execute(
        select(ESModel, Skill, UserSkillScore)
        .join(Skill, ESModel.skill_id == Skill.id)
        .outerjoin(
            UserSkillScore,
            (UserSkillScore.skill_id == Skill.id) &
            (UserSkillScore.user_id == current_user.id)
        )
        .where(ESModel.resume_id == resume.id)
        .order_by(ESModel.confidence.desc())
    )
    rows = skills_result.fetchall()

    skills_output = []
    for es, skill, score in rows:
        skills_output.append({
            "skill_name":       skill.name,
            "category":         skill.skill_type,
            "confidence":       round(es.confidence, 3),
            "proficiency":      score.proficiency if score else "beginner",
            "source_section":   es.source_section,
            "frequency":        es.frequency,
            "years_experience": score.years_of_experience if score else 0,
            "extractor":        es.extractor,
        })

    return {
        "resume_id":        resume.id,
        "file_name":        resume.file_name,
        "parse_confidence": resume.parse_confidence,
        "layout_type":      resume.layout_type,
        "sections_found": [k for k in json.loads(resume.parsed_sections).keys() if not k.startswith("misc_")] if resume.parsed_sections else [],
        "total_skills":     len(skills_output),
        "skills":           skills_output,
    }