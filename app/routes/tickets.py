"""
tickets.py - Support ticket management routes: submission, retrieval, filtering, and approval.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Ticket
from app.schemas import (
    TicketApproveResponse,
    TicketCreateRequest,
    TicketResponse,
)
from app.services.pipeline import approve_ticket, process_ticket

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new support ticket",
)
def create_ticket(
    payload: TicketCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    request_id = getattr(request.state, "request_id", None)
    ticket = process_ticket(
        ticket_id=payload.ticket_id,
        message=payload.message,
        db=db,
        request_id=request_id,
    )
    return ticket


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get details of a specific ticket",
)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )
    return ticket


@router.get(
    "",
    response_model=List[TicketResponse],
    summary="List all tickets with optional status filter",
)
def list_tickets(
    status: Optional[str] = Query(
        None,
        description="Optional filter by status (e.g. received, draft_generated, needs_review, ready)",
    ),
    db: Session = Depends(get_db),
):
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    return query.order_by(Ticket.created_at.desc()).all()


@router.post(
    "/{ticket_id}/approve",
    response_model=TicketApproveResponse,
    summary="Human approval of ticket draft, marking it ready",
)
def approve_ticket_endpoint(
    ticket_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    request_id = getattr(request.state, "request_id", None)
    ticket = approve_ticket(ticket_id=ticket_id, db=db, request_id=request_id)
    return TicketApproveResponse(
        message=f"Draft for ticket '{ticket_id}' successfully approved and marked ready.",
        ticket=ticket,
    )
