"""
validators.py — Data validation utilities for job records and DataFrames.

Provides record-level validation (single job dict) and DataFrame-level
quality reporting (per-column fill rates).
"""

import re
import logging
from typing import Dict, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def validate_job_record(job: Dict) -> Tuple[bool, List[str]]:
    """
    Validate a single job record dictionary.

    Checks:
    - job_title is not None or empty
    - job_link is a valid URL (starts with http)
    - source_website is one of {"LinkedIn", "Indeed", "Glassdoor"}
    - salary_usd_numeric is in a reasonable range if present

    Args:
        job: Dictionary representing a job record.

    Returns:
        Tuple of (is_valid: bool, issues: list of issue descriptions).
    """
    issues = []

    # Job title
    title = job.get("job_title")
    if not title or not str(title).strip():
        issues.append("job_title is missing or empty")

    # Job link
    link = job.get("job_link")
    if not link or not str(link).strip().startswith("http"):
        issues.append(f"job_link is missing or invalid: {link}")

    # Source website
    source = job.get("source_website")
    valid_sources = {"LinkedIn", "Indeed", "Glassdoor"}
    if source not in valid_sources:
        issues.append(f"source_website '{source}' not in {valid_sources}")

    # Salary range check (if present)
    salary_num = job.get("salary_usd_numeric")
    if salary_num is not None:
        try:
            val = float(salary_num)
            if val < 5_000 or val > 5_000_000:
                issues.append(f"salary_usd_numeric {val} is out of range [5000, 5000000]")
        except (ValueError, TypeError):
            issues.append(f"salary_usd_numeric '{salary_num}' is not a valid number")

    is_valid = len(issues) == 0
    if not is_valid:
        logger.warning("Job validation failed: %s", issues)

    return is_valid, issues


def validate_dataframe(df: pd.DataFrame) -> None:
    """
    Print a per-column fill rate report for a jobs DataFrame.

    For each column, prints the number of non-null values, total rows,
    and percentage fill rate. Useful for quality assessment after scraping.

    Args:
        df: pandas DataFrame of job records.
    """
    if df.empty:
        print("⚠️  DataFrame is empty — nothing to validate.")
        return

    total = len(df)
    print(f"\n{'='*60}")
    print(f" DATA QUALITY REPORT — {total} records")
    print(f"{'='*60}")
    print(f"{'Column':<30} {'Filled':>8} {'Total':>8} {'Rate':>8}")
    print(f"{'-'*30} {'-'*8} {'-'*8} {'-'*8}")

    for col in df.columns:
        filled = df[col].notna().sum()
        rate = filled / total * 100
        indicator = "✅" if rate > 70 else "⚠️" if rate > 30 else "❌"
        print(f"{col:<30} {filled:>8} {total:>8} {rate:>7.1f}% {indicator}")

    print(f"{'='*60}\n")
