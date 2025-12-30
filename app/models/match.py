"""Match model for invoice-transaction reconciliation."""

import enum
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, generate_uuid


class MatchStatus(str, enum.Enum):
    """Match status enumeration."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Match(Base, TimestampMixin, TenantScopedMixin):
    """Match model representing a reconciliation match between invoice and transaction."""

    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bank_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        comment="Confidence score between 0 and 1",
    )
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus),
        default=MatchStatus.PROPOSED,
        nullable=False,
        index=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="matches")  # type: ignore[name-defined]
    invoice: Mapped["Invoice"] = relationship(back_populates="matches")  # type: ignore[name-defined]
    bank_transaction: Mapped["BankTransaction"] = relationship(back_populates="matches")  # type: ignore[name-defined]
