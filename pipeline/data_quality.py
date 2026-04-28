"""
data_quality.py — Training data readiness checks.

Keeps scraped-data promotion decisions explicit instead of hidden in the
training command. The thresholds are conservative defaults for an MVP and can
be tightened once the scraper has enough history.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

import pandas as pd


@dataclass
class DataReadinessThresholds:
    min_salary_rows: int = 5_000
    min_salary_coverage_pct: float = 30.0
    min_cities: int = 5
    min_seniority_levels: int = 3
    max_single_source_pct: float = 75.0


def evaluate_training_readiness(
    df: pd.DataFrame,
    thresholds: DataReadinessThresholds | None = None,
) -> Dict[str, Any]:
    """Return scraped-data readiness metrics and pass/fail reasons."""
    thresholds = thresholds or DataReadinessThresholds()
    total_rows = int(len(df))

    salary_col = df.get("salary_usd_numeric")
    salary_rows = int(salary_col.notna().sum()) if salary_col is not None else 0
    salary_coverage_pct = round((salary_rows / total_rows * 100), 2) if total_rows else 0.0

    cities_count = int(df["city"].dropna().nunique()) if "city" in df.columns else 0
    seniority_count = (
        int(df["seniority_level"].dropna().nunique())
        if "seniority_level" in df.columns
        else 0
    )

    top_source_pct = 100.0
    top_source = None
    if total_rows and "source_website" in df.columns:
        source_counts = df["source_website"].fillna("unknown").value_counts()
        if not source_counts.empty:
            top_source = str(source_counts.index[0])
            top_source_pct = round(float(source_counts.iloc[0] / total_rows * 100), 2)

    checks = {
        "salary_rows": salary_rows >= thresholds.min_salary_rows,
        "salary_coverage": salary_coverage_pct >= thresholds.min_salary_coverage_pct,
        "cities": cities_count >= thresholds.min_cities,
        "seniority_levels": seniority_count >= thresholds.min_seniority_levels,
        "source_balance": top_source_pct <= thresholds.max_single_source_pct,
    }

    reasons = []
    if not checks["salary_rows"]:
        reasons.append(
            f"needs at least {thresholds.min_salary_rows:,} salary rows; found {salary_rows:,}"
        )
    if not checks["salary_coverage"]:
        reasons.append(
            f"needs salary coverage >= {thresholds.min_salary_coverage_pct:.0f}%; found {salary_coverage_pct:.1f}%"
        )
    if not checks["cities"]:
        reasons.append(f"needs at least {thresholds.min_cities} cities; found {cities_count}")
    if not checks["seniority_levels"]:
        reasons.append(
            f"needs at least {thresholds.min_seniority_levels} seniority levels; found {seniority_count}"
        )
    if not checks["source_balance"]:
        reasons.append(
            f"single source '{top_source}' dominates {top_source_pct:.1f}% of rows"
        )

    return {
        "ready_for_scraped_only_training": all(checks.values()),
        "total_rows": total_rows,
        "salary_rows": salary_rows,
        "salary_coverage_pct": salary_coverage_pct,
        "cities_count": cities_count,
        "seniority_levels_count": seniority_count,
        "top_source": top_source,
        "top_source_pct": top_source_pct,
        "checks": checks,
        "reasons": reasons,
        "thresholds": asdict(thresholds),
    }
