"""Idempotency record model for tracking idempotent operations."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid, utc_now


class IdempotencyRecord(Base):
    """Record for tracking idempotent operations."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("idempotency_key", "tenant_id", "operation", name="uq_idempotency_key_tenant_op"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    response: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    @staticmethod
    def compute_payload_hash(payload: Any) -> str:
        """Compute SHA-256 hash of the payload."""
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @classmethod
    def create(
        cls,
        idempotency_key: str,
        tenant_id: str,
        operation: str,
        payload: Any,
        response: Any,
        ttl_hours: int = 24,
    ) -> "IdempotencyRecord":
        """Create a new idempotency record."""
        now = datetime.now(timezone.utc)
        return cls(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            operation=operation,
            payload_hash=cls.compute_payload_hash(payload),
            response=json.dumps(response, default=str),
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )

    def is_expired(self) -> bool:
        """Check if the record has expired."""
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        # Handle timezone-naive datetimes from SQLite
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires

    def matches_payload(self, payload: Any) -> bool:
        """Check if the given payload matches the stored payload hash."""
        return self.payload_hash == self.compute_payload_hash(payload)

    def get_response(self) -> Any:
        """Get the stored response as a Python object."""
        return json.loads(self.response)
