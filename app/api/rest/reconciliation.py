"""Reconciliation REST API endpoints."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.rest.dependencies import ValidatedTenantId
from app.core.database import get_db
from app.schemas.bank_transaction import BankTransactionResponse
from app.schemas.explanation import ExplanationResponse
from app.schemas.invoice import InvoiceResponse
from app.schemas.match import (
    MatchCandidateResponse,
    MatchDetailResponse,
    MatchFilters,
    MatchList,
    MatchResponse,
    MatchStatusEnum,
    ReconciliationResult,
)
from app.services.ai_explanation import AIExplanationService
from app.services.match import MatchService
from app.services.reconciliation import ReconciliationEngine

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["reconciliation"])


@router.post(
    "/reconcile",
    response_model=ReconciliationResult,
    status_code=status.HTTP_200_OK,
    summary="Run reconciliation",
)
def run_reconciliation(
    tenant_id: ValidatedTenantId,
    db: Session = Depends(get_db),
    min_score: float = Query(0.5, ge=0, le=1, description="Minimum match score threshold"),
) -> ReconciliationResult:
    """
    Run the reconciliation process to match invoices with bank transactions.

    This endpoint:
    1. Finds all open invoices and unmatched bank transactions
    2. Calculates match scores using deterministic heuristics
    3. Creates proposed match records for candidates above the threshold
    4. Returns the list of match candidates ranked by score

    **Scoring Algorithm:**
    - Amount match (40%): Exact match = 1.0, within tolerance = 0.8
    - Date proximity (30%): Same day = 1.0, scaling down with distance
    - Text similarity (20%): Token matching between descriptions
    - Currency match (10%): Same currency = 1.0

    Candidates with scores >= min_score are returned and stored as proposed matches.
    """
    engine = ReconciliationEngine(db)
    matches_created, candidates = engine.run_reconciliation(
        tenant_id=tenant_id,
        min_score=min_score,
        create_matches=True,
    )
    db.commit()

    # Build response
    candidate_responses = []
    for candidate in candidates:
        # Find the match ID if one was created
        match_id = None
        for match in matches_created:
            if (
                match.invoice_id == candidate.invoice.id
                and match.bank_transaction_id == candidate.transaction.id
            ):
                match_id = match.id
                break

        candidate_responses.append(
            MatchCandidateResponse(
                invoice=InvoiceResponse.model_validate(candidate.invoice),
                bank_transaction=BankTransactionResponse.model_validate(candidate.transaction),
                score=candidate.score,
                match_id=match_id,
            )
        )

    return ReconciliationResult(
        matches_created=len(matches_created),
        candidates=candidate_responses,
    )


@router.get(
    "/matches",
    response_model=MatchList,
    summary="List matches",
)
def list_matches(
    tenant_id: ValidatedTenantId,
    db: Session = Depends(get_db),
    status: MatchStatusEnum | None = Query(None, description="Filter by status"),
    invoice_id: str | None = Query(None, description="Filter by invoice ID"),
    transaction_id: str | None = Query(None, description="Filter by transaction ID"),
    min_score: Decimal | None = Query(None, description="Filter by minimum score"),
) -> MatchList:
    """List all matches for a tenant with optional filtering."""
    filters = MatchFilters(
        status=status,
        invoice_id=invoice_id,
        bank_transaction_id=transaction_id,
        min_score=min_score,
    )

    service = MatchService(db)
    matches = service.list_by_tenant(tenant_id, filters=filters)

    return MatchList(
        items=[MatchResponse.model_validate(m) for m in matches],
        total=len(matches),
    )


@router.get(
    "/matches/{match_id}",
    response_model=MatchDetailResponse,
    summary="Get match details",
)
def get_match(
    tenant_id: ValidatedTenantId,
    match_id: str,
    db: Session = Depends(get_db),
) -> MatchDetailResponse:
    """Get detailed information about a specific match."""
    service = MatchService(db)
    match = service.get_by_id(tenant_id, match_id)

    return MatchDetailResponse(
        id=match.id,
        tenant_id=match.tenant_id,
        invoice_id=match.invoice_id,
        bank_transaction_id=match.bank_transaction_id,
        score=match.score,
        status=MatchStatusEnum(match.status.value),
        created_at=match.created_at,
        invoice=InvoiceResponse.model_validate(match.invoice),
        bank_transaction=BankTransactionResponse.model_validate(match.bank_transaction),
    )


@router.post(
    "/matches/{match_id}/confirm",
    response_model=MatchResponse,
    summary="Confirm a match",
)
def confirm_match(
    tenant_id: ValidatedTenantId,
    match_id: str,
    db: Session = Depends(get_db),
) -> MatchResponse:
    """
    Confirm a proposed match.

    This action:
    1. Updates the match status to CONFIRMED
    2. Updates the invoice status to MATCHED
    3. Rejects other proposed matches for the same invoice/transaction
    """
    service = MatchService(db)
    match = service.confirm(tenant_id, match_id)
    db.commit()
    return MatchResponse.model_validate(match)


@router.post(
    "/matches/{match_id}/reject",
    response_model=MatchResponse,
    summary="Reject a match",
)
def reject_match(
    tenant_id: ValidatedTenantId,
    match_id: str,
    db: Session = Depends(get_db),
) -> MatchResponse:
    """Reject a proposed match."""
    service = MatchService(db)
    match = service.reject(tenant_id, match_id)
    db.commit()
    return MatchResponse.model_validate(match)


@router.get(
    "/reconcile/explain",
    response_model=ExplanationResponse,
    summary="Get AI explanation for a match",
)
def explain_match(
    tenant_id: ValidatedTenantId,
    invoice_id: str = Query(..., description="Invoice ID"),
    transaction_id: str = Query(..., description="Bank Transaction ID"),
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    """
    Get a natural-language explanation of the match decision.

    Uses AI (OpenAI) when available, with automatic fallback to
    deterministic explanations if AI is unavailable or fails.
    """
    service = AIExplanationService(db)
    return service.explain_match(tenant_id, invoice_id, transaction_id)
