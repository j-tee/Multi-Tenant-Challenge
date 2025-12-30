"""Vendor model."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, generate_uuid


class Vendor(Base, TimestampMixin, TenantScopedMixin):
    """Vendor model representing a supplier or vendor."""

    __tablename__ = "vendors"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="vendors")  # type: ignore[name-defined]
    invoices: Mapped[list["Invoice"]] = relationship(  # type: ignore[name-defined]
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
