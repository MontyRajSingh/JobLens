"""
main.py — FastAPI application entry point for JobLens.

Configures:
- Lifespan events: load ML model + seed DB on startup
- CORS: env-var list in prod, all origins in dev
- Rate limiting via SlowAPI (60/min predict, 200/min general)
- API key auth on /predict in production
- Request logging middleware (method, path, status, duration)
- Routers mounted at /api/v1 prefix
- /health at root level

Run with: uvicorn api.main:app --reload --port 8000
"""

import os
import sys
import time
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load .env file for local development
from dotenv import load_dotenv
load_dotenv()

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.routes import predict as predict_routes
from api.routes import jobs as jobs_routes
from api.routes import insights as insights_routes
from api.db.database import engine
from api.db.loader import load_jobs_to_db
from api.schemas.response import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "pipeline", "models"))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "output"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
API_KEYS = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]

if ENVIRONMENT == "production" and not API_KEYS:
    # Don't hard-fail on deploy if secrets weren't configured yet.
    # In this mode, /api/v1/predict won't require X-API-Key (see middleware below).
    logger.warning(
        "ENVIRONMENT=production but API_KEYS is empty. "
        "Prediction endpoint will run without API-key protection until API_KEYS is set."
    )

# App state
_app_state = {
    "model_loaded": False,
    "jobs_count": 0,
    "model_metadata": {},
}

# ──────────────────────────────────────────────
# Rate Limiter
# ──────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ──────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load ML model + seed database."""
    logger.info("=" * 60)
    logger.info("JobLens API — Starting up (%s)", ENVIRONMENT)
    logger.info("=" * 60)

    # Load ML model
    model_path = os.path.join(MODEL_DIR, "model.pkl")
    if os.path.exists(model_path):
        try:
            from pipeline.predict import _ensure_loaded
            _ensure_loaded(MODEL_DIR)
            _app_state["model_loaded"] = True

            metadata_path = os.path.join(MODEL_DIR, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, "r") as f:
                    _app_state["model_metadata"] = json.load(f)

            logger.info("✅ ML model loaded from %s", MODEL_DIR)
        except Exception as e:
            logger.warning("⚠️  ML model not loaded: %s", e)
    else:
        logger.warning("⚠️  No model found at %s — prediction endpoint will return 503", model_path)

    # Get ACTUAL count from DB (Skip heavy CSV loading on every startup)
    from api.db.database import SessionLocal, init_db, engine
    from sqlalchemy import text
    
    logger.info("📡 API connecting to: %s", engine.url)
    init_db()
    with SessionLocal() as db:
        try:
            result = db.execute(text("SELECT COUNT(*) FROM jobs"))
            actual_count = result.scalar() or 0
            _app_state["jobs_count"] = actual_count
            logger.info("📊 Total jobs available in DB: %d", actual_count)
        except Exception as e:
            logger.warning("⚠️  Could not count jobs: %s", e)
            _app_state["jobs_count"] = 0

    logger.info("🚀 JobLens API ready at http://localhost:8000")
    logger.info("📖 Docs: http://localhost:8000/docs")

    yield

    logger.info("JobLens API — Shutting down")


# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────
app = FastAPI(
    title="JobLens API",
    description=(
        "Global Job Market Intelligence & Salary Prediction API.\n\n"
        "Provides salary predictions, job search, and market insights "
        "across multiple cities and job sources."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Attach limiter
app.state.limiter = limiter


# Rate limit error handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down."},
    )


# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────
ALLOW_CREDENTIALS = True
if ENVIRONMENT == "production":
    ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    if not ALLOWED_ORIGINS:
        # Keep the service bootable by default; user can tighten later via CORS_ORIGINS.
        logger.warning(
            "ENVIRONMENT=production but CORS_ORIGINS is empty. "
            "Falling back to allow all origins without credentials."
        )
        ALLOWED_ORIGINS = ["*"]
        ALLOW_CREDENTIALS = False
else:
    ALLOWED_ORIGINS = ["*"]
    ALLOW_CREDENTIALS = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# API Key Authentication Middleware (prod only)
# ──────────────────────────────────────────────
@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    """
    In production, require X-API-Key header for /api/v1/predict.
    Skipped in development mode.
    """
    if ENVIRONMENT == "production" and API_KEYS:
        path = request.url.path
        if path.startswith("/api/v1/predict"):
            api_key = request.headers.get("X-API-Key")
            if not api_key or api_key not in API_KEYS:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )
    return await call_next(request)


# ──────────────────────────────────────────────
# Request logging middleware
# ──────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with method, path, status, and duration."""
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000  # ms

    logger.info(
        "%s %s → %d (%.0fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response


# ──────────────────────────────────────────────
# Rate-Limited Routers
# ──────────────────────────────────────────────
app.include_router(predict_routes.router, prefix="/api/v1")
app.include_router(jobs_routes.router, prefix="/api/v1")
app.include_router(insights_routes.router, prefix="/api/v1")


# ──────────────────────────────────────────────
# Health check (root level)
# ──────────────────────────────────────────────
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="API health check",
)
async def health_check():
    """Check API health, model status, and job count."""
    meta = _app_state.get("model_metadata", {})
    return HealthResponse(
        status="ok",
        model_loaded=_app_state["model_loaded"],
        jobs_count=_app_state["jobs_count"],
        model_rmse=meta.get("rmse"),
        model_version=meta.get("model_version"),
        last_trained=meta.get("training_date"),
    )


@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    """Root redirect to docs."""
    return {
        "message": "Welcome to JobLens API",
        "docs": "/docs",
        "health": "/health",
    }
