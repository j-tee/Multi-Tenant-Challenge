"""Async Invoice service."""

from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.invoice import InvoiceCreate, InvoiceFilters


class InvoiceService:
    """Async service for invoice operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, tenant_id: str, data: InvoiceCreate) -> Invoice:
        """Create a new invoice."""
        invoice = Invoice(
            tenant_id=tenant_id,
            vendor_id=data.vendor_id,
            invoice_number=data.invoice_number,
            amount=data.amount,
            currency=data.currency,
            invoice_date=data.invoice_date,
            description=data.description,
            status=InvoiceStatus(data.status.value),
        )
        self.db.add(invoice)
        await self.db.flush()
        return invoice

    async def get_by_id(self, tenant_id: str, invoice_id: str) -> Invoice:
        """Get invoice by ID with tenant isolation."""
        stmt = (
            select(Invoice)
            .options(joinedload(Invoice.vendor))
            .where(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        invoice = result.unique().scalar_one_or_none()
        if not invoice:
            raise NotFoundError("Invoice", invoice_id)
        return invoice

    async def list_by_tenant(
        self,
        tenant_id: str,
        filters: InvoiceFilters | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Invoice], int]:
        """List invoices for a tenant with optional filtering."""
        # Base query with tenant isolation
        conditions = [Invoice.tenant_id == tenant_id]

        # Apply filters
        if filters:
            if filters.status:
                conditions.append(Invoice.status == InvoiceStatus(filters.status.value))
            if filters.vendor_id:
                conditions.append(Invoice.vendor_id == filters.vendor_id)
            if filters.date_from:
                conditions.append(Invoice.invoice_date >= filters.date_from)
            if filters.date_to:
                conditions.append(Invoice.invoice_date <= filters.date_to)
            if filters.amount_min:
                conditions.append(Invoice.amount >= filters.amount_min)
            if filters.amount_max:
                conditions.append(Invoice.amount <= filters.amount_max)

        # Count total
        count_stmt = select(func.count()).select_from(Invoice).where(and_(*conditions))
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated results
        stmt = (
            select(Invoice)
            .where(and_(*conditions))
            .order_by(Invoice.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        invoices = list(result.scalars().all())

        return invoices, total

    async def delete(self, tenant_id: str, invoice_id: str) -> None:
        """Delete an invoice with tenant isolation."""
        invoice = await self.get_by_id(tenant_id, invoice_id)
        if invoice.status == InvoiceStatus.MATCHED:
            raise ValidationError(
                "Cannot delete a matched invoice",
                {"invoice_id": invoice_id, "status": invoice.status.value},
            )
        await self.db.delete(invoice)
        await self.db.flush()

    async def update_status(
        self,
        tenant_id: str,
        invoice_id: str,
        status: InvoiceStatus,
    ) -> Invoice:
        """Update invoice status with tenant isolation."""
        invoice = await self.get_by_id(tenant_id, invoice_id)
        invoice.status = status
        await self.db.flush()
        return invoice

    async def get_open_invoices(self, tenant_id: str) -> list[Invoice]:
        """Get all open invoices for a tenant."""
        stmt = (
            select(Invoice)
            .options(joinedload(Invoice.vendor))
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.status == InvoiceStatus.OPEN,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())
