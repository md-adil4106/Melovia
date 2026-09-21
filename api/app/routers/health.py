"""Health check and observability metrics endpoints."""

from typing import Any

import psutil
from fastapi import APIRouter, Request
from sqlalchemy import text

from app.logging import global_metrics_tracker
from app.recsys.cache import global_candidate_cache
from app.schemas.health import CatalogStatus, HealthResponse
from app.session.store import global_session_store

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


@router.get(
    "/health/details",
    summary="Detailed Service Health and Observability Metrics",
    description=(
        "Returns detailed process telemetry, memory usage, request counts, stage latencies, "
        "and cache metrics without exposing secrets or personal data."
    ),
)
async def get_health_details(request: Request) -> dict[str, Any]:
    store = getattr(request.app.state, "catalog_store", None)
    catalog_info: dict[str, Any] = {
        "mounted": store is not None,
    }
    if store is not None:
        catalog_info.update(
            {
                "version": store.manifest.version,
                "track_count": store.track_count,
                "plan": store.manifest.plan,
                "dim_t": store.manifest.dim_t,
                "dim_a": store.manifest.dim_a,
                "regions_count": len(store.regions),
                "files_count": len(store.manifest.files),
            }
        )

    # Process Memory Telemetry
    try:
        proc = psutil.Process()
        mem_info = proc.memory_info()
        memory_stats = {
            "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
            "vms_mb": round(mem_info.vms / (1024 * 1024), 2),
        }
    except Exception:
        memory_stats = {"rss_mb": 0.0, "vms_mb": 0.0}

    # Database connectivity ping (degraded-mode awareness)
    db_status = "connected"
    try:
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "degraded"

    # Request and Latency Summary
    metrics_summary = global_metrics_tracker.get_summary()

    return {
        "status": "ok",
        "version": "0.1.0",
        "database": db_status,
        "process_memory": memory_stats,
        "telemetry": metrics_summary,
        "catalog": catalog_info,
        "cache": {
            "candidate_pools_cached": len(global_candidate_cache._cache),
            "active_sessions": len(global_session_store._sessions),
        },
    }
