"""Health check schema."""

from pydantic import BaseModel, Field


class CatalogStatus(BaseModel):
    version: str = Field(..., description="Active catalog bundle version")
    track_count: int = Field(..., description="Total tracks in catalog bundle")
    plan: str = Field(..., description="Active catalog plan")


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service health indicator")
    version: str = Field(default="0.1.0", description="Current API build version")
    catalog: CatalogStatus | None = Field(
        default=None, description="Active catalog bundle status or null if unmounted"
    )
