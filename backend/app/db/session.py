"""
app/db/session.py
Async SQLAlchemy engine + session factory.
Uses SQLite for local development — no installation needed.
"""
import logging
from typing import AsyncGenerator
from time import monotonic

from sqlalchemy import event
from sqlalchemy.exc import DBAPIError, InterfaceError as SAInterfaceError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── URL normalization ─────────────────────────────────────────────────────────
def _normalize_asyncpg_url(url: str) -> tuple[str, dict]:
    """
    Neon (and libpq-style URLs) often include query params like `sslmode` and
    `channel_binding` that asyncpg does not accept.
    """
    url = str(url or "")
    connect_args: dict = {}
    if url.startswith("postgresql+asyncpg://") and ("sslmode=" in url or "channel_binding=" in url):
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        sslmode = query.pop("sslmode", None)
        query.pop("channel_binding", None)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        if sslmode and sslmode.lower() in {"require", "verify-ca", "verify-full"}:
            connect_args["ssl"] = True
    return url, connect_args


# ── Engine ────────────────────────────────────────────────────────────────────
db_url, extra_connect_args = _normalize_asyncpg_url(settings.database_url)
_is_sqlite = "sqlite" in (settings.database_url or "").lower()
engine_kwargs = {
    "connect_args": {
        "check_same_thread": False,
        "timeout": 30,
    } if _is_sqlite else extra_connect_args,
    "echo": False,
}
if not _is_sqlite:
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    )

engine = create_async_engine(db_url, **engine_kwargs)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    _ = connection_record
    if "sqlite" not in settings.database_url:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ── Base class for all ORM models ─────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


_cached_statement_recovery_until = 0.0


def _walk_exception_chain(exc: BaseException | None):
    seen = set()
    current = exc
    while current and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = getattr(current, "orig", None) or getattr(current, "__cause__", None)


def is_connection_closed_error(exc: BaseException) -> bool:
    for current in _walk_exception_chain(exc):
        message = str(current).lower()
        if "connection is closed" not in message:
            continue

        module_name = (getattr(current.__class__, "__module__", "") or "").lower()
        class_name = current.__class__.__name__
        if isinstance(current, SAInterfaceError):
            return True
        if class_name == "InterfaceError" and "asyncpg" in module_name:
            return True
    return False


def is_invalid_cached_statement_error(exc: BaseException) -> bool:
    for current in _walk_exception_chain(exc):
        name = current.__class__.__name__
        message = str(current)
        if "InvalidCachedStatementError" in name or "InvalidCachedStatementError" in message:
            return True
        if isinstance(current, DBAPIError) and "cached statement plan is invalid" in message.lower():
            return True
    return False


def activate_cached_statement_recovery_window(seconds: int = 120) -> None:
    global _cached_statement_recovery_until
    _cached_statement_recovery_until = monotonic() + max(1, int(seconds))


def is_cached_statement_recovery_active() -> bool:
    return monotonic() < _cached_statement_recovery_until


async def dispose_engine_for_cached_statement_error() -> None:
    await engine.dispose()


async def dispose_engine_for_connection_retry() -> None:
    await engine.dispose()


async def execute_with_reconnect_retry(
    session: AsyncSession,
    statement,
    *,
    logger: logging.Logger | None = None,
    method: str | None = None,
    path: str | None = None,
):
    """Execute a statement and retry once if the pooled DB connection was closed."""
    try:
        return await session.execute(statement)
    except Exception as exc:
        if not is_connection_closed_error(exc):
            raise

        await dispose_engine_for_connection_retry()
        if logger:
            try:
                logger.warning(
                    "db_reconnect_retry",
                    method=method,
                    path=path,
                    detail="DB connection closed; disposed engine and retried once",
                )
            except TypeError:
                logger.warning(
                    "db_reconnect_retry method=%s path=%s detail=%s",
                    method,
                    path,
                    "DB connection closed; disposed engine and retried once",
                )

        async with AsyncSessionLocal() as retry_session:
            return await retry_session.execute(statement)


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise