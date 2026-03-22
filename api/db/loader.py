"""
loader.py — Load cleaned job CSV data into the database.

Creates the jobs table, loads data from CSV, and builds indexes
for common query patterns. Supports reload when CSV is newer than DB.
"""

import os
import logging

import pandas as pd
from sqlalchemy import text, inspect

from api.db.database import engine, metadata, jobs_table

logger = logging.getLogger(__name__)


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
    should_reload = True
    db_path = None

    db_url = str(engine.url)
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        if os.path.exists(db_path):
            csv_mtime = os.path.getmtime(csv_path)
            db_mtime = os.path.getmtime(db_path)
            if db_mtime > csv_mtime:
                # Check if table has data
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

    # Create indexes
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
