"""
Reconciliation Engine - Deterministic matching heuristics.

This module implements the core reconciliation logic using deterministic heuristics
to match invoices with bank transactions. The scoring system is designed to produce
reliable matches without relying on AI.

Scoring Algorithm:
------------------
The final score is a weighted combination of multiple factors:

1. Amount Match (40% weight):
   - Exact match: 1.0
   - Within tolerance (default 1%): 0.8
   - No match: 0.0

2. Date Proximity (30% weight):
   - Same day: 1.0
   - Within 1 day: 0.9
   - Within 3 days (configurable): 0.7
   - Within 7 days: 0.4
   - Beyond 7 days: 0.0

3. Text Similarity (20% weight):
   - Uses a simple contains/token matching approach
   - Scores based on common tokens between descriptions

4. Currency Match (10% weight):
   - Same currency: 1.0
   - Different currency: 0.0

Final Score = (amount_score * 0.4) + (date_score * 0.3) + 
              (text_score * 0.2) + (currency_score * 0.1)

Match Threshold:
- Candidates with score >= 0.5 are considered viable matches
- Candidates are ranked by score in descending order
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.bank_transaction import BankTransaction
from app.models.invoice import Invoice, InvoiceStatus
from app.models.match import Match, MatchStatus
from app.services.invoice import InvoiceService
from app.services.bank_transaction import BankTransactionService


@dataclass
class MatchCandidate:
    """Represents a potential match between an invoice and transaction."""

    invoice: Invoice
    transaction: BankTransaction
    score: Decimal
    amount_score: float
    date_score: float
    text_score: float
    currency_score: float


class ReconciliationEngine:
    """
    Engine for matching invoices with bank transactions using deterministic heuristics.
    """

    # Scoring weights
    AMOUNT_WEIGHT = 0.4
    DATE_WEIGHT = 0.3
    TEXT_WEIGHT = 0.2
    CURRENCY_WEIGHT = 0.1

    # Thresholds
    MIN_MATCH_SCORE = 0.5

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.invoice_service = InvoiceService(db)
        self.transaction_service = BankTransactionService(db)

    def calculate_amount_score(
        self,
        invoice_amount: Decimal,
        transaction_amount: Decimal,
    ) -> float:
        """
        Calculate score based on amount matching.

        Returns:
            - 1.0 for exact match
            - 0.8 for match within tolerance
            - 0.0 for no match
        """
        # Handle sign differences (invoices are typically positive, transactions may be negative)
        inv_amt = abs(invoice_amount)
        tx_amt = abs(transaction_amount)

        if inv_amt == tx_amt:
            return 1.0

        # Calculate percentage difference
        if inv_amt == 0:
            return 0.0

        diff_percent = abs(float(inv_amt - tx_amt)) / float(inv_amt)
        tolerance = self.settings.reconciliation_amount_tolerance_percent

        if diff_percent <= tolerance:
            return 0.8

        return 0.0

    def calculate_date_score(
        self,
        invoice_date: date | None,
        transaction_date: datetime,
    ) -> float:
        """
        Calculate score based on date proximity.

        Returns score between 0.0 and 1.0 based on how close the dates are.
        """
        if invoice_date is None:
            # If no invoice date, give a neutral score
            return 0.5

        tx_date = transaction_date.date() if isinstance(transaction_date, datetime) else transaction_date
        days_diff = abs((tx_date - invoice_date).days)
        tolerance = self.settings.reconciliation_date_tolerance_days

        if days_diff == 0:
            return 1.0
        elif days_diff == 1:
            return 0.9
        elif days_diff <= tolerance:
            return 0.7
        elif days_diff <= 7:
            return 0.4
        else:
            return 0.0

    def calculate_text_score(
        self,
        invoice_desc: str | None,
        transaction_desc: str | None,
        invoice_number: str | None = None,
        vendor_name: str | None = None,
    ) -> float:
        """
        Calculate score based on text similarity using token matching.

        Checks for:
        - Common words between descriptions
        - Invoice number in transaction description
        - Vendor name in transaction description
        """
        if not transaction_desc:
            return 0.0

        tx_lower = transaction_desc.lower()
        score = 0.0
        checks = 0

        # Check if invoice number appears in transaction
        if invoice_number:
            checks += 1
            if invoice_number.lower() in tx_lower:
                score += 1.0

        # Check if vendor name appears in transaction
        if vendor_name:
            checks += 1
            if vendor_name.lower() in tx_lower:
                score += 1.0

        # Token matching between descriptions
        if invoice_desc:
            checks += 1
            inv_tokens = set(self._tokenize(invoice_desc))
            tx_tokens = set(self._tokenize(transaction_desc))

            if inv_tokens and tx_tokens:
                common = inv_tokens & tx_tokens
                similarity = len(common) / max(len(inv_tokens), len(tx_tokens))
                score += similarity

        if checks == 0:
            return 0.0

        return score / checks

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into meaningful words."""
        # Remove special characters and split
        words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
        # Filter out common stop words and very short words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        return [w for w in words if len(w) > 2 and w not in stop_words]

    def calculate_currency_score(
        self,
        invoice_currency: str,
        transaction_currency: str,
    ) -> float:
        """Calculate score based on currency matching."""
        return 1.0 if invoice_currency.upper() == transaction_currency.upper() else 0.0

    def calculate_match_score(
        self,
        invoice: Invoice,
        transaction: BankTransaction,
    ) -> MatchCandidate:
        """Calculate overall match score between invoice and transaction."""
        # Get vendor name if available
        vendor_name = invoice.vendor.name if invoice.vendor else None

        # Calculate individual scores
        amount_score = self.calculate_amount_score(invoice.amount, transaction.amount)
        date_score = self.calculate_date_score(invoice.invoice_date, transaction.posted_at)
        text_score = self.calculate_text_score(
            invoice.description,
            transaction.description,
            invoice.invoice_number,
            vendor_name,
        )
        currency_score = self.calculate_currency_score(
            invoice.currency,
            transaction.currency,
        )

        # Calculate weighted final score
        final_score = (
            amount_score * self.AMOUNT_WEIGHT +
            date_score * self.DATE_WEIGHT +
            text_score * self.TEXT_WEIGHT +
            currency_score * self.CURRENCY_WEIGHT
        )

        return MatchCandidate(
            invoice=invoice,
            transaction=transaction,
            score=Decimal(str(round(final_score, 4))),
            amount_score=amount_score,
            date_score=date_score,
            text_score=text_score,
            currency_score=currency_score,
        )

    def find_candidates(
        self,
        tenant_id: str,
        min_score: float | None = None,
    ) -> list[MatchCandidate]:
        """
        Find all potential match candidates for a tenant.

        Returns candidates sorted by score in descending order.
        """
        min_score = min_score or self.MIN_MATCH_SCORE

        # Get open invoices and unmatched transactions
        invoices = self.invoice_service.get_open_invoices(tenant_id)
        transactions = self.transaction_service.get_unmatched_transactions(tenant_id)

        candidates = []

        for invoice in invoices:
            for transaction in transactions:
                candidate = self.calculate_match_score(invoice, transaction)
                if float(candidate.score) >= min_score:
                    candidates.append(candidate)

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        return candidates

    def run_reconciliation(
        self,
        tenant_id: str,
        min_score: float | None = None,
        create_matches: bool = True,
    ) -> tuple[list[Match], list[MatchCandidate]]:
        """
        Run the reconciliation process for a tenant.

        Args:
            tenant_id: The tenant to reconcile
            min_score: Minimum score threshold (default: 0.5)
            create_matches: Whether to create Match records for candidates

        Returns:
            Tuple of (created matches, all candidates)
        """
        from sqlalchemy import select

        candidates = self.find_candidates(tenant_id, min_score)
        matches_created = []

        if create_matches:
            # Track which invoices and transactions already have proposed matches
            used_invoices = set()
            used_transactions = set()

            # Check for existing proposed matches
            existing_stmt = select(Match).where(
                Match.tenant_id == tenant_id,
                Match.status == MatchStatus.PROPOSED,
            )
            for existing in self.db.execute(existing_stmt).scalars().all():
                used_invoices.add(existing.invoice_id)
                used_transactions.add(existing.bank_transaction_id)

            for candidate in candidates:
                # Skip if invoice or transaction already has a proposed match
                if candidate.invoice.id in used_invoices:
                    continue
                if candidate.transaction.id in used_transactions:
                    continue

                # Create match record
                match = Match(
                    tenant_id=tenant_id,
                    invoice_id=candidate.invoice.id,
                    bank_transaction_id=candidate.transaction.id,
                    score=candidate.score,
                    status=MatchStatus.PROPOSED,
                )
                self.db.add(match)
                matches_created.append(match)

                used_invoices.add(candidate.invoice.id)
                used_transactions.add(candidate.transaction.id)

            self.db.flush()

        return matches_created, candidates

    def get_score_explanation(
        self,
        invoice: Invoice,
        transaction: BankTransaction,
    ) -> dict:
        """Get a detailed breakdown of the match score."""
        candidate = self.calculate_match_score(invoice, transaction)

        return {
            "final_score": float(candidate.score),
            "breakdown": {
                "amount": {
                    "score": candidate.amount_score,
                    "weight": self.AMOUNT_WEIGHT,
                    "invoice_amount": str(invoice.amount),
                    "transaction_amount": str(transaction.amount),
                },
                "date": {
                    "score": candidate.date_score,
                    "weight": self.DATE_WEIGHT,
                    "invoice_date": str(invoice.invoice_date) if invoice.invoice_date else None,
                    "transaction_date": str(transaction.posted_at),
                },
                "text": {
                    "score": candidate.text_score,
                    "weight": self.TEXT_WEIGHT,
                    "invoice_description": invoice.description,
                    "transaction_description": transaction.description,
                },
                "currency": {
                    "score": candidate.currency_score,
                    "weight": self.CURRENCY_WEIGHT,
                    "invoice_currency": invoice.currency,
                    "transaction_currency": transaction.currency,
                },
            },
        }
