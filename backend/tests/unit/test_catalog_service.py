import pytest
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models.models import Base, ContentItem
from app.services.catalog_service import validate_catalog_urls


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self._calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def head(self, url: str):
        self._calls.append(("HEAD", url))
        if url == "https://example.com/head-unauthorized":
            return _FakeResponse(401)
        if url == "https://example.com/head-fallback":
            return _FakeResponse(405)
        if url == "https://example.com/good":
            return _FakeResponse(200)
        if url == "https://example.com/bad":
            return _FakeResponse(500)
        raise httpx.ConnectError("unreachable", request=httpx.Request("HEAD", url))

    async def get(self, url: str):
        self._calls.append(("GET", url))
        if url == "https://example.com/head-unauthorized":
            return _FakeResponse(200)
        if url == "https://example.com/head-fallback":
            return _FakeResponse(200)
        return _FakeResponse(500)


@pytest.mark.asyncio
async def test_validate_catalog_urls_deactivates_broken_rows(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.services.catalog_service.httpx.AsyncClient", _FakeAsyncClient)

    async with session_factory() as db:
        good = ContentItem(
            title="Good URL",
            source_url="https://example.com/good",
            difficulty_level="beginner",
            skill_tags=["Python"],
            provider="Docs",
            resource_format="doc",
            is_active=True,
        )
        fallback = ContentItem(
            title="Fallback URL",
            source_url="https://example.com/head-fallback",
            difficulty_level="beginner",
            skill_tags=["Python"],
            provider="Docs",
            resource_format="doc",
            is_active=True,
        )
        unauthorized = ContentItem(
            title="Unauthorized URL",
            source_url="https://example.com/head-unauthorized",
            difficulty_level="beginner",
            skill_tags=["Python"],
            provider="Docs",
            resource_format="doc",
            is_active=True,
        )
        broken = ContentItem(
            title="Broken URL",
            source_url="https://example.com/bad",
            difficulty_level="beginner",
            skill_tags=["Python"],
            provider="Docs",
            resource_format="doc",
            is_active=True,
        )
        empty = ContentItem(
            title="Empty URL",
            source_url=None,
            difficulty_level="beginner",
            skill_tags=["Python"],
            provider="Docs",
            resource_format="doc",
            is_active=True,
        )
        db.add_all([good, fallback, unauthorized, broken, empty])
        await db.commit()

        summary = await validate_catalog_urls(db)

        assert summary["total"] == 5
        assert summary["passed"] == 3
        assert summary["failed"] == 2
        assert len(summary["failed_urls"]) == 2
        assert {row["title"] for row in summary["failed_urls"]} == {"Broken URL", "Empty URL"}

        rows = (await db.execute(select(ContentItem))).scalars().all()
        active_by_title = {row.title: row.is_active for row in rows}
        assert active_by_title["Good URL"] is True
        assert active_by_title["Fallback URL"] is True
        assert active_by_title["Unauthorized URL"] is True
        assert active_by_title["Broken URL"] is False
        assert active_by_title["Empty URL"] is False

    await engine.dispose()
