"""Health check schema."""

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service health indicator")
    version: str = Field(default="0.1.0", description="Current API build version")
    catalog: Any = Field(
        default=None, description="Active catalog bundle status or null if unmounted"
    )
