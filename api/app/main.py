"""Main entrypoint for Melovia FastAPI application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_exception_handlers
from app.logging import RequestLoggingMiddleware, logger, setup_logging
from app.recsys.catalog import CatalogCorruptError, CatalogStore
from app.routers.health import router as health_router
from app.routers.tracks import router as tracks_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and teardown lifecycle."""
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)
    logger.info("Starting Melovia API backend", extra={"env": settings.ENV, "version": "0.1.0"})

    # Mount immutable vector catalog bundle
    bundle_path = Path(settings.CATALOG_BUNDLE_PATH)
    if not bundle_path.is_absolute() and not bundle_path.exists():
        # Check relative to project root if running from api/ subdirectory
        repo_root_path = Path(__file__).resolve().parent.parent.parent / bundle_path
        if repo_root_path.exists():
            bundle_path = repo_root_path

    if bundle_path.exists():
        try:
            logger.info(f"Loading catalog bundle from {bundle_path}...")
            store = CatalogStore.load(bundle_path)
            app.state.catalog_store = store
            logger.info(
                f"Mounted catalog bundle v{store.manifest.version} ({store.track_count} tracks)",
                extra={
                    "catalog_version": store.manifest.version,
                    "catalog_track_count": store.track_count,
                    "catalog_plan": store.manifest.plan,
                },
            )
        except CatalogCorruptError as e:
            logger.critical(f"FATAL: Catalog bundle checksum verification failed: {e}")
            raise
        except Exception as e:
            logger.critical(f"FATAL: Error loading catalog bundle: {e}")
            raise
    else:
        logger.warning(
            f"Catalog bundle path does not exist: {bundle_path}. Running with unmounted catalog."
        )
        app.state.catalog_store = None

    yield

    app.state.catalog_store = None
    logger.info("Shutting down Melovia API backend")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="Melovia API",
        description="Explainable, user-steerable music-discovery engine",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Middleware execution order: Last added executes first
    # 1. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.API_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Structured request logging and latency tracking
    app.add_middleware(RequestLoggingMiddleware)

    # Centralized exception handlers
    register_exception_handlers(app)

    # Include routers
    app.include_router(health_router)
    app.include_router(tracks_router)

    return app


app = create_app()
