"""Tenant REST API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.tenant import TenantCreate, TenantList, TenantResponse
from app.services.tenant import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant",
)
def create_tenant(
    data: TenantCreate,
    db: Session = Depends(get_db),
) -> TenantResponse:
    """Create a new tenant/organization."""
    service = TenantService(db)
    tenant = service.create(data)
    db.commit()
    return TenantResponse.model_validate(tenant)


@router.get(
    "",
    response_model=TenantList,
    summary="List all tenants",
)
def list_tenants(
    db: Session = Depends(get_db),
) -> TenantList:
    """List all tenants."""
    service = TenantService(db)
    tenants = service.list_all()
    return TenantList(
        items=[TenantResponse.model_validate(t) for t in tenants],
        total=len(tenants),
    )


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant by ID",
)
def get_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
) -> TenantResponse:
    """Get a tenant by ID."""
    service = TenantService(db)
    tenant = service.get_by_id(tenant_id)
    return TenantResponse.model_validate(tenant)
