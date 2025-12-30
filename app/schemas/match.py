"""Pydantic schemas for Match."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel

from app.schemas.bank_transaction import BankTransactionResponse
from app.schemas.invoice import InvoiceResponse


class MatchStatusEnum(str, Enum):
    """Match status enumeration."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class MatchCreate(BaseModel):
    """Schema for creating a match."""

    invoice_id: str
    bank_transaction_id: str
    score: Decimal | None = None


class MatchResponse(BaseModel):
    """Schema for match response."""

    id: str
    tenant_id: str
    invoice_id: str
    bank_transaction_id: str
    score: Decimal
    status: MatchStatusEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchDetailResponse(BaseModel):
    """Schema for detailed match response with related entities."""

    id: str
    tenant_id: str
    invoice_id: str
    bank_transaction_id: str
    score: Decimal
    status: MatchStatusEnum
    created_at: datetime
    invoice: InvoiceResponse
    bank_transaction: BankTransactionResponse

    model_config = {"from_attributes": True}


class MatchCandidateResponse(BaseModel):
    """Schema for match candidate response."""

    invoice: InvoiceResponse
    bank_transaction: BankTransactionResponse
    score: Decimal
    match_id: str | None = None


class MatchSuggestion(BaseModel):
    """Schema for a single match suggestion."""

    invoice_id: str
    bank_transaction_id: str
    confidence_score: Decimal
    explanation: str | None = None


class MatchSuggestionList(BaseModel):
    """Schema for list of match suggestions."""

    items: list[MatchSuggestion]
    total: int
    page: int = 1
    page_size: int = 50


class ReconciliationResult(BaseModel):
    """Schema for reconciliation result."""

    matches_created: int
    candidates: list[MatchCandidateResponse]


class MatchFilters(BaseModel):
    """Schema for match filtering."""

    status: MatchStatusEnum | None = None
    invoice_id: str | None = None
    bank_transaction_id: str | None = None
    min_score: Decimal | None = None


class MatchList(BaseModel):
    """Schema for list of matches."""

    items: list[MatchResponse]
    total: int
    page: int = 1
    page_size: int = 50
