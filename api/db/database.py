"""
database.py — SQLAlchemy engine and session management.

Dev: SQLite at data/jobs.db (when no DATABASE_URL is set)
Prod: DATABASE_URL env var (PostgreSQL on Railway / Docker).

Provides get_db() dependency for FastAPI route injection
and get_engine() for use by the scraper and training pipelines.
"""

import os
import logging

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, BigInteger, String, Float, Text, DateTime
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
    # Using absolute path to ensure API and Scraper share the same file
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DB_DIR = os.path.join(ROOT_DIR, "data")
    os.makedirs(DB_DIR, exist_ok=True)
    DB_PATH = os.path.join(DB_DIR, "jobs.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    logger.info("Connected to database at: %s", DB_PATH)

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
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_title", Text),
    Column("company_name", Text),
    Column("company_name_raw", Text),
    Column("city", Text),
    Column("location", Text),
    Column("salary", Text),
    Column("salary_currency", Text),
    Column("salary_usd_numeric", Float),
    Column("seniority_level", Text),
    Column("experience_required", Text),
    Column("employment_type", Text),
    Column("remote_type", Text),
    Column("industry", Text),
    Column("education_required", Text),
    Column("has_equity", Float),
    Column("has_bonus", Float),
    Column("has_remote_benefits", Float),
    Column("skills_required", Text),
    Column("job_description", Text),
    Column("job_link", Text),
    Column("job_id", Text),
    Column("source_website", Text),
    Column("dedup_key", Text, unique=True, index=True),
    Column("is_faang", Float),
    Column("cost_of_living_index", Float),
    Column("date_posted_raw", Text),
    Column("applicant_count", Float),
    Column("currency", Text),
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
