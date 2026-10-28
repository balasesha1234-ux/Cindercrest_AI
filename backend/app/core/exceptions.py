"""Centralized exception handling and standardized error responses."""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.logging import logger


class ErrorDetail(BaseModel):
    """Detailed error object returned to API clients."""

    code: str
    message: str
    details: Any | None = None


class StandardErrorResponse(BaseModel):
    """Predictable root envelope for all client-facing errors."""

    error: ErrorDetail


class AppError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


# Backward compatibility alias
AppException = AppError


class UnauthorizedError(AppError):
    """Raised when authentication fails or is missing."""

    def __init__(
        self,
        message: str = "Authentication required or invalid session token",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenError(AppError):
    """Raised when an operation violates security policy."""

    def __init__(
        self, message: str = "Access denied by security policy", details: Any | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found", details: Any | None = None) -> None:
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationError(AppError):
    """Raised when input parameters fail domain validation."""

    def __init__(
        self, message: str = "Input validation failed", details: Any | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


async def app_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle custom domain exceptions."""
    app_exc = exc if isinstance(exc, AppError) else AppError(str(exc))
    logger.warning(
        "Domain exception: [%s] %s (path: %s)", app_exc.code, app_exc.message, request.url.path
    )
    payload = StandardErrorResponse(
        error=ErrorDetail(code=app_exc.code, message=app_exc.message, details=app_exc.details)
    )
    return JSONResponse(status_code=app_exc.status_code, content=payload.model_dump())


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle FastAPI / Pydantic request validation errors."""
    val_exc = exc if isinstance(exc, RequestValidationError) else None
    details = val_exc.errors() if val_exc else str(exc)
    logger.warning("Validation error on %s: %s", request.url.path, details)
    payload = StandardErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Request body or query parameters failed schema validation",
            details=details,
        )
    )
    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content=payload.model_dump(),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle standard Starlette / FastAPI HTTP exceptions."""
    http_exc = exc if isinstance(exc, StarletteHTTPException) else None
    status_code = http_exc.status_code if http_exc else status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = http_exc.detail if http_exc else str(exc)
    logger.warning("HTTP exception %d on %s: %s", status_code, request.url.path, detail)
    code = "NOT_FOUND" if status_code == 404 else f"HTTP_{status_code}"
    payload = StandardErrorResponse(error=ErrorDetail(code=code, message=str(detail), details=None))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unhandled exception handler to avoid stack leaks in production."""
    logger.exception("Unhandled server exception on %s: %s", request.url.path, str(exc))
    payload = StandardErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred. Check local backend logs.",
            details=None,
        )
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump()
    )
