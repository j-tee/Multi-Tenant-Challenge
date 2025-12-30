"""Pydantic schemas for Vendor."""

from datetime import datetime

from pydantic import BaseModel, Field


class VendorCreate(BaseModel):
    """Schema for creating a vendor."""

    name: str = Field(..., min_length=1, max_length=255)


class VendorResponse(BaseModel):
    """Schema for vendor response."""

    id: str
    tenant_id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VendorList(BaseModel):
    """Schema for list of vendors."""

    items: list[VendorResponse]
    total: int
