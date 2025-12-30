"""Async Vendor REST API endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rest.dependencies import ValidatedTenantId
from app.core.database import get_async_db
from app.schemas.vendor import VendorCreate, VendorList, VendorResponse
from app.services.vendor import VendorService

router = APIRouter(prefix="/tenants/{tenant_id}/vendors", tags=["vendors"])


@router.post(
    "",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new vendor",
)
async def create_vendor(
    tenant_id: ValidatedTenantId,
    data: VendorCreate,
    db: AsyncSession = Depends(get_async_db),
) -> VendorResponse:
    """Create a new vendor for a tenant."""
    service = VendorService(db)
    vendor = await service.create(tenant_id, data)
    return VendorResponse.model_validate(vendor)


@router.get(
    "",
    response_model=VendorList,
    summary="List vendors",
)
async def list_vendors(
    tenant_id: ValidatedTenantId,
    db: AsyncSession = Depends(get_async_db),
) -> VendorList:
    """List all vendors for a tenant."""
    service = VendorService(db)
    vendors = await service.list_by_tenant(tenant_id)
    return VendorList(
        items=[VendorResponse.model_validate(v) for v in vendors],
        total=len(vendors),
    )


@router.get(
    "/{vendor_id}",
    response_model=VendorResponse,
    summary="Get vendor by ID",
)
async def get_vendor(
    tenant_id: ValidatedTenantId,
    vendor_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> VendorResponse:
    """Get a specific vendor by ID."""
    service = VendorService(db)
    vendor = await service.get_by_id(tenant_id, vendor_id)
    return VendorResponse.model_validate(vendor)
