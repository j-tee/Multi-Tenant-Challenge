"""Bank Transaction model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, generate_uuid


class BankTransaction(Base, TimestampMixin, TenantScopedMixin):
    """Bank Transaction model representing imported bank records."""

    __tablename__ = "bank_transactions"

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
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="bank_transactions")  # type: ignore[name-defined]
    matches: Mapped[list["Match"]] = relationship(  # type: ignore[name-defined]
        back_populates="bank_transaction",
        cascade="all, delete-orphan",
    )
