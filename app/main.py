"""
main.py - FastAPI Application entrypoint with structured logging and request ID tracking.
"""

from contextlib import asynccontextmanager
import logging
import sys
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.db import init_db
from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.tickets import router as tickets_router
from app.services.classifier import get_classifier
from app.services.retrieval import get_retriever

# Setup structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("cerevyn.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown hooks."""
    logger.info("Initializing Azure Support Ticket Automation system...")
    logger.info("Configuration summary: %s", settings.safe_summary())

    # Initialize database tables
    init_db()
    logger.info("Database initialized successfully.")

    # Warm up Classifier & index KB Articles
    try:
        classifier = get_classifier()
        logger.info(
            "Classifier loaded. CV threshold: %.4f, Effective threshold: %.4f (Best C: %.2f)",
            classifier.cv_threshold,
            classifier.effective_threshold,
            classifier.best_c,
        )

        retriever = get_retriever()
        retriever.index_articles(classifier.embedder)
        logger.info("Indexed %d KB articles for grounded RAG retrieval.", len(retriever.articles))
    except Exception as e:
        logger.warning("Warmup encountered an issue (will load on demand): %s", e)

    yield
    logger.info("Shutting down Azure Support Ticket Automation system.")


app = FastAPI(
    title="Azure Support Ticket Automation API (PS04)",
    description=(
        "AI-assisted support ticket triage, deterministic classification & priority, "
        "RAG-lite grounded draft responses, and human-in-the-loop approval workflow.\n\n"
        "**Candidate**: Madhusudan Mudgal (Chitkara University, Roll: 2310990812)"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    """
    Attaches a unique Request ID to each incoming request, logs latency and status code,
    and returns X-Request-ID in response headers.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    start_time = time.time()
    logger.info("[%s] HTTP %s %s - Started", request_id, request.method, request.url.path)

    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "[%s] HTTP %s %s - Completed %d in %.2f ms",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )
        return response
    except Exception as exc:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            "[%s] HTTP %s %s - Unhandled Exception after %.2f ms: %s",
            request_id,
            request.method,
            request.url.path,
            process_time,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )


# Register API routers
app.include_router(health_router)
app.include_router(tickets_router)
app.include_router(metrics_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
