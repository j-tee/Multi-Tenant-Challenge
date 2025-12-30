"""GraphQL resolvers - shared utilities."""

from typing import Any

from app.models.invoice import Invoice, InvoiceStatus
from app.models.bank_transaction import BankTransaction
from app.models.match import Match, MatchStatus
from app.models.tenant import Tenant
from app.models.vendor import Vendor
from app.api.graphql.types import (
    BankTransactionType,
    InvoiceStatusGQL,
    InvoiceType,
    MatchDetailType,
    MatchStatusGQL,
    MatchType,
    TenantType,
    VendorType,
)


def tenant_to_gql(tenant: Tenant) -> TenantType:
    """Convert Tenant model to GraphQL type."""
    return TenantType(
        id=tenant.id,
        name=tenant.name,
        created_at=tenant.created_at,
    )


def vendor_to_gql(vendor: Vendor) -> VendorType:
    """Convert Vendor model to GraphQL type."""
    return VendorType(
        id=vendor.id,
        tenant_id=vendor.tenant_id,
        name=vendor.name,
        created_at=vendor.created_at,
    )


def invoice_to_gql(invoice: Invoice) -> InvoiceType:
    """Convert Invoice model to GraphQL type."""
    return InvoiceType(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        vendor_id=invoice.vendor_id,
        invoice_number=invoice.invoice_number,
        amount=invoice.amount,
        currency=invoice.currency,
        invoice_date=invoice.invoice_date,
        description=invoice.description,
        status=InvoiceStatusGQL(invoice.status.value),
        created_at=invoice.created_at,
    )


def bank_transaction_to_gql(tx: BankTransaction) -> BankTransactionType:
    """Convert BankTransaction model to GraphQL type."""
    return BankTransactionType(
        id=tx.id,
        tenant_id=tx.tenant_id,
        external_id=tx.external_id,
        posted_at=tx.posted_at,
        amount=tx.amount,
        currency=tx.currency,
        description=tx.description,
        created_at=tx.created_at,
    )


def match_to_gql(match: Match) -> MatchType:
    """Convert Match model to GraphQL type."""
    return MatchType(
        id=match.id,
        tenant_id=match.tenant_id,
        invoice_id=match.invoice_id,
        bank_transaction_id=match.bank_transaction_id,
        score=match.score,
        status=MatchStatusGQL(match.status.value),
        created_at=match.created_at,
    )


def match_to_detail_gql(match: Match) -> MatchDetailType:
    """Convert Match model to GraphQL detail type with related entities."""
    return MatchDetailType(
        id=match.id,
        tenant_id=match.tenant_id,
        invoice_id=match.invoice_id,
        bank_transaction_id=match.bank_transaction_id,
        score=match.score,
        status=MatchStatusGQL(match.status.value),
        created_at=match.created_at,
        invoice=invoice_to_gql(match.invoice),
        bank_transaction=bank_transaction_to_gql(match.bank_transaction),
    )
