"""Async Tenant REST API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.schemas.tenant import TenantCreate, TenantList, TenantResponse
from app.services.tenant import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant",
)
async def create_tenant(
    data: TenantCreate,
    db: AsyncSession = Depends(get_async_db),
) -> TenantResponse:
    """Create a new tenant/organization."""
    service = TenantService(db)
    tenant = await service.create(data)
    return TenantResponse.model_validate(tenant)


@router.get(
    "",
    response_model=TenantList,
    summary="List all tenants",
)
async def list_tenants(
    db: AsyncSession = Depends(get_async_db),
) -> TenantList:
    """List all tenants."""
    service = TenantService(db)
    tenants = await service.list_all()
    return TenantList(
        items=[TenantResponse.model_validate(t) for t in tenants],
        total=len(tenants),
    )


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant by ID",
)
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> TenantResponse:
    """Get a tenant by ID."""
    service = TenantService(db)
    tenant = await service.get_by_id(tenant_id)
    return TenantResponse.model_validate(tenant)
