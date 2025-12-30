"""Async GraphQL schema with queries and mutations."""

from typing import Optional

import strawberry
from strawberry.types import Info

from app.api.graphql.resolvers import (
    bank_transaction_to_gql,
    invoice_to_gql,
    match_to_detail_gql,
    match_to_gql,
    tenant_to_gql,
    vendor_to_gql,
)
from app.api.graphql.types import (
    BankTransactionConnection,
    BankTransactionFiltersInput,
    BankTransactionImportInput,
    BankTransactionImportResultType,
    BankTransactionType,
    ExplanationType,
    InvoiceConnection,
    InvoiceFiltersInput,
    InvoiceInput,
    InvoiceStatusGQL,
    InvoiceType,
    MatchCandidateType,
    MatchDetailType,
    MatchFiltersInput,
    MatchStatusGQL,
    MatchType,
    PaginationInput,
    ReconcileInput,
    ReconciliationResultType,
    TenantInput,
    TenantType,
    VendorInput,
    VendorType,
)
from app.core.database import get_async_db_session
from app.models.invoice import InvoiceStatus
from app.models.match import MatchStatus
from app.schemas.bank_transaction import BankTransactionCreate, BankTransactionFilters
from app.schemas.invoice import InvoiceCreate, InvoiceFilters, InvoiceStatusEnum
from app.schemas.match import MatchFilters, MatchStatusEnum
from app.schemas.tenant import TenantCreate
from app.schemas.vendor import VendorCreate
from app.services.ai_explanation import AIExplanationService
from app.services.bank_transaction import BankTransactionService
from app.services.idempotency import IdempotencyService
from app.services.invoice import InvoiceService
from app.services.match import MatchService
from app.services.reconciliation import ReconciliationEngine
from app.services.tenant import TenantService
from app.services.vendor import VendorService


