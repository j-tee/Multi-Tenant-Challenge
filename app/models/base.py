"""Base model and common utilities for SQLAlchemy models."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    type_annotation_map = {
        str: String(255),
    }


class TimestampMixin:
    """Mixin for created_at timestamp."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class TenantScopedMixin:
    """Mixin for tenant-scoped models."""

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    def validate_tenant(self, tenant_id: str) -> bool:
        """Validate that the record belongs to the given tenant."""
        return self.tenant_id == tenant_id


def to_dict(model: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy model to a dictionary."""
    return {
        column.name: getattr(model, column.name)
        for column in model.__table__.columns
    }
