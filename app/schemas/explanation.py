"""Pydantic schemas for AI explanation."""

from pydantic import BaseModel


class ExplanationRequest(BaseModel):
    """Schema for explanation request."""

    invoice_id: str
    transaction_id: str


class ExplanationResponse(BaseModel):
    """Schema for explanation response."""

    invoice_id: str
    transaction_id: str
    explanation: str
    confidence: str | None = None
    is_fallback: bool = False
