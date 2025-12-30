"""Bank Transaction service."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.bank_transaction import BankTransaction
from app.schemas.bank_transaction import (
    BankTransactionCreate,
    BankTransactionFilters,
    BankTransactionImportResult,
)


class BankTransactionService:
    """Service for bank transaction operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, tenant_id: str, data: BankTransactionCreate) -> BankTransaction:
        """Create a new bank transaction."""
        transaction = BankTransaction(
            tenant_id=tenant_id,
            external_id=data.external_id,
            posted_at=data.posted_at,
            amount=data.amount,
            currency=data.currency,
            description=data.description,
        )
        self.db.add(transaction)
        self.db.flush()
        return transaction

    def get_by_id(self, tenant_id: str, transaction_id: str) -> BankTransaction:
        """Get bank transaction by ID with tenant isolation."""
        stmt = select(BankTransaction).where(
            BankTransaction.id == transaction_id,
            BankTransaction.tenant_id == tenant_id,
        )
        transaction = self.db.execute(stmt).scalar_one_or_none()
        if not transaction:
            raise NotFoundError("BankTransaction", transaction_id)
        return transaction

    def get_by_external_id(
        self,
        tenant_id: str,
        external_id: str,
    ) -> BankTransaction | None:
        """Get bank transaction by external ID with tenant isolation."""
        stmt = select(BankTransaction).where(
            BankTransaction.external_id == external_id,
            BankTransaction.tenant_id == tenant_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def bulk_import(
        self,
        tenant_id: str,
        transactions: list[BankTransactionCreate],
    ) -> BankTransactionImportResult:
        """Bulk import bank transactions, skipping duplicates by external_id."""
        imported = []
        skipped = 0

        for tx_data in transactions:
            # Check for duplicate by external_id if provided
            if tx_data.external_id:
                existing = self.get_by_external_id(tenant_id, tx_data.external_id)
                if existing:
                    skipped += 1
                    continue

            transaction = self.create(tenant_id, tx_data)
            imported.append(transaction)

        return BankTransactionImportResult(
            imported=len(imported),
            skipped=skipped,
            transactions=[
                self._to_response(tx) for tx in imported
            ],
        )

    def list_by_tenant(
        self,
        tenant_id: str,
        filters: BankTransactionFilters | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[BankTransaction], int]:
        """List bank transactions for a tenant with optional filtering."""
        conditions = [BankTransaction.tenant_id == tenant_id]

        if filters:
            if filters.date_from:
                conditions.append(BankTransaction.posted_at >= filters.date_from)
            if filters.date_to:
                conditions.append(BankTransaction.posted_at <= filters.date_to)
            if filters.amount_min:
                conditions.append(BankTransaction.amount >= filters.amount_min)
            if filters.amount_max:
                conditions.append(BankTransaction.amount <= filters.amount_max)

        # Count total
        count_stmt = select(BankTransaction.id).where(and_(*conditions))
        total = len(list(self.db.execute(count_stmt).scalars().all()))

        # Get paginated results
        stmt = (
            select(BankTransaction)
            .where(and_(*conditions))
            .order_by(BankTransaction.posted_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        transactions = list(self.db.execute(stmt).scalars().all())

        return transactions, total

    def get_unmatched_transactions(self, tenant_id: str) -> list[BankTransaction]:
        """Get all unmatched transactions for a tenant."""
        from app.models.match import Match, MatchStatus

        # Get IDs of transactions that have confirmed matches
        matched_stmt = (
            select(Match.bank_transaction_id)
            .where(
                Match.tenant_id == tenant_id,
                Match.status == MatchStatus.CONFIRMED,
            )
        )
        matched_ids = [
            row for row in self.db.execute(matched_stmt).scalars().all()
        ]

        # Get transactions not in matched list
        stmt = select(BankTransaction).where(
            BankTransaction.tenant_id == tenant_id,
            ~BankTransaction.id.in_(matched_ids) if matched_ids else True,
        )
        return list(self.db.execute(stmt).scalars().all())

    def _to_response(self, tx: BankTransaction) -> dict:
        """Convert transaction to response dict."""
        from app.schemas.bank_transaction import BankTransactionResponse
        return BankTransactionResponse.model_validate(tx).model_dump()
