"""
data_cleaner.py — DataCleaner class for post-scrape data cleaning.

Performs a 10-step cleaning pipeline on raw scraped job data:
drop invalid rows, deduplicate, clean titles/companies, extract numeric salary,
fix missing seniority/employment/remote/industry/education fields,
re-scan for equity/bonus, normalise source names, and print quality report.

All utilities imported from utils/; all constants from config.py.
"""

import re
import hashlib
import logging
from typing import Optional

import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import SENIORITY_FROM_LINKEDIN
from utils.text_utils import (
    clean_text, parse_linkedin_metadata, infer_seniority,
    extract_experience, seniority_to_experience, extract_skills,
    infer_skills_from_title,
)
from utils.salary_utils import parse_salary_numeric_usd, salary_text_to_number

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Multi-step data cleaning pipeline for scraped job records.

    Usage:
        cleaner = DataCleaner()
        df_clean = cleaner.clean(df_raw)
    """

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run the full 10-step cleaning pipeline.

        Args:
            df: Raw scraped DataFrame (expects columns from BaseScraper.REQUIRED_COLUMNS).

        Returns:
            Cleaned DataFrame with additional columns (salary_usd_numeric, company_name_raw).
        """
        logger.info("DataCleaner: starting with %d rows", len(df))
        df = df.copy()

        df = self._step1_drop_invalid(df)
        df = self._step1b_drop_city_mismatch(df)
        df = self._step2_deduplicate(df)
        df = self._step3_clean_title(df)
        df = self._step4_clean_company(df)
        df = self._step5_extract_salary_numeric(df)
        df = self._step5b_validate_salary_range(df)
        df = self._step6_fix_seniority(df)
        df = self._step6b_backfill_skills(df)
        df = self._step7_fix_metadata(df)
        df = self._step8_fix_equity_bonus(df)
        df = self._step9_normalise_source(df)
        self._step10_quality_report(df)


        logger.info("DataCleaner: finished with %d rows", len(df))
        return df

    # ──────────────────────────────────────────────
    # Step 1: Drop invalid rows
    # ──────────────────────────────────────────────

    def _step1_drop_invalid(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop rows where job_title is None or length < 3."""
        before = len(df)
        df = df.dropna(subset=["job_title"])
        df = df[df["job_title"].astype(str).str.len() >= 3]
        logger.info("Step 1 — Drop invalid: %d → %d rows", before, len(df))
        return df.reset_index(drop=True)

    # ──────────────────────────────────────────────
    # Step 1b: Drop city-location mismatches
    # ──────────────────────────────────────────────

    def _step1b_drop_city_mismatch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop rows where job's actual location is in a different country than search city."""
        before = len(df)

        def get_country(loc_str: str) -> Optional[str]:
            if not loc_str:
                return None
            loc_lower = str(loc_str).lower()
            if "india" in loc_lower or any(city in loc_lower for city in ["bengaluru", "bangalore", "gurugram", "gurgaon", "hyderabad", "pune", "mumbai", "noida"]):
                return "India"
            if "united kingdom" in loc_lower or "england" in loc_lower or "london" in loc_lower or " uk" in loc_lower or loc_lower == "uk":
                return "UK"
            if "canada" in loc_lower or "toronto" in loc_lower or "ontario" in loc_lower or "vancouver" in loc_lower:
                return "Canada"
            if "australia" in loc_lower or "sydney" in loc_lower or "melbourne" in loc_lower or "nsw" in loc_lower:
                return "Australia"
            if "singapore" in loc_lower:
                return "Singapore"
            if "united states" in loc_lower or "usa" in loc_lower or "america" in loc_lower or any(state in loc_lower for state in [", ny", ", ca", ", wa", ", tx", ", il", "new york", "california", "washington", "texas", "illinois", "san francisco", "seattle", "austin", "chicago"]):
                return "USA"
            return None

        def is_mismatch(row):
            city = row.get("city")
            location = row.get("location")
            if not city or not location:
                return False
            city_country = get_country(city)
            loc_country = get_country(location)
            if city_country and loc_country and city_country != loc_country:
                return True
            return False

        mismatched = df.apply(is_mismatch, axis=1)
        df = df[~mismatched]
        dropped = before - len(df)
        logger.info("Step 1b — Drop city mismatch: dropped %d rows", dropped)
        return df.reset_index(drop=True)


    # ──────────────────────────────────────────────
    # Step 2: Deduplicate
    # ──────────────────────────────────────────────

    def _step2_deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate missing dedup_key, then deduplicate keeping rows with salary."""
        before = len(df)

        # Generate dedup_key where missing
        mask = df["dedup_key"].isna() | (df["dedup_key"] == "")
        for idx in df[mask].index:
            company = str(df.at[idx, "company_name"] or "").lower()
            title = str(df.at[idx, "job_title"] or "").lower()
            city = str(df.at[idx, "city"] or "").lower()
            df.at[idx, "dedup_key"] = hashlib.md5(
                f"{company}{title}{city}".encode()
            ).hexdigest()[:12]

        # Sort so rows with salary come first
        df["_has_salary"] = df["salary"].notna().astype(int)
        df = df.sort_values("_has_salary", ascending=False)
        df = df.drop_duplicates(subset=["dedup_key"], keep="first")
        df = df.drop(columns=["_has_salary"])

        logger.info("Step 2 — Dedup: %d → %d rows (-%d dupes)", before, len(df), before - len(df))
        return df.reset_index(drop=True)

    # ──────────────────────────────────────────────
    # Step 3: Clean job_title
    # ──────────────────────────────────────────────

    def _step3_clean_title(self, df: pd.DataFrame) -> pd.DataFrame:
        """Title-case, strip trailing digit IDs, strip leading/trailing punctuation."""
        def _clean_title(title):
            if not title or pd.isna(title):
                return title
            t = str(title).strip()
            # Strip trailing 7+ digit IDs (e.g. job ref numbers)
            t = re.sub(r"\s*\d{7,}\s*$", "", t)
            # Strip leading/trailing punctuation (except parentheses)
            t = re.sub(r"^[\-–—:,.\s]+", "", t)
            t = re.sub(r"[\-–—:,.\s]+$", "", t)
            # Title case
            t = t.title()
            return t.strip() if t.strip() else title

        df["job_title"] = df["job_title"].apply(_clean_title)
        logger.info("Step 3 — Clean titles: done")
        return df

    # ──────────────────────────────────────────────
    # Step 4: Clean company_name
    # ──────────────────────────────────────────────

    def _step4_clean_company(self, df: pd.DataFrame) -> pd.DataFrame:
        """Save original to company_name_raw; strip legal suffixes."""
        df["company_name_raw"] = df["company_name"]

        suffixes = [
            r",?\s*Inc\.?",
            r",?\s*Ltd\.?",
            r",?\s*LLC\.?",
            r",?\s*Corp\.?",
            r",?\s*Limited",
            r",?\s*PLC\.?",
            r",?\s*GmbH\.?",
            r",?\s*Pvt\.?\s*Ltd\.?",
            r",?\s*Private\s+Limited",
        ]
        pattern = "|".join(f"({s})$" for s in suffixes)

        def _clean_company(name):
            if not name or pd.isna(name):
                return name
            cleaned = re.sub(pattern, "", str(name), flags=re.IGNORECASE).strip()
            return cleaned if cleaned else name

        df["company_name"] = df["company_name"].apply(_clean_company)
        logger.info("Step 4 — Clean companies: done")
        return df

    # ──────────────────────────────────────────────
    # Step 5: Extract salary_usd_numeric
    # ──────────────────────────────────────────────

    def _step5_extract_salary_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract numeric USD salary using the shared salary parser."""
        def _coerce_existing(value):
            if value is None or pd.isna(value):
                return np.nan
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = salary_text_to_number(str(value))
            if numeric is None or numeric < 5_000 or numeric > 5_000_000:
                return np.nan
            return round(float(numeric), 2)

        def _parse_row(row):
            existing = _coerce_existing(row.get("salary_usd_numeric"))
            if pd.notna(existing):
                return existing

            salary_str = row.get("salary")
            if not salary_str or pd.isna(salary_str):
                return np.nan

            numeric = parse_salary_numeric_usd(str(salary_str), usd_rate=1.0)
            if numeric is None:
                return np.nan
            return round(float(numeric), 2)

        df["salary_usd_numeric"] = df.apply(_parse_row, axis=1)
        filled = df["salary_usd_numeric"].notna().sum()
        logger.info("Step 5 — Salary numeric: %d/%d rows have numeric salary", filled, len(df))
        return df

    # ──────────────────────────────────────────────
    # Step 5b: Validate salary range (ceilings)
    # ──────────────────────────────────────────────

    def _step5b_validate_salary_range(self, df: pd.DataFrame) -> pd.DataFrame:
        """Null out unreasonable salary values above per-city ceilings for non-FAANG companies."""
        nulled = 0

        def get_city_ceiling(city_str: str) -> float:
            if not city_str:
                return 500_000.0
            city_lower = str(city_str).lower()
            if any(c in city_lower for c in ["bengaluru", "gurugram", "hyderabad", "pune", "india"]):
                return 100_000.0
            if any(c in city_lower for c in ["london", "uk", "sydney", "australia", "singapore", "toronto", "canada"]):
                return 400_000.0
            return 500_000.0

        for idx in df.index:
            salary = df.at[idx, "salary_usd_numeric"]
            if pd.isna(salary) or salary is None:
                continue

            # Exclude FAANG companies
            is_faang_val = False
            if "is_faang" in df.columns:
                val = df.at[idx, "is_faang"]
                is_faang_val = bool(val) and val not in (0, "0", "False", False)

            if not is_faang_val:
                city = df.at[idx, "city"]
                ceiling = get_city_ceiling(city)
                if salary > ceiling:
                    df.at[idx, "salary_usd_numeric"] = np.nan
                    df.at[idx, "salary"] = np.nan
                    nulled += 1

        logger.info("Step 5b — Salary ceiling validation: nulled %d suspect salaries", nulled)
        return df


    # ──────────────────────────────────────────────
    # Step 6: Fix seniority_level
    # ──────────────────────────────────────────────

    def _step6_fix_seniority(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing seniority from description metadata or title inference."""
        fixed = 0
        for idx in df.index:
            if pd.notna(df.at[idx, "seniority_level"]) and df.at[idx, "seniority_level"]:
                continue

            seniority = None

            # Priority 1: parse from job_description
            desc = df.at[idx, "job_description"] if pd.notna(df.at[idx, "job_description"]) else ""
            if desc:
                meta = parse_linkedin_metadata(desc)
                raw = meta.get("seniority_raw")
                if raw and raw.strip().lower() in SENIORITY_FROM_LINKEDIN:
                    seniority = SENIORITY_FROM_LINKEDIN[raw.strip().lower()]

            # Priority 2: infer from title
            if not seniority:
                title = df.at[idx, "job_title"] if pd.notna(df.at[idx, "job_title"]) else ""
                seniority = infer_seniority(title)

            # Default
            if not seniority:
                seniority = "Mid-Level (2-5 years)"

            df.at[idx, "seniority_level"] = seniority
            fixed += 1

        logger.info("Step 6 — Fix seniority: filled %d rows", fixed)
        return df

    # ──────────────────────────────────────────────
    # Step 6b: Backfill skills_required
    # ──────────────────────────────────────────────

    def _step6b_backfill_skills(self, df: pd.DataFrame) -> pd.DataFrame:
        """Backfill missing skills_required from job description or title inference."""
        filled = 0
        for idx in df.index:
            if pd.notna(df.at[idx, "skills_required"]) and df.at[idx, "skills_required"] and str(df.at[idx, "skills_required"]).strip():
                continue

            # Priority 1: Extract from description
            desc = df.at[idx, "job_description"] if pd.notna(df.at[idx, "job_description"]) else ""
            if desc:
                skills = extract_skills(desc)
                if skills:
                    df.at[idx, "skills_required"] = skills
                    filled += 1
                    continue

            # Priority 2: Infer from title
            title = df.at[idx, "job_title"] if pd.notna(df.at[idx, "job_title"]) else ""
            inferred = infer_skills_from_title(title)
            if inferred:
                df.at[idx, "skills_required"] = inferred
                filled += 1

        logger.info("Step 6b — Backfill skills: filled/inferred skills for %d rows", filled)
        return df


    # ──────────────────────────────────────────────
    # Step 7: Fix metadata fields
    # ──────────────────────────────────────────────

    def _step7_fix_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing employment_type, remote_type, industry, education_required."""
        if "has_remote_benefits" in df.columns:
            df["has_remote_benefits"] = df["has_remote_benefits"].astype(object)

        for idx in df.index:
            desc = df.at[idx, "job_description"] if pd.notna(df.at[idx, "job_description"]) else ""
            meta = parse_linkedin_metadata(desc) if desc else {}


            # Employment type
            if pd.isna(df.at[idx, "employment_type"]) or not df.at[idx, "employment_type"]:
                df.at[idx, "employment_type"] = meta.get("employment_type") or "Full-time"

            # Remote type
            if pd.isna(df.at[idx, "remote_type"]) or not df.at[idx, "remote_type"]:
                df.at[idx, "remote_type"] = meta.get("remote_type") or "On-site"

            # Override remote_type if "remote" is in title
            title = str(df.at[idx, "job_title"]) if pd.notna(df.at[idx, "job_title"]) else ""
            if "remote" in title.lower() and df.at[idx, "remote_type"] == "On-site":
                df.at[idx, "remote_type"] = "Remote"
                if "has_remote_benefits" in df.columns:
                    df.at[idx, "has_remote_benefits"] = True


            # Industry
            if pd.isna(df.at[idx, "industry"]) or not df.at[idx, "industry"]:
                industry = meta.get("industry")
                if industry:
                    df.at[idx, "industry"] = industry

            # Education
            if pd.isna(df.at[idx, "education_required"]) or not df.at[idx, "education_required"]:
                edu = meta.get("education_required")
                if edu:
                    df.at[idx, "education_required"] = edu

        logger.info("Step 7 — Fix metadata: done")
        return df

    # ──────────────────────────────────────────────
    # Step 8: Fix equity/bonus flags
    # ──────────────────────────────────────────────

    def _step8_fix_equity_bonus(self, df: pd.DataFrame) -> pd.DataFrame:
        """Re-scan job_description for equity/bonus keywords where flags are 0."""
        equity_pattern = re.compile(
            r"\b(equity|rsu|restricted stock|stock option|vesting|esop)\b",
            re.IGNORECASE,
        )
        bonus_pattern = re.compile(
            r"\b(bonus|incentive|commission|performance pay|signing bonus)\b",
            re.IGNORECASE,
        )

        equity_fixed = 0
        bonus_fixed = 0

        for idx in df.index:
            desc = str(df.at[idx, "job_description"]) if pd.notna(df.at[idx, "job_description"]) else ""

            if not df.at[idx, "has_equity"] or df.at[idx, "has_equity"] == 0:
                if equity_pattern.search(desc):
                    df.at[idx, "has_equity"] = 1
                    equity_fixed += 1

            if not df.at[idx, "has_bonus"] or df.at[idx, "has_bonus"] == 0:
                if bonus_pattern.search(desc):
                    df.at[idx, "has_bonus"] = 1
                    bonus_fixed += 1

        logger.info("Step 8 — Equity/bonus: fixed %d equity, %d bonus flags", equity_fixed, bonus_fixed)
        return df

    # ──────────────────────────────────────────────
    # Step 9: Normalise source_website
    # ──────────────────────────────────────────────

    def _step9_normalise_source(self, df: pd.DataFrame) -> pd.DataFrame:
        """Title-case source_website values."""
        df["source_website"] = df["source_website"].apply(
            lambda x: str(x).strip().title() if pd.notna(x) else x
        )
        logger.info("Step 9 — Normalise sources: done")
        return df

    # ──────────────────────────────────────────────
    # Step 10: Quality report
    # ──────────────────────────────────────────────

    def _step10_quality_report(self, df: pd.DataFrame) -> None:
        """Print per-column fill rate with terminal bar chart."""
        total = len(df)
        if total == 0:
            print("⚠️  No rows to report on.")
            return

        print(f"\n{'='*70}")
        print(f" 🧹 POST-CLEANING QUALITY REPORT — {total} records")
        print(f"{'='*70}")
        print(f"{'Column':<30} {'Fill':>6} {'Rate':>7}  {'Bar'}")
        print(f"{'-'*30} {'-'*6} {'-'*7}  {'-'*25}")

        for col in df.columns:
            filled = df[col].notna().sum()
            rate = filled / total * 100
            bar_len = int(rate / 4)
            bar = "█" * bar_len + "░" * (25 - bar_len)
            indicator = "✅" if rate > 70 else "⚠️" if rate > 30 else "❌"
            print(f"{col:<30} {filled:>6} {rate:>6.1f}%  {bar} {indicator}")

        print(f"{'='*70}\n")
