"""Async Bank Transaction REST API endpoints."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rest.dependencies import ValidatedTenantId
from app.core.database import get_async_db
from app.schemas.bank_transaction import (
    BankTransactionCreate,
    BankTransactionFilters,
    BankTransactionImport,
    BankTransactionImportResult,
    BankTransactionList,
    BankTransactionResponse,
)
from app.services.bank_transaction import BankTransactionService
from app.services.idempotency import IdempotencyService

router = APIRouter(
    prefix="/tenants/{tenant_id}/bank-transactions", tags=["bank-transactions"]
)


@router.post(
    "",
    response_model=BankTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bank transaction",
)
async def create_bank_transaction(
    tenant_id: ValidatedTenantId,
    data: BankTransactionCreate,
    db: AsyncSession = Depends(get_async_db),
) -> BankTransactionResponse:
    """Create a new bank transaction for a tenant."""
    service = BankTransactionService(db)
    transaction = await service.create(tenant_id, data)
    return BankTransactionResponse.model_validate(transaction)


@router.post(
    "/import",
    response_model=BankTransactionImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Import bank transactions in bulk",
)
async def import_bank_transactions(
    tenant_id: ValidatedTenantId,
    data: BankTransactionImport,
    db: AsyncSession = Depends(get_async_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> BankTransactionImportResult:
    """
    Import bank transactions in bulk.

    Supports idempotency via the Idempotency-Key header.
    Duplicate external_ids within the same tenant are skipped.
    """
    # Check idempotency
    if idempotency_key:
        idempotency_service = IdempotencyService(db)
        is_duplicate, cached = await idempotency_service.check_and_get(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            operation="bank_transaction_import",
            payload=data.model_dump(),
        )
        if is_duplicate and cached:
            return BankTransactionImportResult.model_validate(cached)

    service = BankTransactionService(db)
    result = await service.bulk_import(tenant_id, data.transactions)

    # Store idempotent response
    if idempotency_key:
        await idempotency_service.store(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            operation="bank_transaction_import",
            payload=data.model_dump(),
            response=result.model_dump(),
        )

    return result


@router.get(
    "",
    response_model=BankTransactionList,
    summary="List bank transactions",
)
async def list_bank_transactions(
    tenant_id: ValidatedTenantId,
    db: AsyncSession = Depends(get_async_db),
    date_from: date | None = Query(None, description="Filter by date range start"),
    date_to: date | None = Query(None, description="Filter by date range end"),
    amount_min: Decimal | None = Query(None, description="Filter by minimum amount"),
    amount_max: Decimal | None = Query(None, description="Filter by maximum amount"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> BankTransactionList:
    """
    List bank transactions for a tenant with optional filtering.

    Supports filtering by:
    - date_from/date_to: date range
    - amount_min/amount_max: amount range
    """
    filters = BankTransactionFilters(
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
    )

    service = BankTransactionService(db)
    transactions, total = await service.list_by_tenant(
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
async def get_bank_transaction(
    tenant_id: ValidatedTenantId,
    transaction_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> BankTransactionResponse:
    """Get a specific bank transaction by ID."""
    service = BankTransactionService(db)
    transaction = await service.get_by_id(tenant_id, transaction_id)
    return BankTransactionResponse.model_validate(transaction)


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a bank transaction",
)
async def delete_bank_transaction(
    tenant_id: ValidatedTenantId,
    transaction_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Delete a bank transaction. Cannot delete matched transactions."""
    service = BankTransactionService(db)
    await service.delete(tenant_id, transaction_id)
