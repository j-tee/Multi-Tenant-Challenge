"""Pydantic schemas for Tenant."""

from datetime import datetime

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    """Schema for creating a tenant."""

    name: str = Field(..., min_length=1, max_length=255)


class TenantResponse(BaseModel):
    """Schema for tenant response."""

    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantList(BaseModel):
    """Schema for list of tenants."""

    items: list[TenantResponse]
    total: int
