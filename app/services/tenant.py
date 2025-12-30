"""Tenant service."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate


class TenantService:
    """Service for tenant operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: TenantCreate) -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(name=data.name)
        self.db.add(tenant)
        self.db.flush()
        return tenant

    def get_by_id(self, tenant_id: str) -> Tenant:
        """Get tenant by ID."""
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = self.db.execute(stmt).scalar_one_or_none()
        if not tenant:
            raise NotFoundError("Tenant", tenant_id)
        return tenant

    def list_all(self) -> list[Tenant]:
        """List all tenants."""
        stmt = select(Tenant).order_by(Tenant.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def exists(self, tenant_id: str) -> bool:
        """Check if tenant exists."""
        stmt = select(Tenant.id).where(Tenant.id == tenant_id)
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def validate_tenant(self, tenant_id: str) -> Tenant:
        """Validate tenant exists and return it."""
        return self.get_by_id(tenant_id)
