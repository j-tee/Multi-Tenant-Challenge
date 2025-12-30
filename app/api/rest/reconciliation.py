"""Async Reconciliation REST API endpoints."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rest.dependencies import ValidatedTenantId
from app.core.database import get_async_db
from app.schemas.match import (
    MatchCandidateResponse,
    MatchCreate,
    MatchList,
    MatchResponse,
    ReconciliationResult,
)
from app.schemas.invoice import InvoiceResponse
from app.schemas.bank_transaction import BankTransactionResponse
from app.services.ai_explanation import AIExplanationService
from app.services.match import MatchService
from app.services.reconciliation import ReconciliationEngine
from app.models.match import Match, MatchStatus

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["reconciliation"])


@router.post(
    "/reconcile",
    response_model=ReconciliationResult,
    status_code=status.HTTP_200_OK,
    summary="Run reconciliation",
)
async def run_reconciliation(
    tenant_id: ValidatedTenantId,
    db: AsyncSession = Depends(get_async_db),
    min_score: float = Query(0.5, ge=0.0, le=1.0, description="Minimum match score"),
    create_matches: bool = Query(True, description="Create match records for candidates"),
) -> ReconciliationResult:
    """
    Run the reconciliation process for a tenant.

    This will:
    1. Analyze all unmatched invoices and bank transactions
    2. Apply deterministic matching heuristics
    3. Create proposed match records (if create_matches=True)
    4. Return all viable match candidates
    """
    engine = ReconciliationEngine(db)
    matches, candidates = await engine.run_reconciliation(
        tenant_id, min_score=min_score, create_matches=create_matches
    )

    # Build a lookup of invoice+transaction -> match_id
    match_lookup = {}
    for m in matches:
        match_lookup[(m.invoice_id, m.bank_transaction_id)] = str(m.id)

    # Convert candidates to response format
    candidate_responses = []
    for c in candidates:
        # Find match_id if a match was created for this candidate
        key = (c.invoice.id, c.transaction.id)
        match_id = match_lookup.get(key)
        
        candidate_responses.append(
            MatchCandidateResponse(
                invoice=InvoiceResponse.model_validate(c.invoice),
                bank_transaction=BankTransactionResponse.model_validate(c.transaction),
                score=c.score,
                match_id=match_id,
            )
        )

    return ReconciliationResult(
        matches_created=len(matches),
        candidates=candidate_responses,
    )


@router.get(
    "/reconcile/explain",
    summary="Get AI explanation for a potential match",
)
async def explain_potential_match(
    tenant_id: ValidatedTenantId,
    invoice_id: str = Query(..., description="Invoice ID"),
    transaction_id: str = Query(..., description="Bank transaction ID"),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    Generate an AI explanation for a potential match between invoice and transaction.

    Returns a detailed explanation including:
    - Matching criteria that were satisfied
    - Confidence breakdown
    - Any discrepancies or flags
    """
    ai_service = AIExplanationService(db)
    explanation_data = await ai_service.explain_match(tenant_id, invoice_id, transaction_id)
    return explanation_data.model_dump()


@router.post(
    "/reconciliation/matches",
    response_model=MatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a match",
)
async def create_match(
    tenant_id: ValidatedTenantId,
    data: MatchCreate,
    db: AsyncSession = Depends(get_async_db),
) -> MatchResponse:
    """
    Create a match between an invoice and bank transaction.

    This creates a manual match with PROPOSED status.
    """
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
    "/reconciliation/matches",
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

    # Simple pagination
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
    "/reconciliation/matches/{match_id}",
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
    "/reconciliation/matches/{match_id}/confirm",
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
    "/reconciliation/matches/{match_id}/reject",
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
    "/reconciliation/matches/{match_id}",
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


@router.post(
    "/reconciliation/matches/{match_id}/explain",
    response_model=dict,
    summary="Get AI explanation for a confirmed match",
)
async def explain_match(
    tenant_id: ValidatedTenantId,
    match_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    Generate an AI explanation for why a specific match was suggested.

    Returns a detailed explanation including:
    - Matching criteria that were satisfied
    - Confidence breakdown
    - Any discrepancies or flags
    """
    ai_service = AIExplanationService(db)
    explanation = await ai_service.explain_match(tenant_id, match_id)
    return {"match_id": match_id, "explanation": explanation}
