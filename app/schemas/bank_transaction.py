"""Pydantic schemas for Bank Transaction."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BankTransactionCreate(BaseModel):
    """Schema for creating a bank transaction."""

    external_id: str | None = Field(None, max_length=255)
    posted_at: datetime
    amount: Decimal = Field(..., decimal_places=2)
    currency: str = Field(default="USD", max_length=3)
    description: str | None = None


class BankTransactionImport(BaseModel):
    """Schema for bulk importing bank transactions."""

    transactions: list[BankTransactionCreate]


class BankTransactionResponse(BaseModel):
    """Schema for bank transaction response."""

    id: str
    tenant_id: str
    external_id: str | None
    posted_at: datetime
    amount: Decimal
    currency: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BankTransactionFilters(BaseModel):
    """Schema for bank transaction filtering."""

    date_from: datetime | None = None
    date_to: datetime | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None


class BankTransactionList(BaseModel):
    """Schema for list of bank transactions."""

    items: list[BankTransactionResponse]
    total: int
    page: int = 1
    page_size: int = 50


class BankTransactionImportResult(BaseModel):
    """Schema for bank transaction import result."""

    imported: int
    skipped: int
    transactions: list[BankTransactionResponse]
