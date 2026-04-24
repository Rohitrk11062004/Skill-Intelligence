"""app/api/v1/endpoints/roles.py"""
from typing import Annotated
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.admin import require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.models import Role, RoleSkillRequirement, Skill, User
from app.schemas.roles import (
    RoleListItem,
    RoleSkillsResponse,
    RoleSkillItem,
    RoleSkillsUpdateRequest,
)
from app.services.extraction import llm_extractor
from app.services.parsing.resume_parser import resume_parser

router = APIRouter(prefix="/roles", tags=["roles"])


async def _save_upload(content: bytes, filename: str) -> str:
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{filename}"
    path = os.path.join(settings.upload_dir, safe_name)
    with open(path, "wb") as f:
        f.write(content)
    return path


@router.get("/skills/search")
async def search_skills(
    _: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    query: str = Query(default=""),
):
    stmt = select(Skill).order_by(Skill.name.asc()).limit(100)
    q = query.strip().lower()
    if q:
        stmt = stmt.where(func.lower(Skill.name).contains(q))

    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": skill.id,
            "name": skill.name,
            "category": skill.category,
        }
        for skill in rows
    ]


@router.get("", response_model=list[RoleListItem])
async def list_roles(
    _: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Role.id,
            Role.name,
            Role.department,
            Role.seniority_level,
            func.count(RoleSkillRequirement.id).label("skill_count"),
        )
        .outerjoin(RoleSkillRequirement, RoleSkillRequirement.role_id == Role.id)
        .group_by(Role.id)
        .order_by(Role.name.asc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        RoleListItem(
            id=row.id,
            name=row.name,
            department=row.department,
            seniority_level=row.seniority_level,
            skill_count=row.skill_count,
        )
        for row in rows
    ]


@router.post("/ingest-jd")
async def ingest_jd(
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(description="JD file (DOCX)"),
    role_name: str = Form(...),
    department: str | None = Form(default=None),
    seniority_level: str | None = Form(default=None),
):
    if file.content_type not in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        raise HTTPException(status_code=415, detail="Unsupported file type. Upload a DOCX.")

    raw_name = str(role_name or "").strip()
    if not raw_name:
        raise HTTPException(status_code=422, detail="role_name is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    file_path = await _save_upload(content, file.filename or "jd.docx")
    parsed = resume_parser.parse(file_path)

    extracted = await llm_extractor.extract(parsed.raw_text, sections=parsed.sections)
    extracted = [s for s in extracted if str(s.name or "").strip()]

    # Upsert role (case-insensitive)
    role = await db.scalar(select(Role).where(func.lower(Role.name) == raw_name.lower()))
    if not role:
        role = Role(name=raw_name, department=department, seniority_level=seniority_level, is_custom=True)
        db.add(role)
        await db.flush()
    else:
        if department is not None:
            role.department = department
        if seniority_level is not None:
            role.seniority_level = seniority_level
        db.add(role)
        await db.flush()

    # Upsert skills + requirements
    created_skills = 0
    linked = 0
    for s in extracted:
        skill_name = str(s.name).strip()
        existing_skill = await db.scalar(select(Skill).where(func.lower(Skill.name) == skill_name.lower()))
        if not existing_skill:
            existing_skill = Skill(
                name=skill_name,
                skill_type="technical",
                category=str(s.category or "technical"),
                source_role=role.name,
            )
            db.add(existing_skill)
            await db.flush()
            created_skills += 1

        importance = float(s.confidence or 0.8)
        importance = max(0.0, min(1.0, importance))
        is_mandatory = bool((s.confidence or 0.0) >= 0.85)

        req = await db.scalar(
            select(RoleSkillRequirement).where(
                RoleSkillRequirement.role_id == role.id,
                RoleSkillRequirement.skill_id == existing_skill.id,
            )
        )
        if not req:
            req = RoleSkillRequirement(
                role_id=role.id,
                skill_id=existing_skill.id,
                importance=importance,
                is_mandatory=is_mandatory,
                min_proficiency="intermediate",
            )
            db.add(req)
            linked += 1

    await db.commit()

    return {
        "role_id": role.id,
        "role_name": role.name,
        "file_name": file.filename,
        "extracted_skill_count": len(extracted),
        "created_skills": created_skills,
        "linked_requirements": linked,
    }


@router.get("/{role_id}/skills", response_model=RoleSkillsResponse)
async def get_role_skills(
    role_id: str,
    _: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    stmt = (
        select(RoleSkillRequirement, Skill)
        .join(Skill, Skill.id == RoleSkillRequirement.skill_id)
        .where(RoleSkillRequirement.role_id == role_id)
        .order_by(RoleSkillRequirement.is_mandatory.desc(), RoleSkillRequirement.importance.desc(), Skill.name.asc())
    )
    rows = (await db.execute(stmt)).all()

    skills = [
        RoleSkillItem(
            skill_id=skill.id,
            skill_name=skill.name,
            category=skill.category,
            importance=req.importance,
            is_mandatory=req.is_mandatory,
            min_proficiency=req.min_proficiency,
        )
        for req, skill in rows
    ]

    return RoleSkillsResponse(
        role_id=role.id,
        role_name=role.name,
        department=role.department,
        seniority_level=role.seniority_level,
        skills=skills,
    )


@router.put("/{role_id}/skills", response_model=RoleSkillsResponse)
async def replace_role_skills(
    role_id: str,
    payload: RoleSkillsUpdateRequest,
    _: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    await db.execute(delete(RoleSkillRequirement).where(RoleSkillRequirement.role_id == role_id))

    for item in payload.skills:
        skill = None
        if item.skill_id:
            skill = await db.scalar(select(Skill).where(Skill.id == item.skill_id))
        elif item.skill_name:
            skill = await db.scalar(select(Skill).where(func.lower(Skill.name) == item.skill_name.lower()))

        if not skill and item.skill_name:
            skill = Skill(
                name=item.skill_name,
                skill_type="technical",
                category=item.category or "Technical Skills",
                source_role=role.name,
            )
            db.add(skill)
            await db.flush()

        if not skill:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each item must provide valid skill_id or skill_name",
            )

        req = RoleSkillRequirement(
            role_id=role_id,
            skill_id=skill.id,
            importance=item.importance,
            is_mandatory=item.is_mandatory,
            min_proficiency=item.min_proficiency,
        )
        db.add(req)

    await db.flush()

    return await get_role_skills(role_id=role_id, _=_, db=db)


@router.delete("/{role_id}")
async def delete_role(
    role_id: str,
    _: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    await db.execute(delete(RoleSkillRequirement).where(RoleSkillRequirement.role_id == role_id))
    await db.delete(role)
    await db.flush()

    return {"message": "Role deleted", "role_id": role_id}
