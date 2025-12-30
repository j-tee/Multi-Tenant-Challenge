"""Bank Transaction REST API endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.api.rest.dependencies import ValidatedTenantId
from app.core.database import get_db
from app.core.exceptions import ConflictError
from app.schemas.bank_transaction import (
    BankTransactionFilters,
    BankTransactionImport,
    BankTransactionImportResult,
    BankTransactionList,
    BankTransactionResponse,
)
from app.services.bank_transaction import BankTransactionService
from app.services.idempotency import IdempotencyService

router = APIRouter(prefix="/tenants/{tenant_id}/bank-transactions", tags=["bank-transactions"])

IMPORT_OPERATION = "bank_transaction_import"


@router.post(
    "/import",
    response_model=BankTransactionImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk import bank transactions",
    responses={
        409: {"description": "Conflict - Idempotency key reused with different payload"},
    },
)
def import_bank_transactions(
    tenant_id: ValidatedTenantId,
    data: BankTransactionImport,
    db: Session = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> BankTransactionImportResult:
    """
    Bulk import bank transactions.

    **Idempotency:**
    - Provide an `Idempotency-Key` header for idempotent imports
    - Same key + same payload = returns cached result
    - Same key + different payload = returns 409 Conflict

    Transactions with duplicate `external_id` values are skipped.
    """
    # Convert to serializable format for idempotency check
    payload = [tx.model_dump(mode="json") for tx in data.transactions]

    # Check idempotency if key provided
    if idempotency_key:
        idempotency_service = IdempotencyService(db)

        is_duplicate, cached_response = idempotency_service.check_and_get(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            operation=IMPORT_OPERATION,
            payload=payload,
        )

        if is_duplicate:
            # Return cached response
            return BankTransactionImportResult(**cached_response)

    # Perform the import
    service = BankTransactionService(db)
    result = service.bulk_import(tenant_id, data.transactions)

    # Store result for idempotency if key provided
    if idempotency_key:
        idempotency_service = IdempotencyService(db)
        idempotency_service.store(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            operation=IMPORT_OPERATION,
            payload=payload,
            response=result.model_dump(mode="json"),
        )

    db.commit()
    return result


@router.get(
    "",
    response_model=BankTransactionList,
    summary="List bank transactions",
)
def list_bank_transactions(
    tenant_id: ValidatedTenantId,
    db: Session = Depends(get_db),
    date_from: datetime | None = Query(None, description="Filter by date range start"),
    date_to: datetime | None = Query(None, description="Filter by date range end"),
    amount_min: Decimal | None = Query(None, description="Filter by minimum amount"),
    amount_max: Decimal | None = Query(None, description="Filter by maximum amount"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> BankTransactionList:
    """List bank transactions for a tenant with optional filtering."""
    filters = BankTransactionFilters(
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
    )

    service = BankTransactionService(db)
    transactions, total = service.list_by_tenant(
        tenant_id, filters=filters, page=page, page_size=page_size
    )

    return BankTransactionList(
        items=[BankTransactionResponse.model_validate(tx) for tx in transactions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{transaction_id}",
    response_model=BankTransactionResponse,
    summary="Get bank transaction by ID",
)
def get_bank_transaction(
    tenant_id: ValidatedTenantId,
    transaction_id: str,
    db: Session = Depends(get_db),
) -> BankTransactionResponse:
    """Get a specific bank transaction by ID."""
    service = BankTransactionService(db)
    transaction = service.get_by_id(tenant_id, transaction_id)
    return BankTransactionResponse.model_validate(transaction)
