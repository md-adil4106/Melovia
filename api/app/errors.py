"""Global exception handlers enforcing uniform error envelopes and no stack traces."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging import get_request_id

logger = logging.getLogger("melovia.api.errors")

HTTP_422 = (
    status.HTTP_422_UNPROCESSABLE_CONTENT
    if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT")
    else 422
)


class AppException(Exception):
    """Base application exception for Melovia domain errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _build_error_payload(code: str, message: str, req_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": req_id,
        }
    }


def _extract_request_id(request: Request) -> str:
    req_id = getattr(request.state, "request_id", None)
    if req_id:
        return str(req_id)
    return get_request_id()


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    req_id = _extract_request_id(request)
    logger.warning(
        f"Domain exception: {exc.code} - {exc.message}",
        extra={"request_id": req_id, "error_code": exc.code},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload(exc.code, exc.message, req_id),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    req_id = _extract_request_id(request)
    code_map = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
        status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    logger.warning(
        f"HTTP exception: {exc.status_code} {code} - {message}",
        extra={"request_id": req_id, "status_code": exc.status_code},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload(code, message, req_id),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    req_id = _extract_request_id(request)
    errors = exc.errors()
    messages = []
    for err in errors:
        loc = " -> ".join(str(item) for item in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        messages.append(f"{loc}: {msg}" if loc else msg)
    combined_message = "; ".join(messages) if messages else "Invalid request payload"

    logger.info(
        f"Validation error: {combined_message}",
        extra={"request_id": req_id, "validation_errors": errors},
    )
    return JSONResponse(
        status_code=HTTP_422,
        content=_build_error_payload("VALIDATION_ERROR", combined_message, req_id),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = _extract_request_id(request)
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={"request_id": req_id},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_build_error_payload(
            "INTERNAL_SERVER_ERROR",
            "An unexpected server error occurred. Reference request_id when reporting.",
            req_id,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized error handlers on the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)
