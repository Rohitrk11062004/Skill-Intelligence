"""Admin catalog maintenance endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.admin import require_admin
from app.db.session import get_db
from app.models.models import User
from app.services.catalog_service import validate_catalog_urls

router = APIRouter(prefix="/admin/catalog", tags=["catalog"])


@router.post("/validate-urls")
async def validate_catalog_urls_endpoint(
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    return await validate_catalog_urls(db)
