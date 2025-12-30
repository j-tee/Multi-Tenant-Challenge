"""GraphQL types using Strawberry."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

import strawberry


@strawberry.enum
class InvoiceStatusGQL(Enum):
    """Invoice status enumeration for GraphQL."""

    OPEN = "open"
    MATCHED = "matched"
    PAID = "paid"


@strawberry.enum
class MatchStatusGQL(Enum):
    """Match status enumeration for GraphQL."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@strawberry.type
class TenantType:
    """GraphQL type for Tenant."""

    id: str
    name: str
    created_at: datetime


@strawberry.type
class VendorType:
    """GraphQL type for Vendor."""

    id: str
    tenant_id: str
    name: str
    created_at: datetime


@strawberry.type
class InvoiceType:
    """GraphQL type for Invoice."""

    id: str
    tenant_id: str
    vendor_id: Optional[str]
    invoice_number: Optional[str]
    amount: Decimal
    currency: str
    invoice_date: Optional[date]
    description: Optional[str]
    status: InvoiceStatusGQL
    created_at: datetime


@strawberry.type
class BankTransactionType:
    """GraphQL type for BankTransaction."""

    id: str
    tenant_id: str
    external_id: Optional[str]
    posted_at: datetime
    amount: Decimal
    currency: str
    description: Optional[str]
    created_at: datetime


@strawberry.type
class MatchType:
    """GraphQL type for Match."""

    id: str
    tenant_id: str
    invoice_id: str
    bank_transaction_id: str
    score: Decimal
    status: MatchStatusGQL
    created_at: datetime


@strawberry.type
class MatchDetailType:
    """GraphQL type for Match with related entities."""

    id: str
    tenant_id: str
    invoice_id: str
    bank_transaction_id: str
    score: Decimal
    status: MatchStatusGQL
    created_at: datetime
    invoice: InvoiceType
    bank_transaction: BankTransactionType


@strawberry.type
class MatchCandidateType:
    """GraphQL type for match candidates."""

    invoice: InvoiceType
    bank_transaction: BankTransactionType
    score: Decimal
    match_id: Optional[str]


@strawberry.type
class ReconciliationResultType:
    """GraphQL type for reconciliation results."""

    matches_created: int
    candidates: list[MatchCandidateType]


@strawberry.type
class ExplanationType:
    """GraphQL type for AI explanation."""

    invoice_id: str
    transaction_id: str
    explanation: str
    confidence: Optional[str]
    is_fallback: bool


@strawberry.type
class BankTransactionImportResultType:
    """GraphQL type for bank transaction import results."""

    imported: int
    skipped: int
    transactions: list[BankTransactionType]


# Input types


@strawberry.input
class TenantInput:
    """Input for creating a tenant."""

    name: str


@strawberry.input
class VendorInput:
    """Input for creating a vendor."""

    name: str


@strawberry.input
class InvoiceInput:
    """Input for creating an invoice."""

    vendor_id: Optional[str] = None
    invoice_number: Optional[str] = None
    amount: Decimal
    currency: str = "USD"
    invoice_date: Optional[date] = None
    description: Optional[str] = None
    status: InvoiceStatusGQL = InvoiceStatusGQL.OPEN


@strawberry.input
class BankTransactionInput:
    """Input for a single bank transaction."""

    external_id: Optional[str] = None
    posted_at: datetime
    amount: Decimal
    currency: str = "USD"
    description: Optional[str] = None


@strawberry.input
class BankTransactionImportInput:
    """Input for bulk importing bank transactions."""

    transactions: list[BankTransactionInput]


@strawberry.input
class InvoiceFiltersInput:
    """Input for invoice filtering."""

    status: Optional[InvoiceStatusGQL] = None
    vendor_id: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None


@strawberry.input
class BankTransactionFiltersInput:
    """Input for bank transaction filtering."""

    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None


@strawberry.input
class MatchFiltersInput:
    """Input for match filtering."""

    status: Optional[MatchStatusGQL] = None
    invoice_id: Optional[str] = None
    bank_transaction_id: Optional[str] = None
    min_score: Optional[Decimal] = None


@strawberry.input
class ReconcileInput:
    """Input for reconciliation."""

    min_score: float = 0.5


@strawberry.input
class PaginationInput:
    """Input for pagination."""

    page: int = 1
    page_size: int = 50


# Paginated types


@strawberry.type
class InvoiceConnection:
    """Paginated list of invoices."""

    items: list[InvoiceType]
    total: int
    page: int
    page_size: int


@strawberry.type
class BankTransactionConnection:
    """Paginated list of bank transactions."""

    items: list[BankTransactionType]
    total: int
    page: int
    page_size: int
