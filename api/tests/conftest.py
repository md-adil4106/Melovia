"""Pytest fixtures for AMDE API tests."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client bound directly to FastAPI application instance."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
