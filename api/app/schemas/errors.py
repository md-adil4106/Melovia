"""Error response schemas adhering to uniform API envelope."""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable explanation of the error")
    request_id: str = Field(..., description="Unique correlation ID for tracing the request")


class ErrorResponse(BaseModel):
    error: ErrorDetail = Field(..., description="Standardized error body")
