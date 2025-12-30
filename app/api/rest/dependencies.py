"""REST API dependencies."""

from typing import Annotated

from fastapi import Depends, Header, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.services.tenant import TenantService


def get_tenant_service(
    db: Session = Depends(get_db),
) -> TenantService:
    """Get tenant service dependency."""
    return TenantService(db)


def validate_tenant_id(
    tenant_id: Annotated[str, Path(description="Tenant ID")],
    db: Session = Depends(get_db),
) -> str:
    """Validate that the tenant exists and return the tenant_id."""
    service = TenantService(db)
    service.validate_tenant(tenant_id)
    return tenant_id


# Type alias for validated tenant ID
ValidatedTenantId = Annotated[str, Depends(validate_tenant_id)]


def get_optional_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    """Get optional idempotency key from header."""
    return idempotency_key
