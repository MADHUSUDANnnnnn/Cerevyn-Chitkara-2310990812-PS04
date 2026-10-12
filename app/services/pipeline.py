"""
pipeline.py - Core processing pipeline orchestrator.
Coordinates: Input Validation -> Embedding Classification -> Priority Assignment ->
RAG-lite Grounded Retrieval -> LLM / Template Draft Generation -> State Machine Persistence.
"""

import logging
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Ticket
from app.services.classifier import get_classifier
from app.services.llm import get_llm_client
from app.services.priority import determine_priority
from app.services.retrieval import get_retriever

logger = logging.getLogger("cerevyn.pipeline")


def process_ticket(
    ticket_id: str,
    message: str,
    db: Session,
    request_id: Optional[str] = None,
) -> Ticket:
    """
    Executes the deterministic & AI support ticket pipeline.
    """
    req_tag = f"[{request_id}] " if request_id else ""
    logger.info("%sStarting pipeline processing for ticket '%s'", req_tag, ticket_id)

    # 1. Check for duplicate ticket_id
    existing = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if existing:
        logger.warning("%sDuplicate ticket_id detected: '%s'", req_tag, ticket_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket ID '{ticket_id}' already exists in database.",
        )

    # 2. Category Classification
    classifier = get_classifier()
    category, confidence, needs_review = classifier.predict(message)
    ticket_status = "needs_review" if needs_review else "draft_generated"
    logger.info(
        "%sClassification result: category=%s, confidence=%.4f (threshold=%.4f, status=%s)",
        req_tag,
        category,
        confidence,
        classifier.effective_threshold,
        ticket_status,
    )

    # 3. Deterministic Priority Assignment
    priority, priority_reason = determine_priority(message, category)
    logger.info("%sPriority assigned: %s (%s)", req_tag, priority, priority_reason)

    # 4. Team Routing
    assigned_team = settings.TEAM_ROUTING.get(category, "Customer Care")

    # 5. RAG-lite Grounded KB Retrieval
    retriever = get_retriever()
    query_embedding = classifier.embedder.encode(message, normalize_embeddings=True)
    kb_article, similarity_score = retriever.retrieve(query_embedding)
    if kb_article:
        logger.info(
            "%sMatched KB article '%s' (similarity=%.4f)",
            req_tag,
            kb_article.get("id"),
            similarity_score,
        )
    else:
        logger.info(
            "%sNo KB article matched above threshold (top similarity=%.4f)",
            req_tag,
            similarity_score,
        )

    # 6. LLM / Template Draft Generation
    llm_client = get_llm_client()
    llm_output, draft_source = llm_client.generate_draft(
        message=message,
        category=category,
        priority=priority,
        kb_article=kb_article,
    )
    logger.info("%sDraft generated via source: %s", req_tag, draft_source)

    # 7. Persist Ticket State
    ticket = Ticket(
        ticket_id=ticket_id,
        message=message,
        category=category,
        priority=priority,
        assigned_team=assigned_team,
        summary=llm_output.summary,
        draft_response=llm_output.draft_response,
        status=ticket_status,
        confidence=confidence,
        draft_source=draft_source,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    logger.info("%sTicket '%s' persisted successfully with status '%s'", req_tag, ticket_id, ticket_status)
    return ticket


def approve_ticket(ticket_id: str, db: Session, request_id: Optional[str] = None) -> Ticket:
    """
    Transitions a ticket from 'draft_generated' or 'needs_review' -> 'approved' -> 'ready'.
    Throws 404 if ticket doesn't exist.
    Throws 409 if already ready/approved or in an invalid state.
    """
    req_tag = f"[{request_id}] " if request_id else ""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        logger.warning("%sApprove failed: Ticket '%s' not found.", req_tag, ticket_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )

    if ticket.status == "ready":
        logger.warning("%sApprove conflict: Ticket '%s' is already in 'ready' status.", req_tag, ticket_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket '{ticket_id}' has already been approved and is marked ready.",
        )

    if ticket.status not in ("draft_generated", "needs_review"):
        logger.warning("%sApprove conflict: Ticket '%s' in unexpected status '%s'.", req_tag, ticket_id, ticket.status)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket '{ticket_id}' cannot be approved from current status '{ticket.status}'.",
        )

    # Transition: approved -> ready
    ticket.status = "ready"
    db.commit()
    db.refresh(ticket)
    logger.info("%sTicket '%s' successfully approved and marked 'ready'.", req_tag, ticket_id)
    return ticket
