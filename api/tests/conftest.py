"""Pytest fixtures for Melovia API tests."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

# Configure test database before any app module import
test_db = Path(__file__).resolve().parent / "test_suite.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db.as_posix()}"
os.environ["TESTING"] = "1"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.recsys.catalog import CatalogStore  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db() -> None:
    yield
    if test_db.exists():
        try:
            test_db.unlink()
        except Exception:
            pass


@pytest.fixture(autouse=True)
async def init_test_db() -> None:
    """Ensure all database tables exist before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
