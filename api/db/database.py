"""
database.py — SQLAlchemy engine and session management.

Dev: SQLite at data/jobs.db (when no DATABASE_URL is set)
Prod: DATABASE_URL env var (PostgreSQL on Railway / Docker).

Provides get_db() dependency for FastAPI route injection
and get_engine() for use by the scraper and training pipelines.
"""

import os
import logging

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Database URL
# ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Production (PostgreSQL on Railway / Docker)
    # Railway sometimes uses postgres:// which SQLAlchemy doesn't support
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    logger.info("Using PostgreSQL: %s", DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "configured")
else:
    # Development fallback (SQLite)
    DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    os.makedirs(DB_DIR, exist_ok=True)
    DB_PATH = os.path.join(DB_DIR, "jobs.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    logger.info("Using SQLite: %s", DB_PATH)

# ──────────────────────────────────────────────
# Session factory
# ──────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData()

# ──────────────────────────────────────────────
# Jobs table schema
# ──────────────────────────────────────────────
jobs_table = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("job_title", String(500)),
    Column("company_name", String(300)),
    Column("company_name_raw", String(300)),
    Column("city", String(200)),
    Column("location", String(300)),
    Column("salary", String(200)),
    Column("salary_currency", String(10)),
    Column("salary_usd_numeric", Float),
    Column("seniority_level", String(100)),
    Column("experience_required", String(100)),
    Column("employment_type", String(50)),
    Column("remote_type", String(50)),
    Column("industry", String(200)),
    Column("education_required", String(100)),
    Column("has_equity", Integer),
    Column("has_bonus", Integer),
    Column("has_remote_benefits", Integer),
    Column("skills_required", Text),
    Column("job_description", Text),
    Column("job_link", String(1000)),
    Column("job_id", String(100)),
    Column("source_website", String(50)),
    Column("dedup_key", String(20), unique=True, index=True),
    Column("company_tier_score", Integer),
    Column("cost_of_living_index", Integer),
    Column("date_posted_raw", String(100)),
    Column("applicant_count", Integer),
    Column("currency", String(10)),
    Column("scraped_at", DateTime, default=datetime.utcnow),
)


def get_db():
    """FastAPI dependency: yield a database session, auto-close on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_engine():
    """Return the active engine for use outside FastAPI (scraper, training)."""
    return engine


def init_db():
    """Create all tables if they don't exist. Safe to call multiple times."""
    metadata.create_all(engine)
    logger.info("Database tables ensured.")
