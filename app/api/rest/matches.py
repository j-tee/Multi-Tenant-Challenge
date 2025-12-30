"""Async Match REST API endpoints - shorthand routes."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rest.dependencies import ValidatedTenantId
from app.core.database import get_async_db
from app.schemas.match import (
    MatchCreate,
    MatchList,
    MatchResponse,
)
from app.services.match import MatchService
from app.models.match import Match, MatchStatus

router = APIRouter(prefix="/tenants/{tenant_id}/matches", tags=["matches"])


@router.post(
    "",
    response_model=MatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a match",
)
async def create_match(
    tenant_id: ValidatedTenantId,
    data: MatchCreate,
    db: AsyncSession = Depends(get_async_db),
) -> MatchResponse:
    """Create a match between an invoice and bank transaction."""
    match = Match(
        tenant_id=tenant_id,
        invoice_id=data.invoice_id,
        bank_transaction_id=data.bank_transaction_id,
        score=data.score if data.score else Decimal("1.0"),
        status=MatchStatus.PROPOSED,
    )
    db.add(match)
    await db.flush()
    return MatchResponse.model_validate(match)


@router.get(
    "",
    response_model=MatchList,
    summary="List matches",
)
async def list_matches(
    tenant_id: ValidatedTenantId,
    db: AsyncSession = Depends(get_async_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> MatchList:
    """List all matches for a tenant."""
    service = MatchService(db)
    matches = await service.list_by_tenant(tenant_id)

    total = len(matches)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = matches[start:end]

    return MatchList(
        items=[MatchResponse.model_validate(m) for m in paginated],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{match_id}",
    response_model=MatchResponse,
    summary="Get match by ID",
)
async def get_match(
    tenant_id: ValidatedTenantId,
    match_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> MatchResponse:
    """Get a specific match by ID."""
    service = MatchService(db)
    match = await service.get_by_id(tenant_id, match_id)
    return MatchResponse.model_validate(match)


@router.post(
    "/{match_id}/confirm",
    response_model=MatchResponse,
    summary="Confirm a match",
)
async def confirm_match(
    tenant_id: ValidatedTenantId,
    match_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> MatchResponse:
    """Confirm a proposed match."""
    service = MatchService(db)
    match = await service.confirm(tenant_id, match_id)
    return MatchResponse.model_validate(match)


@router.post(
    "/{match_id}/reject",
    response_model=MatchResponse,
    summary="Reject a match",
)
async def reject_match(
    tenant_id: ValidatedTenantId,
    match_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> MatchResponse:
    """Reject a proposed match."""
    service = MatchService(db)
    match = await service.reject(tenant_id, match_id)
    return MatchResponse.model_validate(match)


@router.delete(
    "/{match_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a match",
)
async def delete_match(
    tenant_id: ValidatedTenantId,
    match_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Delete a match."""
    service = MatchService(db)
    match = await service.get_by_id(tenant_id, match_id)
    await db.delete(match)
    await db.flush()
