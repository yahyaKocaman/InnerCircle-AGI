from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.limiter import limiter
from app.core.middleware import SecurityHeadersMiddleware, RequestLoggingMiddleware
from app.infrastructure.database import Base, engine
from app.infrastructure.chroma_client import get_chroma_client
from app.infrastructure.openai_client import llm
from app.api import auth
from app.api import council, insights, profile, dashboard
from app.api.deps import get_db
import os

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialise DB tables and ChromaDB on startup."""
    # SQL tables
    Base.metadata.create_all(bind=engine)
    # ChromaDB — create collections for all agents
    get_chroma_client()
    # Log LLM status
    import logging
    logger = logging.getLogger(__name__)
    llm_status = await llm.health_check()
    logger.info(f"LLM status: {llm_status['status']} | model={llm_status.get('configured_model')}")
    yield


# ── FastAPI Application ───────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## InnerCircle AGI — Your Private Advisory Council
""",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── Security: Rate Limiter ────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security: CORS ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security: HTTP Security Headers ──────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── Observability: Request Logging ───────────────────────────
app.add_middleware(RequestLoggingMiddleware)

# ── API Routes ────────────────────────────────────────────────
app.include_router(auth.router,     prefix="/auth")
app.include_router(council.router,  prefix="/council")
app.include_router(insights.router, prefix="/insights")
app.include_router(profile.router,  prefix="/profile")
app.include_router(dashboard.router, prefix="/dashboard")

# ── Observability: Prometheus Metrics ────────────────────────
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
).instrument(app).expose(app)

# ── Static files + Frontend SPA ──────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "app", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse(os.path.join(static_dir, "index.html"))


# ── System Endpoints ─────────────────────────────────────────
@app.get("/health", tags=["System"], summary="Health check")
async def health(db: Session = Depends(get_db)):
    """
    Detailed health check for load balancers and monitoring.
    Checks: API, database, OpenAI LLM connectivity.
    """
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    llm_info = await llm.health_check()
    llm_status = llm_info.get("status", "unknown")

    overall = "ok" if db_status == "ok" else "degraded"
    if llm_status != "ok":
        overall = "degraded"

    return {
        "status":    overall,
        "app":       settings.APP_NAME,
        "version":   settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "api":            "ok",
            "database":       db_status,
            "llm":            llm_status,
            "llm_model":      settings.OPENAI_MODEL,
            "model_available": llm_info.get("model_available", False),
        },
    }