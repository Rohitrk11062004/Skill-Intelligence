"""
app/api/v1/endpoints/features.py
Placeholders for UI feature flags.
"""
from fastapi import APIRouter
from app.schemas.features import FeatureHealthResponse

reports_router = APIRouter(prefix="/reports", tags=["features"])
talent_map_router = APIRouter(prefix="/talent-map", tags=["features"])

@reports_router.get("/health", response_model=FeatureHealthResponse)
async def reports_health():
    return FeatureHealthResponse(enabled=False, message="Coming soon")

@talent_map_router.get("/health", response_model=FeatureHealthResponse)
async def talent_map_health():
    return FeatureHealthResponse(enabled=False, message="Coming soon")
