"""Exception handlers for FastAPI."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppException,
    ConflictError,
    NotFoundError,
    TenantIsolationError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers with the FastAPI app."""

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "not_found",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "conflict",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "validation_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(TenantIsolationError)
    async def tenant_isolation_handler(
        request: Request, exc: TenantIsolationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "tenant_isolation_violation",
                "message": exc.message,
            },
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": exc.message,
                "details": exc.details,
            },
        )
