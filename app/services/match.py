"""Match service."""

from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.invoice import InvoiceStatus
from app.models.match import Match, MatchStatus
from app.schemas.match import MatchFilters


class MatchService:
    """Service for match operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, tenant_id: str, match_id: str) -> Match:
        """Get match by ID with tenant isolation."""
        stmt = (
            select(Match)
            .options(joinedload(Match.invoice), joinedload(Match.bank_transaction))
            .where(
                Match.id == match_id,
                Match.tenant_id == tenant_id,
            )
        )
        match = self.db.execute(stmt).unique().scalar_one_or_none()
        if not match:
            raise NotFoundError("Match", match_id)
        return match

    def list_by_tenant(
        self,
        tenant_id: str,
        filters: MatchFilters | None = None,
    ) -> list[Match]:
        """List matches for a tenant with optional filtering."""
        conditions = [Match.tenant_id == tenant_id]

        if filters:
            if filters.status:
                conditions.append(Match.status == MatchStatus(filters.status.value))
            if filters.invoice_id:
                conditions.append(Match.invoice_id == filters.invoice_id)
            if filters.bank_transaction_id:
                conditions.append(Match.bank_transaction_id == filters.bank_transaction_id)
            if filters.min_score:
                conditions.append(Match.score >= filters.min_score)

        stmt = (
            select(Match)
            .options(joinedload(Match.invoice), joinedload(Match.bank_transaction))
            .where(and_(*conditions))
            .order_by(Match.score.desc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def confirm(self, tenant_id: str, match_id: str) -> Match:
        """
        Confirm a proposed match.

        This will:
        1. Update match status to CONFIRMED
        2. Update invoice status to MATCHED
        3. Reject other proposed matches for the same invoice/transaction
        """
        match = self.get_by_id(tenant_id, match_id)

        if match.status == MatchStatus.CONFIRMED:
            return match  # Already confirmed, idempotent

        if match.status == MatchStatus.REJECTED:
            raise ValidationError(
                "Cannot confirm a rejected match",
                {"match_id": match_id, "status": match.status.value},
            )

        # Confirm this match
        match.status = MatchStatus.CONFIRMED

        # Update invoice status
        match.invoice.status = InvoiceStatus.MATCHED

        # Reject other proposed matches for the same invoice
        stmt = select(Match).where(
            Match.tenant_id == tenant_id,
            Match.invoice_id == match.invoice_id,
            Match.id != match_id,
            Match.status == MatchStatus.PROPOSED,
        )
        for other_match in self.db.execute(stmt).scalars().all():
            other_match.status = MatchStatus.REJECTED

        # Reject other proposed matches for the same transaction
        stmt = select(Match).where(
            Match.tenant_id == tenant_id,
            Match.bank_transaction_id == match.bank_transaction_id,
            Match.id != match_id,
            Match.status == MatchStatus.PROPOSED,
        )
        for other_match in self.db.execute(stmt).scalars().all():
            other_match.status = MatchStatus.REJECTED

        self.db.flush()
        return match

    def reject(self, tenant_id: str, match_id: str) -> Match:
        """Reject a proposed match."""
        match = self.get_by_id(tenant_id, match_id)

        if match.status != MatchStatus.PROPOSED:
            raise ValidationError(
                "Can only reject proposed matches",
                {"match_id": match_id, "status": match.status.value},
            )

        match.status = MatchStatus.REJECTED
        self.db.flush()
        return match
