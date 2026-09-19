"""Health check endpoint."""

from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns the current operational status, API version, and catalog state.",
)
async def get_health() -> HealthResponse:
    # At this bootstrap phase, catalog bundle is unmounted and returns null
    return HealthResponse(
        status="ok",
        version="0.1.0",
        catalog=None,
    )
