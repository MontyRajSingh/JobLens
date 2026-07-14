"""
loader.py — Load job data into the database.

Provides two entry points:
  - load_jobs_to_db(csv_path): Bulk-load from a cleaned CSV (used at API startup).
  - save_jobs_to_db(jobs):     Insert a list of job dicts (used by the scraper pipeline).
  - load_training_data():      Load all jobs from DB as a Pandas DataFrame (used by trainer).
"""

import os
import hashlib
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text, inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from api.db.database import engine, metadata, jobs_table, app_meta_table, init_db

logger = logging.getLogger(__name__)

# Columns that exist in the jobs table (excluding auto-generated ones)
TABLE_COLUMNS = [c.name for c in jobs_table.columns if c.name not in ("id", "scraped_at")]


def _to_number(v):
    """Coerce mixed boolean/numeric/string values to float (or None)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and pd.isna(v)) else float(v)
    s = str(v).strip().lower()
    if s in ("true", "yes", "y"):
        return 1.0
    if s in ("false", "no", "n"):
        return 0.0
    if s in ("", "nan", "none", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


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


SEED_FINGERPRINT_KEY = "jobs_master_csv_fingerprint"


def _csv_fingerprint(csv_path: str) -> str:
    """MD5 of the CSV contents — identifies exactly what was last seeded."""
    h = hashlib.md5()
    with open(csv_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_meta(conn, key: str):
    row = conn.execute(
        text("SELECT meta_value FROM app_meta WHERE meta_key = :k"), {"k": key}
    ).fetchone()
    return row[0] if row else None


def _set_meta(conn, key: str, value: str):
    conn.execute(text("DELETE FROM app_meta WHERE meta_key = :k"), {"k": key})
    conn.execute(
        text("INSERT INTO app_meta (meta_key, meta_value) VALUES (:k, :v)"),
        {"k": key, "v": value},
    )


def reseed_jobs_from_csv(csv_path: str) -> int:
    """
    Replace the entire jobs table with cleaned data from a scraped CSV.

    Used at API startup so the deployed app serves the committed scraped
    dataset (jobs_master.csv) instead of any stale/seed data. The CSV is run
    through DataCleaner so salary_usd_numeric is populated and rows are
    deduplicated — Jobs filtering and Insights rely on the numeric salary.

    Skips the expensive clean-and-replace when the DB already holds data
    seeded from a byte-identical CSV (fingerprint stored in app_meta), so
    restarts without a new scrape boot fast.

    Args:
        csv_path: Path to the scraped jobs CSV.

    Returns:
        Number of rows loaded (0 if the CSV is missing/empty or already
        seeded — table left intact).
    """
    if not os.path.exists(csv_path):
        logger.warning("Reseed skipped: CSV not found at %s", csv_path)
        return 0

    init_db()

    fingerprint = _csv_fingerprint(csv_path)
    with engine.connect() as conn:
        try:
            seeded = _get_meta(conn, SEED_FINGERPRINT_KEY)
            jobs_count = conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar() or 0
        except Exception:
            seeded, jobs_count = None, 0
    if seeded == fingerprint and jobs_count > 0:
        logger.info(
            "Reseed skipped: DB already holds %d rows from this CSV (fingerprint %s)",
            jobs_count, fingerprint[:12],
        )
        return 0

    df = pd.read_csv(csv_path, low_memory=False)
    if df.empty:
        logger.warning("Reseed skipped: CSV is empty (%s)", csv_path)
        return 0

    # Clean: parse salary -> salary_usd_numeric, dedup, normalise
    from pipeline.data_cleaner import DataCleaner
    df = DataCleaner().clean(df)
    if df.empty:
        logger.warning("Reseed skipped: no rows after cleaning")
        return 0

    # Coerce Float columns (has_equity/has_bonus/is_faang/etc. arrive as
    # strings like 'True'/'False'/'0') to real numbers so the API's bool()
    # checks and salary filters work correctly.
    from sqlalchemy import Float
    float_cols = [c.name for c in jobs_table.columns if isinstance(c.type, Float)]
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].map(_to_number)

    # Build the output frame: explicit id (for GET /jobs/{id}), the known
    # table columns, and a scraped_at timestamp (used for ordering).
    keep = [c for c in TABLE_COLUMNS if c in df.columns]
    df_out = df[keep].copy().reset_index(drop=True)
    df_out.insert(0, "id", range(1, len(df_out) + 1))
    df_out["scraped_at"] = datetime.utcnow()

    # Build the staging table then swap it in atomically, so requests being
    # served while a background reseed runs never see a dropped/empty jobs
    # table. Works on both SQLite and Postgres (transactional DDL).
    df_out.to_sql("jobs_staging", engine, if_exists="replace", index=False, chunksize=1000)

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS jobs"))
        conn.execute(text("ALTER TABLE jobs_staging RENAME TO jobs"))
        _set_meta(conn, SEED_FINGERPRINT_KEY, fingerprint)

    logger.info("Reseeded jobs table with %d rows from %s", len(df_out), csv_path)
    return len(df_out)


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
