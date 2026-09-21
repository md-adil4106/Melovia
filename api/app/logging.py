"""Structured JSON logging with request_id context and latency middleware."""

import json
import logging
import sys
import threading
import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Context variable to correlate all logs within an active HTTP request
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the active request_id from context or a placeholder."""
    return request_id_ctx.get()


class JSONFormatter(logging.Formatter):
    """Formats log records as one-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
        }

        # Include additional structured extra fields if provided
        for key in ("method", "path", "status_code", "duration_ms", "client_ip", "stage"):
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)

        if record.exc_info and not record.exc_text:
            # Format exception internally for logs only (never leaked in HTTP responses)
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_obj["exception"] = record.exc_text

        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(debug: bool = False) -> None:
    """Configure the root logger with JSON formatting."""
    log_level = logging.DEBUG if debug else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Reduce noisiness from uvicorn access logger in favor of our middleware
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False


logger = logging.getLogger("melovia.api")


class MetricsTracker:
    """Thread-safe in-memory metrics collector for request counts, status codes, and latencies."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self._lock = threading.Lock()
        self.request_count = 0
        self.status_counts: dict[int, int] = {}
        self.endpoint_latencies: dict[str, list[float]] = {}

    def record_request(self, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self.request_count += 1
            self.status_counts[status_code] = self.status_counts.get(status_code, 0) + 1
            parts = [p for p in path.split("/") if p]
            prefix = f"/{parts[0]}" if parts else "/"
            if prefix not in self.endpoint_latencies:
                self.endpoint_latencies[prefix] = []
            samples = self.endpoint_latencies[prefix]
            if len(samples) >= 500:
                samples.pop(0)
            samples.append(duration_ms)

    def get_summary(self) -> dict[str, Any]:
        with self._lock:
            uptime = round(time.time() - self.start_time, 2)
            endpoint_stats: dict[str, Any] = {}
            for ep, samples in self.endpoint_latencies.items():
                if samples:
                    sorted_s = sorted(samples)
                    p50 = round(sorted_s[len(sorted_s) // 2], 2)
                    p95_idx = min(len(sorted_s) - 1, int(len(sorted_s) * 0.95))
                    p95 = round(sorted_s[p95_idx], 2)
                    endpoint_stats[ep] = {
                        "count": len(samples),
                        "p50_ms": p50,
                        "p95_ms": p95,
                        "mean_ms": round(sum(samples) / len(samples), 2),
                    }
            return {
                "uptime_seconds": uptime,
                "total_requests": self.request_count,
                "status_codes": dict(self.status_counts),
                "endpoints": endpoint_stats,
            }


global_metrics_tracker = MetricsTracker()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that injects request_id and logs request duration and status."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        incoming_id = request.headers.get("X-Request-ID")
        req_id = incoming_id if incoming_id else str(uuid.uuid4())
        token = request_id_ctx.set(req_id)
        request.state.request_id = req_id

        start_time = time.perf_counter()
        status_code = 500

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            # Log the unhandled exception internally
            logger.error(
                f"Unhandled exception in request pipeline: {exc}",
                exc_info=True,
                extra={"request_id": req_id},
            )
            # Produce uniform error envelope suppressing stack trace
            error_payload = {
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred. Reference request_id.",
                    "request_id": req_id,
                }
            }
            status_code = 500
            err_response = JSONResponse(status_code=500, content=error_payload)
            err_response.headers["X-Request-ID"] = req_id
            return err_response
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            client_host = request.client.host if request.client else "unknown"

            # Record in global metrics
            global_metrics_tracker.record_request(request.url.path, status_code, duration_ms)

            logger.info(
                f"{request.method} {request.url.path} {status_code} ({duration_ms}ms)",
                extra={
                    "request_id": req_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_host,
                },
            )
            request_id_ctx.reset(token)
