"""Async Idempotency service."""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.idempotency import IdempotencyRecord


class IdempotencyService:
    """Async service for managing idempotent operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_and_get(
        self,
        idempotency_key: str,
        tenant_id: str,
        operation: str,
        payload: Any,
    ) -> tuple[bool, Any | None]:
        """
        Check if an idempotent operation has already been performed.

        Returns:
            Tuple of (is_duplicate, cached_response).
            - If is_duplicate is True, cached_response contains the previous result.
            - If is_duplicate is False, cached_response is None.

        Raises:
            ConflictError: If the same key was used with a different payload.
        """
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == idempotency_key,
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.operation == operation,
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return False, None

        # Check if expired
        if record.is_expired():
            await self.db.delete(record)
            await self.db.flush()
            return False, None

        # Check if payload matches
        if not record.matches_payload(payload):
            raise ConflictError(
                "Idempotency key reused with different payload",
                {
                    "idempotency_key": idempotency_key,
                    "operation": operation,
                },
            )

        return True, record.get_response()

    async def store(
        self,
        idempotency_key: str,
        tenant_id: str,
        operation: str,
        payload: Any,
        response: Any,
        ttl_hours: int = 24,
    ) -> IdempotencyRecord:
        """Store the result of an idempotent operation."""
        record = IdempotencyRecord.create(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            operation=operation,
            payload=payload,
            response=response,
            ttl_hours=ttl_hours,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def cleanup_expired(self) -> int:
        """Remove expired idempotency records."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.expires_at < now
        )
        result = await self.db.execute(stmt)
        expired = list(result.scalars().all())
        for record in expired:
            await self.db.delete(record)
        await self.db.flush()
        return len(expired)
