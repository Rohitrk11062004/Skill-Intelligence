"""
app/schemas/features.py
Schemas for feature flags.
"""
from pydantic import BaseModel


class FeatureHealthResponse(BaseModel):
    enabled: bool
    message: str = "Coming soon"
