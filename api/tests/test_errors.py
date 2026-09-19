"""Tests for error envelope compliance and stack trace suppression."""

import pytest
from fastapi import APIRouter
from httpx import AsyncClient
from pydantic import BaseModel

from app.errors import AppException
from app.main import app

# Test probe router to provoke various failure scenarios
error_probe_router = APIRouter(prefix="/test-errors", tags=["Testing"])


class SamplePayload(BaseModel):
    required_number: int


@error_probe_router.get("/app-exception")
async def trigger_app_exception() -> None:
    raise AppException(
        code="SAMPLE_DOMAIN_ERROR",
        message="Domain constraint violated",
        status_code=400,
    )


@error_probe_router.post("/validation-error")
async def trigger_validation_error(payload: SamplePayload) -> dict[str, int]:
    return {"number": payload.required_number}


@error_probe_router.get("/unhandled-error")
async def trigger_unhandled_error() -> None:
    # Deliberate runtime error with internal trace
    raise ZeroDivisionError("division by zero in critical section")


app.include_router(error_probe_router)


@pytest.mark.asyncio
async def test_404_error_envelope(async_client: AsyncClient) -> None:
    """Non-existent route returns standard error envelope with NOT_FOUND code."""
    response = await async_client.get("/non-existent-endpoint")
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "NOT_FOUND"
    assert "message" in error
    assert "request_id" in error
    assert isinstance(error["request_id"], str)
    assert len(error["request_id"]) > 0


@pytest.mark.asyncio
async def test_app_exception_envelope(async_client: AsyncClient) -> None:
    """Domain AppException returns proper status code and error details."""
    response = await async_client.get("/test-errors/app-exception")
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "SAMPLE_DOMAIN_ERROR"
    assert error["message"] == "Domain constraint violated"
    assert "request_id" in error


@pytest.mark.asyncio
async def test_validation_error_envelope(async_client: AsyncClient) -> None:
    """Pydantic validation errors return 422 with clean envelope without raw internals."""
    response = await async_client.post(
        "/test-errors/validation-error",
        json={"required_number": "not-a-number"},
    )
    assert response.status_code in (422, 400)

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert "required_number" in error["message"]
    assert "request_id" in error


@pytest.mark.asyncio
async def test_unhandled_exception_suppresses_stack_trace(async_client: AsyncClient) -> None:
    """500 Unhandled errors must never expose stack traces or internal exception details."""
    response = await async_client.get("/test-errors/unhandled-error")
    assert response.status_code == 500

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "INTERNAL_SERVER_ERROR"
    assert "request_id" in error

    raw_text = response.text
    # Ensure no python traceback keywords or internal details leak
    assert "Traceback" not in raw_text
    assert "ZeroDivisionError: division by zero in critical section" not in raw_text
    assert "File " not in raw_text
