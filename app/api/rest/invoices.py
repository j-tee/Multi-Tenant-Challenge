"""Async Invoice REST API endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rest.dependencies import ValidatedTenantId
from app.core.database import get_async_db
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceFilters,
    InvoiceList,
    InvoiceResponse,
    InvoiceStatusEnum,
)
from app.services.invoice import InvoiceService

router = APIRouter(prefix="/tenants/{tenant_id}/invoices", tags=["invoices"])


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new invoice",
)
async def create_invoice(
    tenant_id: ValidatedTenantId,
    data: InvoiceCreate,
    db: AsyncSession = Depends(get_async_db),
) -> InvoiceResponse:
    """Create a new invoice for a tenant."""
    service = InvoiceService(db)
    invoice = await service.create(tenant_id, data)
    return InvoiceResponse.model_validate(invoice)


@router.get(
    "",
    response_model=InvoiceList,
    summary="List invoices",
)
async def list_invoices(
    tenant_id: ValidatedTenantId,
    db: AsyncSession = Depends(get_async_db),
    status: InvoiceStatusEnum | None = Query(None, description="Filter by status"),
    vendor_id: str | None = Query(None, description="Filter by vendor ID"),
    date_from: date | None = Query(None, description="Filter by date range start"),
    date_to: date | None = Query(None, description="Filter by date range end"),
    amount_min: Decimal | None = Query(None, description="Filter by minimum amount"),
    amount_max: Decimal | None = Query(None, description="Filter by maximum amount"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> InvoiceList:
    """
    List invoices for a tenant with optional filtering.

    Supports filtering by:
    - status: open, matched, paid
    - vendor_id: specific vendor
    - date_from/date_to: date range
    - amount_min/amount_max: amount range
    """
    filters = InvoiceFilters(
        status=status,
        vendor_id=vendor_id,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
    )

    service = InvoiceService(db)
    invoices, total = await service.list_by_tenant(
        tenant_id, filters=filters, page=page, page_size=page_size
    )

    return InvoiceList(
        items=[InvoiceResponse.model_validate(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice by ID",
)
async def get_invoice(
    tenant_id: ValidatedTenantId,
    invoice_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> InvoiceResponse:
    """Get a specific invoice by ID."""
    service = InvoiceService(db)
    invoice = await service.get_by_id(tenant_id, invoice_id)
    return InvoiceResponse.model_validate(invoice)


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an invoice",
)
async def delete_invoice(
    tenant_id: ValidatedTenantId,
    invoice_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Delete an invoice. Cannot delete matched invoices."""
    service = InvoiceService(db)
    await service.delete(tenant_id, invoice_id)
