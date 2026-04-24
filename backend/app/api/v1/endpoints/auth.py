"""
app/api/v1/endpoints/auth.py
Auth endpoints: register, login, get current user.
"""
import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.db.session import execute_with_reconnect_retry, get_db
from app.models.models import User
from app.schemas.auth import TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
HARDCODED_ADMIN_USERNAME = "admin"
HARDCODED_ADMIN_PASSWORD = "admin123"
HARDCODED_ADMIN_EMAIL = "admin@local.dev"
log = logging.getLogger(__name__)


# ── Dependencies ──────────────────────────────────────────────────────────────

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if not user_id:
        raise credentials_error

    method = request.method if request else None
    path = str(request.url.path) if request else None
    result = await execute_with_reconnect_retry(
        db,
        select(User).where(User.id == user_id),
        logger=log,
        method=method,
        path=path,
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_error
    return user


async def _get_or_create_hardcoded_admin(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == HARDCODED_ADMIN_EMAIL))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        username=HARDCODED_ADMIN_USERNAME,
        email=HARDCODED_ADMIN_EMAIL,
        hashed_password=hash_password(HARDCODED_ADMIN_PASSWORD),
        full_name="Admin User",
        department="Administration",
        job_title="Administrator",
        is_manager=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    # Check email not already taken
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    # Check username not already taken
    existing_username = await db.execute(
        select(User).where(func.lower(User.username) == str(payload.username).strip().lower())
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    requested_role = (payload.account_role or "").strip().lower()
    is_manager = requested_role in {"admin", "hr", "manager"}

    user = User(
        username=str(payload.username).strip(),
        email           = payload.email,
        hashed_password = hash_password(payload.password),
        full_name       = payload.full_name,
        department      = payload.department,
        job_title       = payload.job_title,
        is_manager      = is_manager,
    )
    db.add(user)
    await db.flush()   # get the generated UUID without committing
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    """Exchange credentials for a JWT access token."""
    identifier = form.username.strip()
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username is required",
        )
    identifier_lower = identifier.lower()

    # Local dev fallback credential used by Swagger/manual testing.
    if (
        identifier_lower == HARDCODED_ADMIN_USERNAME
        and form.password == HARDCODED_ADMIN_PASSWORD
    ):
        admin_user = await _get_or_create_hardcoded_admin(db)
        token = create_access_token(str(admin_user.id))
        return TokenResponse(access_token=token, token_type="bearer")

    bind = getattr(db, "bind", None)
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")

    def _local_part_expression():
        if dialect_name == "postgresql":
            return func.split_part(User.email, "@", 1)
        return func.substr(User.email, 1, func.instr(User.email, "@") - 1)

    # Accept login by full email or username as email local-part.
    result = await db.execute(
        select(User).where(
            or_(
                func.lower(User.username) == identifier_lower,
                func.lower(User.email) == identifier_lower,
                func.lower(_local_part_expression()) == identifier_lower,
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    """Return the currently authenticated user."""
    return current_user


@router.get("/oauth/{provider}/url")
async def oauth_provider_url(provider: str):
    return {
        "url": "not-configured",
        "provider": provider,
        "detail": "OAuth provider is not configured in this environment.",
    }


@router.post("/oauth/{provider}/callback")
async def oauth_provider_callback(provider: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"OAuth callback for provider '{provider}' is not configured.",
    )
