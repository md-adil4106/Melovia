"""Pytest fixtures for Melovia API tests."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.recsys.catalog import CatalogStore


@pytest.fixture(autouse=True)
def setup_catalog_store() -> None:
    """Ensure catalog store is loaded from data/bundles/v1 if present."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    bundle_path = repo_root / "data" / "bundles" / "v1"
    if bundle_path.exists():
        app.state.catalog_store = CatalogStore.load(bundle_path)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client bound directly to FastAPI application instance."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
