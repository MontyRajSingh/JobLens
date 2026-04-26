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
    Uses UPSERT (on conflict do nothing) to merge data safely.
    """
    if not os.path.exists(csv_path):
        logger.warning("CSV not found: %s — skipping DB load", csv_path)
        return 0

    init_db()
    
    # Read CSV
    df = pd.read_csv(csv_path)
    logger.info("Read %d rows from CSV", len(df))

    if df.empty:
        logger.warning("CSV is empty — nothing to load")
        return 0

    # Convert to list of dicts for save_jobs_to_db
    jobs = df.to_dict(orient="records")
    return save_jobs_to_db(jobs)


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
