"""Custom exceptions for the application."""

from typing import Any


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found exception."""

    def __init__(self, resource: str, identifier: Any) -> None:
        super().__init__(
            f"{resource} not found",
            {"resource": resource, "identifier": str(identifier)},
        )


class ConflictError(AppException):
    """Conflict exception (e.g., idempotency key reuse with different payload)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)


class ValidationError(AppException):
    """Validation exception."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)


class TenantIsolationError(AppException):
    """Tenant isolation violation exception."""

    def __init__(self, message: str = "Tenant isolation violation") -> None:
        super().__init__(message)


class AIServiceError(AppException):
    """AI service exception."""

    def __init__(self, message: str = "AI service unavailable") -> None:
        super().__init__(message)
