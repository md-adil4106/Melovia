"""Health check endpoint."""

from fastapi import APIRouter, Request

from app.schemas.health import CatalogStatus, HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns the current operational status, API version, and catalog state.",
)
async def get_health(request: Request) -> HealthResponse:
    catalog_status: CatalogStatus | None = None
    store = getattr(request.app.state, "catalog_store", None)
    if store is not None:
        catalog_status = CatalogStatus(
            version=store.manifest.version,
            track_count=store.track_count,
            plan=store.manifest.plan,
        )

    return HealthResponse(
        status="ok",
        version="0.1.0",
        catalog=catalog_status,
    )
