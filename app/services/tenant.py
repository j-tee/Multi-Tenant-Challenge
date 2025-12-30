"""Async Tenant service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate


class TenantService:
    """Async service for tenant operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: TenantCreate) -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(name=data.name)
        self.db.add(tenant)
        await self.db.flush()
        return tenant

    async def get_by_id(self, tenant_id: str) -> Tenant:
        """Get tenant by ID."""
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.db.execute(stmt)
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundError("Tenant", tenant_id)
        return tenant

    async def list_all(self) -> list[Tenant]:
        """List all tenants."""
        stmt = select(Tenant).order_by(Tenant.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def exists(self, tenant_id: str) -> bool:
        """Check if tenant exists."""
        stmt = select(Tenant.id).where(Tenant.id == tenant_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def validate_tenant(self, tenant_id: str) -> Tenant:
        """Validate tenant exists and return it."""
        return await self.get_by_id(tenant_id)
