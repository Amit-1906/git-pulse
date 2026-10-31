from typing import Any, Optional, Dict
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class GitPulseException(Exception):
    """Base exception for all GitPulse application errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class EntityNotFoundException(GitPulseException):
    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found.",
            code="ENTITY_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"entity": entity_name, "identifier": str(identifier)},
        )


class EntityAlreadyExistsException(GitPulseException):
    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' already exists.",
            code="ENTITY_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
            details={"entity": entity_name, "identifier": str(identifier)},
        )


class GitHubAPIException(GitPulseException):
    def __init__(self, message: str, status_code: int = 502, details: Optional[Any] = None):
        super().__init__(
            message=f"GitHub API Error: {message}",
            code="GITHUB_API_ERROR",
            status_code=status_code,
            details=details,
        )


class GitHubRateLimitExceededException(GitHubAPIException):
    def __init__(self, reset_timestamp: Optional[int] = None):
        super().__init__(
            message="GitHub API rate limit exceeded. Please configure GITHUB_ACCESS_TOKEN or wait for window reset.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"rate_limit_reset": reset_timestamp},
        )
        self.code = "RATE_LIMIT_EXCEEDED"


class PipelineExecutionException(GitPulseException):
    def __init__(self, pipeline_name: str, message: str, details: Optional[Any] = None):
        super().__init__(
            message=f"Pipeline '{pipeline_name}' failed: {message}",
            code="PIPELINE_EXECUTION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class DatabaseException(GitPulseException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=f"Database operational error: {message}",
            code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


def build_error_payload(
    code: str,
    message: str,
    details: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        },
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Registers centralized exception handlers on the FastAPI application."""

    @app.exception_handler(GitPulseException)
    async def gitpulse_exception_handler(request: Request, exc: GitPulseException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = build_error_payload(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = build_error_payload(
            code="VALIDATION_ERROR",
            message="Request body or query parameters validation failed.",
            details=exc.errors(),
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        code = "HTTP_ERROR"
        if exc.status_code == 404:
            code = "NOT_FOUND"
        elif exc.status_code == 403:
            code = "FORBIDDEN"
        elif exc.status_code == 401:
            code = "UNAUTHORIZED"

        payload = build_error_payload(
            code=code,
            message=str(exc.detail),
            request_id=request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = build_error_payload(
            code="UNHANDLED_EXCEPTION",
            message="An unexpected server error occurred.",
            details=str(exc) if getattr(request.app.state, "debug", False) else None,
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)

