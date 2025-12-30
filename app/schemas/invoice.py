"""Pydantic schemas for Invoice."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class InvoiceStatusEnum(str, Enum):
    """Invoice status enumeration."""

    OPEN = "open"
    MATCHED = "matched"
    PAID = "paid"


class InvoiceCreate(BaseModel):
    """Schema for creating an invoice."""

    vendor_id: str | None = None
    invoice_number: str | None = Field(None, max_length=100)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="USD", max_length=3)
    invoice_date: date | None = None
    description: str | None = None
    status: InvoiceStatusEnum = InvoiceStatusEnum.OPEN


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice."""

    vendor_id: str | None = None
    invoice_number: str | None = None
    amount: Decimal | None = Field(None, gt=0, decimal_places=2)
    currency: str | None = None
    invoice_date: date | None = None
    description: str | None = None
    status: InvoiceStatusEnum | None = None


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""

    id: str
    tenant_id: str
    vendor_id: str | None
    invoice_number: str | None
    amount: Decimal
    currency: str
    invoice_date: date | None
    description: str | None
    status: InvoiceStatusEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceFilters(BaseModel):
    """Schema for invoice filtering."""

    status: InvoiceStatusEnum | None = None
    vendor_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None


class InvoiceList(BaseModel):
    """Schema for list of invoices."""

    items: list[InvoiceResponse]
    total: int
    page: int = 1
    page_size: int = 50
