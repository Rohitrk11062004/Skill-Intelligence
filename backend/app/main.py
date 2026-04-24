"""
app/main.py
FastAPI application factory.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import (  # noqa: F401
    AsyncSessionLocal,
    engine,
    Base,
    activate_cached_statement_recovery_window,
    dispose_engine_for_cached_statement_error,
    is_cached_statement_recovery_active,
    is_invalid_cached_statement_error,
)

log = structlog.get_logger()


def _is_llm_record(record: logging.LogRecord) -> bool:
    name = str(record.name or "")
    if name.startswith("app.services.llm"):
        return True
    message = ""
    try:
        message = record.getMessage()
    except Exception:
        message = str(record.msg or "")
    return "llm_call" in str(message)


class IncludeLLMFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return _is_llm_record(record)


class ExcludeLLMFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _is_llm_record(record)

def _configure_logging() -> None:
    """
    Configure file + console logging for local observability.
    Writes to backend/logs/app.log.
    """
    backend_root = Path(__file__).resolve().parents[1]
    logs_dir = backend_root / "logs"
    app_log_path = logs_dir / "app.log"
    llm_log_path = logs_dir / "llm.log"
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    has_file_handler = any(
        isinstance(handler, RotatingFileHandler) and getattr(handler, "name", "") == "skill_file"
        for handler in root.handlers
    )
    if not has_file_handler:
        file_handler = RotatingFileHandler(
            app_log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.set_name("skill_file")
        file_handler.setFormatter(fmt)
        file_handler.addFilter(ExcludeLLMFilter())
        root.addHandler(file_handler)

    for handler in root.handlers:
        if getattr(handler, "name", "") != "skill_file":
            continue
        if not any(isinstance(existing_filter, ExcludeLLMFilter) for existing_filter in handler.filters):
            handler.addFilter(ExcludeLLMFilter())

    has_llm_file_handler = any(
        isinstance(handler, RotatingFileHandler) and getattr(handler, "name", "") == "skill_llm_file"
        for handler in root.handlers
    )
    if not has_llm_file_handler:
        llm_handler = RotatingFileHandler(
            llm_log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        llm_handler.set_name("skill_llm_file")
        llm_handler.setFormatter(fmt)
        llm_handler.addFilter(IncludeLLMFilter())
        root.addHandler(llm_handler)

    for handler in root.handlers:
        if getattr(handler, "name", "") != "skill_llm_file":
            continue
        if not any(isinstance(existing_filter, IncludeLLMFilter) for existing_filter in handler.filters):
            handler.addFilter(IncludeLLMFilter())

    has_console_handler = any(getattr(handler, "name", "") == "skill_console" for handler in root.handlers)
    if not has_console_handler:
        console = logging.StreamHandler()
        console.set_name("skill_console")
        console.setFormatter(fmt)
        root.addHandler(console)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _sync_tracing_env() -> None:
    """Expose tracing settings to the LangSmith client (reads os.environ)."""
    if settings.langchain_api_key:
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langchain_api_key)
    if settings.langchain_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ.setdefault("LANGSMITH_TRACING", "true")
    if settings.langchain_project:
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langchain_project)


async def _ensure_sqlite_schema() -> None:
    """
    SQLite does not support ALTERs via create_all(). For local dev we apply
    tiny additive migrations to keep the DB in sync with models.
    """
    if "sqlite" not in (settings.database_url or "").lower():
        return

    async with engine.begin() as conn:
        # Add `skills.skill_band` if missing (older DBs won't have it).
        columns = await conn.execute(text("PRAGMA table_info(skills)"))
        names = {row[1] for row in columns.fetchall()}  # (cid, name, type, notnull, dflt, pk)
        if "skill_band" not in names:
            await conn.execute(text("ALTER TABLE skills ADD COLUMN skill_band VARCHAR(50)"))
            log.info("sqlite_migration_applied", table="skills", column="skill_band")

        # Add `learning_plan_items.skill_band` if missing.
        columns = await conn.execute(text("PRAGMA table_info(learning_plan_items)"))
        names = {row[1] for row in columns.fetchall()}
        if "skill_band" not in names:
            await conn.execute(text("ALTER TABLE learning_plan_items ADD COLUMN skill_band VARCHAR(50)"))
            log.info("sqlite_migration_applied", table="learning_plan_items", column="skill_band")

        if "subtopics_json" not in names:
            await conn.execute(text("ALTER TABLE learning_plan_items ADD COLUMN subtopics_json TEXT"))
            log.info("sqlite_migration_applied", table="learning_plan_items", column="subtopics_json")

        if "priority_score" not in names:
            await conn.execute(text("ALTER TABLE learning_plan_items ADD COLUMN priority_score FLOAT DEFAULT 0.0"))
            log.info("sqlite_migration_applied", table="learning_plan_items", column="priority_score")

        if "skill_rationale" not in names:
            await conn.execute(text("ALTER TABLE learning_plan_items ADD COLUMN skill_rationale TEXT"))
            log.info("sqlite_migration_applied", table="learning_plan_items", column="skill_rationale")

        if "assessment_questions" not in names:
            await conn.execute(text("ALTER TABLE learning_plan_items ADD COLUMN assessment_questions TEXT"))
            log.info("sqlite_migration_applied", table="learning_plan_items", column="assessment_questions")

        if "assessment_score" not in names:
            await conn.execute(text("ALTER TABLE learning_plan_items ADD COLUMN assessment_score FLOAT"))
            log.info("sqlite_migration_applied", table="learning_plan_items", column="assessment_score")

        if "assessment_attempts" not in names:
            await conn.execute(
                text("ALTER TABLE learning_plan_items ADD COLUMN assessment_attempts INTEGER NOT NULL DEFAULT 0")
            )
            log.info("sqlite_migration_applied", table="learning_plan_items", column="assessment_attempts")

        columns = await conn.execute(text("PRAGMA table_info(learning_plans)"))
        names = {row[1] for row in columns.fetchall()}
        if "completed_at" not in names:
            await conn.execute(text("ALTER TABLE learning_plans ADD COLUMN completed_at DATETIME"))
            log.info("sqlite_migration_applied", table="learning_plans", column="completed_at")


async def _check_postgres_schema_health() -> None:
    """Log a clear error when required Postgres columns are missing."""
    required_columns = {
        "assessment_questions",
        "assessment_score",
        "assessment_attempts",
    }

    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'learning_plan_items'
                    """
                )
            )
            existing_columns = {row[0] for row in rows.fetchall()}

        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            log.error(
                "database_schema_out_of_date",
                table="learning_plan_items",
                missing_columns=missing_columns,
                detail="Database schema out of date; run alembic upgrade head",
            )
    except Exception as exc:
        log.warning("postgres_schema_health_check_failed", reason=str(exc))


