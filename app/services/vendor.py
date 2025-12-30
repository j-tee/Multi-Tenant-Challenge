"""Vendor service."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate


class VendorService:
    """Service for vendor operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, tenant_id: str, data: VendorCreate) -> Vendor:
        """Create a new vendor."""
        vendor = Vendor(tenant_id=tenant_id, name=data.name)
        self.db.add(vendor)
        self.db.flush()
        return vendor

    def get_by_id(self, tenant_id: str, vendor_id: str) -> Vendor:
        """Get vendor by ID with tenant isolation."""
        stmt = select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.tenant_id == tenant_id,
        )
        vendor = self.db.execute(stmt).scalar_one_or_none()
        if not vendor:
            raise NotFoundError("Vendor", vendor_id)
        return vendor

    def list_by_tenant(self, tenant_id: str) -> list[Vendor]:
        """List all vendors for a tenant."""
        stmt = (
            select(Vendor)
            .where(Vendor.tenant_id == tenant_id)
            .order_by(Vendor.name)
        )
        return list(self.db.execute(stmt).scalars().all())
