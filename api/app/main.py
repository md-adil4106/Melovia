"""Main entrypoint for Melovia FastAPI application."""

import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.errors import register_exception_handlers
from app.llm.client import get_llm_client
from app.llm.polish import LLMPolishService
from app.logging import RequestLoggingMiddleware, logger, setup_logging
from app.recsys.catalog import CatalogCorruptError, CatalogStore
from app.routers.feedback import router as feedback_router
from app.routers.health import router as health_router
from app.routers.playlist import router as playlist_router
from app.routers.recommendations import router as recommendations_router
from app.routers.refine import router as refine_router
from app.routers.taste import router as taste_router
from app.routers.tracks import router as tracks_router
from app.routers.universe import router as universe_router
from app.session.store import global_session_store


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and teardown lifecycle."""
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)
    logger.info("Starting Melovia API backend", extra={"env": settings.ENV, "version": "0.1.0"})

    # Ensure database schema is initialized
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.settings = settings
    app.state.llm_polish_service = LLMPolishService(enabled=settings.EXPLAIN_LLM_POLISH)
    app.state.llm_client = get_llm_client(settings)
    app.state.session_store = global_session_store

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
    app.include_router(recommendations_router)
    app.include_router(refine_router)
    app.include_router(feedback_router)
    app.include_router(playlist_router)
    app.include_router(taste_router)
    app.include_router(universe_router)

    return app


app = create_app()
