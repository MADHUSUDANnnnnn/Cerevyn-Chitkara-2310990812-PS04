"""
health.py - Health check endpoints for system liveness and LLM reachability.
"""

from datetime import datetime
import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.schemas import HealthLLMResponse, HealthResponse

logger = logging.getLogger("cerevyn.health")
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application and database liveness health check",
)
def health_check(db: Session = Depends(get_db)):
    # Verify DB connectivity
    db.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok",
        database="ok",
        timestamp=datetime.utcnow(),
    )


@router.get(
    "/health/llm",
    response_model=HealthLLMResponse,
    summary="LLM endpoint configuration and reachability check (no ticket data sent)",
)
def health_llm_check():
    """
    Probes LLM endpoint connectivity without transmitting any ticket data.
    """
    if not settings.GROQ_API_KEY:
        return HealthLLMResponse(
            configured=False,
            reachable=False,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            message="LLM is not configured (GROQ_API_KEY is not set). System runs deterministically with TemplateClient.",
        )

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=min(5.0, settings.LLM_TIMEOUT_SECONDS),
        )
        # Lightweight probe: list models or make a minimal non-data check
        client.models.list()
        return HealthLLMResponse(
            configured=True,
            reachable=True,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            message="LLM endpoint is configured and reachable.",
        )
    except Exception as e:
        logger.warning("LLM reachability check failed: %s", type(e).__name__)
        return HealthLLMResponse(
            configured=True,
            reachable=False,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            message=f"LLM is configured but currently unreachable: {type(e).__name__}.",
        )
