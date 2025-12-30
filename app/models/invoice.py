"""Invoice model."""

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, generate_uuid


class InvoiceStatus(str, enum.Enum):
    """Invoice status enumeration."""

    OPEN = "open"
    MATCHED = "matched"
    PAID = "paid"


class Invoice(Base, TimestampMixin, TenantScopedMixin):
    """Invoice model."""

    __tablename__ = "invoices"

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
    vendor_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus),
        default=InvoiceStatus.OPEN,
        nullable=False,
        index=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="invoices")  # type: ignore[name-defined]
    vendor: Mapped["Vendor | None"] = relationship(back_populates="invoices")  # type: ignore[name-defined]
    matches: Mapped[list["Match"]] = relationship(  # type: ignore[name-defined]
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