@strawberry.type
class Query:
    """GraphQL Query root."""

    @strawberry.field
    async def tenants(self) -> list[TenantType]:
        """List all tenants."""
        async with get_async_db_session() as db:
            service = TenantService(db)
            tenants = await service.list_all()
            return [tenant_to_gql(t) for t in tenants]

    @strawberry.field
    async def tenant(self, tenant_id: str) -> TenantType:
        """Get a tenant by ID."""
        async with get_async_db_session() as db:
            service = TenantService(db)
            tenant = await service.get_by_id(tenant_id)
            return tenant_to_gql(tenant)

    @strawberry.field
    async def invoices(
        self,
        tenant_id: str,
        filters: Optional[InvoiceFiltersInput] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> InvoiceConnection:
        """List invoices for a tenant with optional filtering and pagination."""
        async with get_async_db_session() as db:
            # Validate tenant
            await TenantService(db).validate_tenant(tenant_id)

            # Build filters
            invoice_filters = None
            if filters:
                invoice_filters = InvoiceFilters(
                    status=InvoiceStatusEnum(filters.status.value) if filters.status else None,
                    vendor_id=filters.vendor_id,
                    date_from=filters.date_from,
                    date_to=filters.date_to,
                    amount_min=filters.amount_min,
                    amount_max=filters.amount_max,
                )

            page = pagination.page if pagination else 1
            page_size = pagination.page_size if pagination else 50

            service = InvoiceService(db)
            invoices, total = await service.list_by_tenant(
                tenant_id, filters=invoice_filters, page=page, page_size=page_size
            )

            return InvoiceConnection(
                items=[invoice_to_gql(inv) for inv in invoices],
                total=total,
                page=page,
                page_size=page_size,
            )

    @strawberry.field
    async def invoice(self, tenant_id: str, invoice_id: str) -> InvoiceType:
        """Get an invoice by ID."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)
            service = InvoiceService(db)
            invoice = await service.get_by_id(tenant_id, invoice_id)
            return invoice_to_gql(invoice)

    @strawberry.field
    async def bank_transactions(
        self,
        tenant_id: str,
        filters: Optional[BankTransactionFiltersInput] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> BankTransactionConnection:
        """List bank transactions for a tenant with optional filtering and pagination."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)

            tx_filters = None
            if filters:
                tx_filters = BankTransactionFilters(
                    date_from=filters.date_from,
                    date_to=filters.date_to,
                    amount_min=filters.amount_min,
                    amount_max=filters.amount_max,
                )

            page = pagination.page if pagination else 1
            page_size = pagination.page_size if pagination else 50

            service = BankTransactionService(db)
            transactions, total = await service.list_by_tenant(
                tenant_id, filters=tx_filters, page=page, page_size=page_size
            )

            return BankTransactionConnection(
                items=[bank_transaction_to_gql(tx) for tx in transactions],
                total=total,
                page=page,
                page_size=page_size,
            )

    @strawberry.field
    async def matches(
        self,
        tenant_id: str,
        filters: Optional[MatchFiltersInput] = None,
    ) -> list[MatchDetailType]:
        """List matches for a tenant with optional filtering."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)

            match_filters = None
            if filters:
                match_filters = MatchFilters(
                    status=MatchStatusEnum(filters.status.value) if filters.status else None,
                    invoice_id=filters.invoice_id,
                    bank_transaction_id=filters.bank_transaction_id,
                    min_score=filters.min_score,
                )

            service = MatchService(db)
            matches = await service.list_by_tenant(tenant_id, filters=match_filters)
            return [match_to_detail_gql(m) for m in matches]

    @strawberry.field
    async def match(self, tenant_id: str, match_id: str) -> MatchDetailType:
        """Get a match by ID."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)
            service = MatchService(db)
            match = await service.get_by_id(tenant_id, match_id)
            return match_to_detail_gql(match)

    @strawberry.field
    async def explain_reconciliation(
        self,
        tenant_id: str,
        invoice_id: str,
        transaction_id: str,
    ) -> ExplanationType:
        """Get AI explanation for a match decision."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)
            service = AIExplanationService(db)
            result = await service.explain_match(tenant_id, invoice_id, transaction_id)
            return ExplanationType(
                invoice_id=result.invoice_id,
                transaction_id=result.transaction_id,
                explanation=result.explanation,
                confidence=result.confidence,
                is_fallback=result.is_fallback,
            )


@strawberry.type
class Mutation:
    """GraphQL Mutation root."""

    @strawberry.mutation
    async def create_tenant(self, input: TenantInput) -> TenantType:
        """Create a new tenant."""
        async with get_async_db_session() as db:
            service = TenantService(db)
            tenant = await service.create(TenantCreate(name=input.name))
            await db.commit()
            return tenant_to_gql(tenant)

    @strawberry.mutation
    async def create_vendor(self, tenant_id: str, input: VendorInput) -> VendorType:
        """Create a new vendor."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)
            service = VendorService(db)
            vendor = await service.create(tenant_id, VendorCreate(name=input.name))
            await db.commit()
            return vendor_to_gql(vendor)

    @strawberry.mutation
    async def create_invoice(self, tenant_id: str, input: InvoiceInput) -> InvoiceType:
        """Create a new invoice."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)
            service = InvoiceService(db)
            invoice = await service.create(
                tenant_id,
                InvoiceCreate(
                    vendor_id=input.vendor_id,
                    invoice_number=input.invoice_number,
                    amount=input.amount,
                    currency=input.currency,
                    invoice_date=input.invoice_date,
                    description=input.description,
                    status=InvoiceStatusEnum(input.status.value),
                ),
            )
            await db.commit()
            return invoice_to_gql(invoice)

    @strawberry.mutation
    async def delete_invoice(self, tenant_id: str, invoice_id: str) -> bool:
        """Delete an invoice."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)
            service = InvoiceService(db)
            await service.delete(tenant_id, invoice_id)
            await db.commit()
            return True

    @strawberry.mutation
    async def import_bank_transactions(
        self,
        tenant_id: str,
        input: BankTransactionImportInput,
        idempotency_key: Optional[str] = None,
    ) -> BankTransactionImportResultType:
        """Bulk import bank transactions with optional idempotency."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)

            # Convert input to create schemas
            transactions = [
                BankTransactionCreate(
                    external_id=tx.external_id,
                    posted_at=tx.posted_at,
                    amount=tx.amount,
                    currency=tx.currency,
                    description=tx.description,
                )
                for tx in input.transactions
            ]

            # Serialize for idempotency check
            payload = [tx.model_dump(mode="json") for tx in transactions]

            # Check idempotency if key provided
            if idempotency_key:
                idempotency_service = IdempotencyService(db)
                is_duplicate, cached_response = await idempotency_service.check_and_get(
                    idempotency_key=idempotency_key,
                    tenant_id=tenant_id,
                    operation="bank_transaction_import",
                    payload=payload,
                )

                if is_duplicate and cached_response:
                    return BankTransactionImportResultType(
                        imported=cached_response["imported"],
                        skipped=cached_response["skipped"],
                        transactions=[
                            BankTransactionType(**tx)
                            for tx in cached_response["transactions"]
                        ],
                    )

            # Perform import
            service = BankTransactionService(db)
            result = await service.bulk_import(tenant_id, transactions)

            # Store for idempotency
            if idempotency_key:
                idempotency_service = IdempotencyService(db)
                await idempotency_service.store(
                    idempotency_key=idempotency_key,
                    tenant_id=tenant_id,
                    operation="bank_transaction_import",
                    payload=payload,
                    response=result.model_dump(mode="json"),
                )

            await db.commit()

            return BankTransactionImportResultType(
                imported=result.imported,
                skipped=result.skipped,
                transactions=[
                    bank_transaction_to_gql_from_dict(tx)
                    for tx in result.transactions
                ],
            )

    @strawberry.mutation
    async def reconcile(
        self,
        tenant_id: str,
        input: Optional[ReconcileInput] = None,
    ) -> ReconciliationResultType:
        """Run reconciliation to match invoices with bank transactions."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)

            min_score = input.min_score if input else 0.5

            engine = ReconciliationEngine(db)
            matches_created, candidates = await engine.run_reconciliation(
                tenant_id=tenant_id,
                min_score=min_score,
                create_matches=True,
            )
            await db.commit()

            candidate_types = []
            for candidate in candidates:
                match_id = None
                for match in matches_created:
                    if (
                        match.invoice_id == candidate.invoice.id
                        and match.bank_transaction_id == candidate.transaction.id
                    ):
                        match_id = match.id
                        break

                candidate_types.append(
                    MatchCandidateType(
                        invoice=invoice_to_gql(candidate.invoice),
                        bank_transaction=bank_transaction_to_gql(candidate.transaction),
                        score=candidate.score,
                        match_id=match_id,
                    )
                )

            return ReconciliationResultType(
                matches_created=len(matches_created),
                candidates=candidate_types,
            )

    @strawberry.mutation
    async def confirm_match(self, tenant_id: str, match_id: str) -> MatchType:
        """Confirm a proposed match."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)
            service = MatchService(db)
            match = await service.confirm(tenant_id, match_id)
            await db.commit()
            return match_to_gql(match)

    @strawberry.mutation
    async def reject_match(self, tenant_id: str, match_id: str) -> MatchType:
        """Reject a proposed match."""
        async with get_async_db_session() as db:
            await TenantService(db).validate_tenant(tenant_id)
            service = MatchService(db)
            match = await service.reject(tenant_id, match_id)
            await db.commit()
            return match_to_gql(match)


def bank_transaction_to_gql_from_dict(data: dict) -> BankTransactionType:
    """Convert dict to BankTransactionType for cached responses."""
    from datetime import datetime as dt

    posted_at = data["posted_at"]
    if isinstance(posted_at, str):
        posted_at = dt.fromisoformat(posted_at.replace("Z", "+00:00"))

    created_at = data["created_at"]
    if isinstance(created_at, str):
        created_at = dt.fromisoformat(created_at.replace("Z", "+00:00"))

    return BankTransactionType(
        id=data["id"],
        tenant_id=data["tenant_id"],
        external_id=data.get("external_id"),
        posted_at=posted_at,
        amount=data["amount"],
        currency=data["currency"],
        description=data.get("description"),
        created_at=created_at,
    )


# Create the schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
