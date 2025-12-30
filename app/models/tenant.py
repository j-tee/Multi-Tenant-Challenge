"""Tenant model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Tenant(Base, TimestampMixin):
    """Tenant model representing an organization."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Relationships
    vendors: Mapped[list["Vendor"]] = relationship(  # type: ignore[name-defined]
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    invoices: Mapped[list["Invoice"]] = relationship(  # type: ignore[name-defined]
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    bank_transactions: Mapped[list["BankTransaction"]] = relationship(  # type: ignore[name-defined]
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    matches: Mapped[list["Match"]] = relationship(  # type: ignore[name-defined]
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
