"""Pydantic schemas for Reconciliation."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class ReconciliationRunStatusEnum(str, Enum):
    """Reconciliation run status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconciliationRunCreate(BaseModel):
    """Schema for creating a reconciliation run."""

    description: str | None = None
    auto_match_threshold: Decimal = Field(
        default=Decimal("0.8"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Minimum confidence score for auto-matching"
    )


class ReconciliationRunResponse(BaseModel):
    """Schema for reconciliation run response."""

    id: str
    tenant_id: str
    status: ReconciliationRunStatusEnum
    description: str | None
    matches_found: int = 0
    matches_auto_approved: int = 0
    started_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReconciliationRunList(BaseModel):
    """Schema for list of reconciliation runs."""

    items: list[ReconciliationRunResponse]
    total: int
    page: int = 1
    page_size: int = 50


class ReconciliationSummary(BaseModel):
    """Summary statistics for reconciliation."""

    total_invoices: int = 0
    matched_invoices: int = 0
    unmatched_invoices: int = 0
    total_transactions: int = 0
    matched_transactions: int = 0
    unmatched_transactions: int = 0
    total_matches: int = 0


class ReconciliationReportResponse(BaseModel):
    """Schema for reconciliation report response."""

    tenant_id: str
    summary: ReconciliationSummary
    recent_runs: list[ReconciliationRunResponse] = []
    generated_at: datetime

    model_config = {"from_attributes": True}
