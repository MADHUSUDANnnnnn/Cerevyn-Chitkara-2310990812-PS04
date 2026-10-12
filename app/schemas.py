"""
schemas.py - Pydantic models for request validation and response serialization.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


TicketCategory = Literal["Billing", "Technical", "Access", "General"]
TicketPriority = Literal["low", "medium", "high"]
TicketStatus = Literal["received", "draft_generated", "needs_review", "approved", "ready"]
DraftSource = Literal["llm", "template"]


class TicketCreateRequest(BaseModel):
    ticket_id: str = Field(
        ...,
        description="Unique identifier for the ticket (e.g., TCK-1001)",
        min_length=1,
        max_length=64,
    )
    message: str = Field(
        ...,
        description="Support request body text",
        min_length=1,
        max_length=4000,
    )

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("ticket_id cannot be empty or purely whitespace")
        return cleaned

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("message cannot be empty or purely whitespace")
        return cleaned


class TicketResponse(BaseModel):
    ticket_id: str
    message: str
    category: TicketCategory
    priority: TicketPriority
    assigned_team: str
    summary: str
    draft_response: str
    status: TicketStatus
    confidence: float
    draft_source: DraftSource
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketApproveResponse(BaseModel):
    message: str
    ticket: TicketResponse


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "ok"
    timestamp: datetime


class HealthLLMResponse(BaseModel):
    configured: bool
    reachable: bool
    model: Optional[str] = None
    base_url: Optional[str] = None
    message: str


class LLMOutputSchema(BaseModel):
    summary: str = Field(..., description="A concise 1-2 sentence executive summary of the issue.")
    draft_response: str = Field(..., description="Professional, grounded draft response to the customer.")

    @field_validator("summary", "draft_response")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned
