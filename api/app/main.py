"""Main entrypoint for Melovia FastAPI application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_exception_handlers
from app.logging import RequestLoggingMiddleware, logger, setup_logging
from app.routers.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and teardown lifecycle."""
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)
    logger.info("Starting Melovia API backend", extra={"env": settings.ENV, "version": "0.1.0"})
    yield
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

    return app


app = create_app()
