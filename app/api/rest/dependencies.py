"""Async REST API dependencies."""

from typing import Annotated

from fastapi import Depends, Header, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.exceptions import NotFoundError
from app.services.tenant import TenantService


async def get_tenant_service(
    db: AsyncSession = Depends(get_async_db),
) -> TenantService:
    """Get tenant service dependency."""
    return TenantService(db)


async def validate_tenant_id(
    tenant_id: Annotated[str, Path(description="Tenant ID")],
    db: AsyncSession = Depends(get_async_db),
) -> str:
    """Validate that the tenant exists and return the tenant_id."""
    service = TenantService(db)
    await service.validate_tenant(tenant_id)
    return tenant_id


# Type alias for validated tenant ID
ValidatedTenantId = Annotated[str, Depends(validate_tenant_id)]


def get_optional_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    """Get optional idempotency key from header."""
    return idempotency_key
