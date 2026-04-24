"""Content management endpoints."""
import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.admin import require_admin
from app.api.v1.endpoints.auth import get_current_user
from app.db.session import get_db
from app.models.models import ContentChunk, ContentItem, Skill, SkillGap, User

router = APIRouter(prefix="/admin/content", tags=["content"])
public_router = APIRouter(prefix="/content", tags=["content"])


def _chunk_text(text: str, chunk_size: int = 1200) -> list[str]:
    normalized = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
    if not normalized:
        return []

    chunks = []
    current = ""
    for para in normalized.split("\n"):
        if len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            while len(para) > chunk_size:
                chunks.append(para[:chunk_size])
                para = para[chunk_size:]
            current = para
    if current:
        chunks.append(current)
    return chunks


@router.get("")
async def list_content(
    _: Annotated[object, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
    query: str = Query(default=""),
):
    stmt = (
        select(ContentItem, func.count(ContentChunk.id).label("chunk_count"))
        .outerjoin(ContentChunk, ContentChunk.content_item_id == ContentItem.id)
        .group_by(ContentItem.id)
        .order_by(ContentItem.created_at.desc())
    )

    q = query.strip().lower()
    if q:
        stmt = stmt.where(func.lower(ContentItem.title).contains(q))

    rows = (await db.execute(stmt)).all()
    return [
        {
            "title": item.title,
            "source_url": item.source_url,
            "difficulty_level": item.difficulty_level,
            "chunk_count": int(chunk_count or 0),
        }
        for item, chunk_count in rows
    ]


@router.post("/upload")
async def upload_content(
    _: Annotated[object, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    skill_tags: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    decoded = data.decode("utf-8", errors="ignore").strip()
    if not decoded:
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    resolved_title = (title or "").strip() or (file.filename or "Untitled Content")
    resolved_tags = [t.strip() for t in (skill_tags or "").split(",") if t.strip()]

    item = ContentItem(
        title=resolved_title,
        source_url=(source_url or "").strip() or None,
        difficulty_level="intermediate",
        skill_tags={"tags": resolved_tags},
        created_at=datetime.now(timezone.utc),
    )
    db.add(item)
    await db.flush()

    chunks = _chunk_text(decoded)
    for idx, chunk in enumerate(chunks):
        db.add(ContentChunk(content_item_id=item.id, chunk_text=chunk, chunk_index=idx))

    await db.flush()

    return {
        "message": "Content uploaded and indexed successfully",
        "title": item.title,
        "chunk_count": len(chunks),
    }


@router.delete("/{title}")
async def delete_content_by_title(
    title: str,
    _: Annotated[object, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    items = (
        await db.execute(select(ContentItem).where(ContentItem.title == title))
    ).scalars().all()

    if not items:
        raise HTTPException(status_code=404, detail="Content title not found")

    deleted = 0
    for item in items:
        deleted += int(
            await db.scalar(select(func.count(ContentChunk.id)).where(ContentChunk.content_item_id == item.id))
            or 0
        )
        await db.delete(item)

    await db.flush()
    return {"message": "Content deleted", "title": title, "chunk_count": deleted}


@public_router.get("/personalized")
async def get_personalized_content(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    gap_rows = (
        await db.execute(
            select(Skill.name)
            .join(SkillGap, SkillGap.skill_id == Skill.id)
            .where(SkillGap.user_id == current_user.id)
            .order_by(SkillGap.priority_score.desc())
            .limit(8)
        )
    ).scalars().all()
    target_skills = [s.lower() for s in gap_rows if s]

    items = (
        await db.execute(
            select(ContentItem)
            .order_by(ContentItem.created_at.desc())
            .limit(120)
        )
    ).scalars().all()

    scored: list[tuple[int, ContentItem, list[str]]] = []
    for item in items:
        tags = []
        if isinstance(item.skill_tags, dict):
            tags = [str(t).strip() for t in item.skill_tags.get("tags", []) if str(t).strip()]
        elif isinstance(item.skill_tags, str):
            try:
                parsed = json.loads(item.skill_tags)
                if isinstance(parsed, dict):
                    tags = [str(t).strip() for t in parsed.get("tags", []) if str(t).strip()]
            except Exception:
                tags = []

        text_blob = f"{item.title} {' '.join(tags)}".lower()
        matches = [skill for skill in target_skills if skill in text_blob]
        if target_skills and not matches:
            continue
        score = len(matches)
        scored.append((score, item, matches))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:12] if scored else [(0, i, []) for i in items[:12]]

    return [
        {
            "title": item.title,
            "source_url": item.source_url,
            "difficulty_level": item.difficulty_level,
            "matched_skills": matches,
        }
        for _, item, matches in top
    ]
