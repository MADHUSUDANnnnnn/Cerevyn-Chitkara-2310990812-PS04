"""
health.py - Health check endpoints for system liveness and LLM reachability.
"""

from datetime import datetime
import logging
from fastapi import APIRouter, Depends, status
from openai import OpenAI
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

    The LLM is considered configured only when ALL THREE of GROQ_API_KEY,
    LLM_BASE_URL, and LLM_MODEL are set.  If any are missing the endpoint
    returns configured=False, lists the missing setting *names* (never
    values), and makes no network call — preventing the OpenAI SDK from
    silently falling back to https://api.openai.com.
    """
    missing = settings.llm_missing_settings()
    if missing:
        names_str = ", ".join(missing)
        logger.info("LLM health check: not configured. Missing settings: %s", names_str)
        return HealthLLMResponse(
            configured=False,
            reachable=False,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            missing_settings=missing,
            message=(
                f"LLM is not fully configured. Missing settings: {names_str}. "
                "System runs deterministically with TemplateClient."
            ),
        )

    # All three settings are present — safe to construct the SDK client.
    try:
        client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.LLM_BASE_URL,  # explicit; never relies on SDK default
            timeout=min(5.0, settings.LLM_TIMEOUT_SECONDS),
        )
        # Lightweight probe: list models — no ticket data is transmitted
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