async def _ensure_postgres_additive_schema() -> None:
    """
    Apply tiny additive migrations for Postgres in dev environments.
    This keeps the app usable without requiring an alembic run for small additions.
    """
    if "sqlite" in (settings.database_url or "").lower():
        return
    try:
        async with engine.begin() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'week_assessment_attempts'
                    """
                )
            )
            existing = {row[0] for row in rows.fetchall()}
            if "report_json" not in existing:
                await conn.execute(text("ALTER TABLE week_assessment_attempts ADD COLUMN report_json TEXT"))
                log.info("postgres_migration_applied", table="week_assessment_attempts", column="report_json")
            if "report_generated_at" not in existing:
                await conn.execute(
                    text("ALTER TABLE week_assessment_attempts ADD COLUMN report_generated_at TIMESTAMPTZ")
                )
                log.info(
                    "postgres_migration_applied",
                    table="week_assessment_attempts",
                    column="report_generated_at",
                )
    except Exception as exc:
        log.warning("postgres_additive_migration_failed", reason=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup + shutdown logic."""
    # ── Startup ───────────────────────────────────────────────────────────────
    _configure_logging()
    _sync_tracing_env()
    db_kind = "sqlite" if "sqlite" in (settings.database_url or "").lower() else "postgres"
    log.info("starting_up", env=settings.app_env, version=settings.app_version, db_kind=db_kind)

    if db_kind == "sqlite":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await _ensure_sqlite_schema()
        log.info("database_ready", db_kind=db_kind, schema_strategy="create_all+sqlite_alters")
    else:
        # For Postgres (Neon), schema is managed by Alembic.
        log.info("database_ready", db_kind=db_kind, schema_strategy="alembic")
        await _ensure_postgres_additive_schema()
        await _check_postgres_schema_health()

    # Warm up skill normalizer (builds alias index from DB)
    try:
        from app.services.normalization.skill_normalizer import skill_normalizer
        async with AsyncSessionLocal() as db:
            await skill_normalizer.initialize(db)
        log.info("skill_normalizer_ready")
    except Exception as e:
        log.warning("skill_normalizer_init_skipped", reason=str(e))

    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────
    await engine.dispose()
    log.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def log_requests(request, call_next):
        from time import perf_counter
        start = perf_counter()

        if request.url.path != "/health" and is_cached_statement_recovery_active():
            response = JSONResponse(
                status_code=503,
                content={
                    "detail": "Database prepared statement cache invalid; restart app after migrations.",
                },
            )
            elapsed_ms = int((perf_counter() - start) * 1000)
            log.info(
                "request_complete",
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )
            return response

        try:
            response = await call_next(request)
        except Exception as exc:
            if is_invalid_cached_statement_error(exc):
                await dispose_engine_for_cached_statement_error()
                activate_cached_statement_recovery_window(seconds=120)
                log.error(
                    "db_prepared_statement_cache_invalid",
                    method=request.method,
                    path=str(request.url.path),
                    detail="DB prepared statement cache invalid; restart app after migrations",
                )
                response = JSONResponse(
                    status_code=503,
                    content={
                        "detail": "Database cache is refreshing after migrations. Please retry shortly and restart the app.",
                    },
                )
            else:
                log.exception("request_failed", method=request.method, path=str(request.url.path))
                raise
        finally:
            elapsed_ms = int((perf_counter() - start) * 1000)
            status_code = getattr(locals().get("response"), "status_code", None)
            log.info(
                "request_complete",
                method=request.method,
                path=str(request.url.path),
                status_code=status_code,
                elapsed_ms=elapsed_ms,
            )
        return response

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
