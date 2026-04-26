"""
loader.py — Load job data into the database.

Provides two entry points:
  - load_jobs_to_db(csv_path): Bulk-load from a cleaned CSV (used at API startup).
  - save_jobs_to_db(jobs):     Insert a list of job dicts (used by the scraper pipeline).
  - load_training_data():      Load all jobs from DB as a Pandas DataFrame (used by trainer).
"""

import os
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text, inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from api.db.database import engine, metadata, jobs_table, init_db

logger = logging.getLogger(__name__)

# Columns that exist in the jobs table (excluding auto-generated ones)
TABLE_COLUMNS = [c.name for c in jobs_table.columns if c.name not in ("id", "scraped_at")]


def save_jobs_to_db(jobs: list[dict]) -> int:
    """
    Insert a batch of scraped job dicts into the database.

    Uses INSERT ... ON CONFLICT (dedup_key) DO NOTHING for automatic
    deduplication. Jobs that already exist are silently skipped.

    Args:
        jobs: List of job dicts from the scraper pipeline.

    Returns:
        Number of new rows inserted.
    """
    if not jobs:
        return 0

    init_db()

    # Filter each job dict to only include known table columns
    rows = []
    for job in jobs:
        row = {k: job.get(k) for k in TABLE_COLUMNS if k in job}
        row["scraped_at"] = datetime.utcnow()
        rows.append(row)

    db_url = str(engine.url)
    inserted = 0

    with engine.begin() as conn:
        for row in rows:
            try:
                if db_url.startswith("postgresql"):
                    # PostgreSQL: native upsert
                    stmt = pg_insert(jobs_table).values(**row).on_conflict_do_nothing(
                        index_elements=["dedup_key"]
                    )
                else:
                    # SQLite: native upsert
                    stmt = sqlite_insert(jobs_table).values(**row).on_conflict_do_nothing(
                        index_elements=["dedup_key"]
                    )
                result = conn.execute(stmt)
                if result.rowcount > 0:
                    inserted += 1
            except Exception as e:
                logger.debug("Skipping job (dedup_key=%s): %s", row.get("dedup_key"), e)

    logger.info("Saved %d new jobs to database (%d duplicates skipped)", inserted, len(rows) - inserted)
    return inserted


def load_jobs_to_db(csv_path: str) -> int:
    """
    Load jobs from CSV into the 'jobs' database table.

    Creates indexes on: city, seniority_level, remote_type,
    source_website, salary_usd_numeric for fast filtering.
    Reloads if CSV is newer than DB (for SQLite) or if table is empty.

    Args:
        csv_path: Path to the cleaned jobs CSV file.

    Returns:
        Number of rows loaded.
    """
    if not os.path.exists(csv_path):
        logger.warning("CSV not found: %s — skipping DB load", csv_path)
        return 0

    # Check if reload needed (SQLite only)
    db_url = str(engine.url)
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        if os.path.exists(db_path):
            csv_mtime = os.path.getmtime(csv_path)
            db_mtime = os.path.getmtime(db_path)
            if db_mtime > csv_mtime:
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text("SELECT COUNT(*) FROM jobs"))
                        count = result.scalar()
                        if count and count > 0:
                            logger.info("DB is up-to-date with %d rows, skipping reload", count)
                            return count
                except Exception:
                    pass  # Table might not exist yet

    logger.info("Loading jobs from %s", csv_path)

    # Read CSV
    df = pd.read_csv(csv_path)
    logger.info("Read %d rows from CSV", len(df))

    if df.empty:
        logger.warning("CSV is empty — nothing to load")
        return 0

    # Create table (drop if exists for fresh reload)
    metadata.drop_all(engine, tables=[jobs_table], checkfirst=True)
    metadata.create_all(engine, tables=[jobs_table])

    # Filter columns to match table schema
    table_columns = [c.name for c in jobs_table.columns if c.name != "id"]
    df_columns = [c for c in table_columns if c in df.columns]
    df_load = df[df_columns].copy()

    # Load data
    df_load.to_sql("jobs", engine, if_exists="append", index=False)

    # Create indexes (dedup_key index is already defined in the table schema)
    index_columns = ["city", "seniority_level", "remote_type", "source_website", "salary_usd_numeric"]
    with engine.connect() as conn:
        for col in index_columns:
            try:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_jobs_{col} ON jobs ({col})"))
            except Exception as e:
                logger.debug("Index creation for %s: %s", col, e)
        conn.commit()

    row_count = len(df_load)
    logger.info("Loaded %d jobs into database with indexes", row_count)
    return row_count


def load_training_data() -> pd.DataFrame:
    """
    Load all job records from the database as a Pandas DataFrame.

    Used by the training pipeline as an alternative to reading from CSV.

    Returns:
        DataFrame with all jobs. Empty DataFrame if table doesn't exist.
    """
    init_db()
    try:
        df = pd.read_sql_table("jobs", engine)
        logger.info("Loaded %d rows from database for training", len(df))
        return df
    except Exception as e:
        logger.warning("Failed to load training data from DB: %s", e)
        return pd.DataFrame()
