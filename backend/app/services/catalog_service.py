"""Catalog resource lookup utilities for static content catalog."""

from __future__ import annotations

import asyncio
from collections import defaultdict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ContentItem


_ALLOWED_LEVELS = {"beginner", "intermediate", "advanced"}
_VIDEO_FORMATS = {"video", "course"}
_ARTICLE_FORMATS = {"article", "doc"}
_HEAD_FALLBACK_STATUS_CODES = {401, 403, 405}


def _normalize_level(level: str) -> str:
    value = str(level or "").strip().lower()
    return value if value in _ALLOWED_LEVELS else "intermediate"


def _normalize_skill(skill_name: str) -> str:
    return str(skill_name or "").strip().lower()


def _extract_skill_tags(raw_tags: object) -> list[str]:
    """Support current list format and legacy {'tags': [...]} payloads."""
    if isinstance(raw_tags, list):
        return [str(tag).strip().lower() for tag in raw_tags if str(tag).strip()]
    if isinstance(raw_tags, dict):
        tags = raw_tags.get("tags", [])
        if isinstance(tags, list):
            return [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    return []


def _level_fallback_chain(level: str) -> list[str]:
    normalized = _normalize_level(level)
    # Explicit fallback rules:
    # intermediate -> beginner
    # advanced -> intermediate
    # beginner -> intermediate
    if normalized == "intermediate":
        return ["intermediate", "beginner"]
    if normalized == "advanced":
        return ["advanced", "intermediate"]
    return ["beginner", "intermediate"]


def _to_result_item(item: ContentItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "url": item.source_url,
        "provider": item.provider,
        "format": item.resource_format,
        "duration_minutes": item.duration_minutes,
    }


async def is_url_reachable(client: httpx.AsyncClient, url: str) -> bool:
    normalized_url = str(url or "").strip()
    if not normalized_url:
        return False

    try:
        response = await client.head(normalized_url)
        if response.status_code in _HEAD_FALLBACK_STATUS_CODES:
            response = await client.get(normalized_url)
        return 200 <= response.status_code < 400
    except Exception:
        return False


async def validate_catalog_urls(db: AsyncSession) -> dict:
    """Validate active catalog URLs and deactivate broken rows.

    Null/empty URLs are treated as failures and deactivated so the catalog stays clean.
    """
    items = (
        await db.execute(
            select(ContentItem).where(ContentItem.is_active.is_(True))
        )
    ).scalars().all()

    semaphore = asyncio.Semaphore(10)
    failed_rows: list[dict] = []

    async def _check_item(client: httpx.AsyncClient, item: ContentItem) -> tuple[ContentItem, bool]:
        async with semaphore:
            return item, await is_url_reachable(client, str(item.source_url or ""))

    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        results = await asyncio.gather(*[_check_item(client, item) for item in items])

    passed = 0
    failed = 0
    for item, ok in results:
        if ok:
            passed += 1
            continue

        failed += 1
        item.is_active = False
        db.add(item)
        failed_rows.append({"id": item.id, "title": item.title, "url": item.source_url})

    await db.flush()
    await db.commit()

    return {
        "total": len(items),
        "passed": passed,
        "failed": failed,
        "failed_urls": failed_rows,
    }


async def get_resources_for_skill(
    db: AsyncSession,
    skill_name: str,
    level: str,
    limit_per_format: int = 1,
) -> dict:
    normalized_skill = _normalize_skill(skill_name)
    per_bucket_limit = max(1, int(limit_per_format or 1))

    if not normalized_skill:
        return {"video": [], "article": []}

    for current_level in _level_fallback_chain(level):
        rows = (
            await db.execute(
                select(ContentItem)
                .where(
                    ContentItem.is_active.is_(True),
                    ContentItem.difficulty_level == current_level,
                )
                .order_by(ContentItem.created_at.desc())
            )
        ).scalars().all()

        filtered = []
        for item in rows:
            tags = _extract_skill_tags(item.skill_tags)
            if normalized_skill in tags:
                filtered.append(item)

        if not filtered:
            continue

        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in filtered:
            fmt = str(item.resource_format or "").strip().lower()
            if fmt in _VIDEO_FORMATS and len(grouped["video"]) < per_bucket_limit:
                grouped["video"].append(_to_result_item(item))
            elif fmt in _ARTICLE_FORMATS and len(grouped["article"]) < per_bucket_limit:
                grouped["article"].append(_to_result_item(item))

            if (
                len(grouped["video"]) >= per_bucket_limit
                and len(grouped["article"]) >= per_bucket_limit
            ):
                break

        if grouped["video"] or grouped["article"]:
            return {
                "video": grouped["video"],
                "article": grouped["article"],
            }

    return {"video": [], "article": []}
