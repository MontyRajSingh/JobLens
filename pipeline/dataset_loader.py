"""
dataset_loader.py — Load and map the Kaggle job descriptions dataset
to the pipeline schema.

class KaggleDatasetLoader:
    load(csv_path) → pd.DataFrame  (same columns as scraper output)
    validate(df)   → print fill rates and warnings

The returned DataFrame is fully compatible with DataCleaner().clean()
and FeatureEngineer().fit_transform(), no changes needed downstream.
"""

import os
import re
import sys
import hashlib
import logging
from typing import Optional

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.text_utils import infer_seniority, extract_skills, get_company_tier_score, extract_experience

logger = logging.getLogger(__name__)

# Only keep jobs from countries with reliable USD-comparable salaries
KEEP_COUNTRIES = {
    "United States", "United Kingdom", "Canada",
    "Australia", "Germany", "Singapore", "Ireland",
    "Netherlands", "Switzerland", "Sweden", "Denmark",
    "New Zealand", "Hong Kong", "Japan",
}

# ──────────────────────────────────────────────
# Lookup tables
# ──────────────────────────────────────────────
QUALIFICATIONS_MAP = {
    "M.Tech":       "Master's",
    "MBA":          "Master's",
    "MSc":          "Master's",
    "M.Sc":         "Master's",
    "B.Tech":       "Bachelor's",
    "BCA":          "Bachelor's",
    "BBA":          "Bachelor's",
    "BSc":          "Bachelor's",
    "B.Sc":         "Bachelor's",
    "PhD":          "PhD",
    "Ph.D":         "PhD",
    "High School":  "High School",
}

WORK_TYPE_MAP = {
    "Full-Time":  ("Full-time",   "On-site"),
    "Part-Time":  ("Part-time",   "On-site"),
    "Contract":   ("Contract",    "On-site"),
    "Intern":     ("Internship",  "On-site"),
    "Temporary":  ("Contract",    "On-site"),
    "Remote":     ("Full-time",   "Remote"),
}

COUNTRY_COL_INDEX = {
    "United States":     95,
    "US":                95,
    "United Kingdom":    88,
    "UK":                88,
    "Canada":            78,
    "Australia":         85,
    "Germany":           70,
    "Singapore":         88,
    "India":             30,
    "Isle of Man":       85,
    "Turkmenistan":      35,
    "Japan":             75,
    "France":            72,
    "Netherlands":       73,
    "Ireland":           80,
    "Switzerland":       95,
    "Sweden":            70,
    "Norway":            75,
    "Denmark":           72,
    "New Zealand":       78,
    "South Korea":       65,
    "Israel":            75,
    "UAE":               80,
    "China":             45,
    "Brazil":            35,
    "Mexico":            30,
}

# Equity/bonus keywords
EQUITY_KEYWORDS = re.compile(r"stock|equity|rsu|esop|shares|options", re.IGNORECASE)
BONUS_KEYWORDS = re.compile(r"bonus|incentive|commission", re.IGNORECASE)

# Experience regex: "5 to 15 Years"
EXP_REGEX = re.compile(r"(\d+)\s+to\s+(\d+)\s+[Yy]ears?")

# Salary regex: "$59K-$99K"
SALARY_REGEX = re.compile(r"\$(\d+)K\s*-\s*\$(\d+)K", re.IGNORECASE)


class KaggleDatasetLoader:
    """Load and map the Kaggle job descriptions dataset to pipeline schema."""

    def load(self, csv_path: str) -> pd.DataFrame:
        """
        Load Kaggle CSV and map columns to match the scraper output schema.

        Args:
            csv_path: Path to the Kaggle CSV file.

        Returns:
            pd.DataFrame with columns matching scraper output, ready for
            DataCleaner().clean() and FeatureEngineer().fit_transform().
        """
        logger.info("Loading Kaggle dataset from %s", csv_path)
        df = pd.read_csv(csv_path, low_memory=False)
        logger.info("Loaded %d rows, %d columns", len(df), len(df.columns))

        # ── 1. Direct column renames ──
        out = pd.DataFrame()
        out["job_id"] = df["Job Id"].astype(str)
        out["job_title"] = df["Job Title"]
        out["role"] = df["Role"]
        out["company_name"] = df["Company"]
        out["location"] = df["location"]
        out["city"] = df["location"]                     # use location as city
        out["country"] = df["Country"]
        out["latitude"] = df["latitude"]
        out["longitude"] = df["longitude"]
        out["company_size"] = pd.to_numeric(df["Company Size"], errors="coerce")
        out["date_posted_raw"] = df["Job Posting Date"]
        out["job_description"] = df["Job Description"]
        out["skills_raw"] = df["skills"]
        out["benefits_raw"] = df["Benefits"]
        out["responsibilities"] = df["Responsibilities"]
        out["gender_preference"] = df["Preference"]
        out["company_profile_raw"] = df["Company Profile"]
        out["contact_person"] = df["Contact Person"]
        out["contact"] = df["Contact"]

        # ── FILTER: Keep only high-salary countries ──
        before_filter = len(out)
        out = out[out["country"].isin(KEEP_COUNTRIES)].copy()
        dropped = before_filter - len(out)
        logger.info("Kept %d rows from high-salary countries (dropped %d rows)", len(out), dropped)
        print(f"   Filtered countries: kept {len(out):,} rows (dropped {dropped:,})")

        # Re-index df to match out after filtering
        df = df.loc[out.index]

        # ── 2. Salary parsing: "$59K-$99K" → midpoint ──
        logger.info("Parsing salary ranges...")
        salary_data = df["Salary Range"].apply(self._parse_salary)
        out["salary_usd_numeric"] = salary_data.apply(lambda x: x[0])
        out["salary_currency"] = "USD"
        out["currency"] = "USD"

        # ── 2b. Adjust salary by cost_of_living_index for geographic variation ──
        out["cost_of_living_index"] = out["country"].apply(
            lambda c: COUNTRY_COL_INDEX.get(str(c).strip(), 70) if pd.notna(c) else 70
        )
        out["salary_usd_numeric"] = out["salary_usd_numeric"] * (out["cost_of_living_index"] / 90)
        out["salary"] = out["salary_usd_numeric"].apply(
            lambda v: f"${v:,.0f} USD/yr" if pd.notna(v) else None
        )

        # Drop salary outliers
        out = out[
            (out["salary_usd_numeric"].isna()) |
            ((out["salary_usd_numeric"] >= 25000) & (out["salary_usd_numeric"] <= 400000))
        ].copy()

        # ── 3. Experience parsing ──
        logger.info("Parsing experience...")
        out["experience_required"] = df.loc[out.index, "Experience"].apply(self._parse_experience)

        # ── 4. Qualifications → education_required ──
        out["education_required"] = df.loc[out.index, "Qualifications"].map(QUALIFICATIONS_MAP)

        # ── 5. Work Type → employment_type + remote_type ──
        work_mapped = df.loc[out.index, "Work Type"].apply(
            lambda w: WORK_TYPE_MAP.get(str(w).strip(), ("Full-time", "On-site"))
        )
        out["employment_type"] = work_mapped.apply(lambda x: x[0])
        out["remote_type"] = work_mapped.apply(lambda x: x[1])

        # ── 6. Seniority from title ──
        logger.info("Deriving seniority levels...")
        out["seniority_level"] = out["job_title"].apply(
            lambda t: infer_seniority(t) if pd.notna(t) else None
        )

        # ── 7. Company Tier score ──
        out["company_tier_score"] = out["company_name"].apply(
            lambda c: get_company_tier_score(c) if pd.notna(c) else 1
        )

        # ── 8. Equity / Bonus from Benefits ──
        benefits_text = df.loc[out.index, "Benefits"].fillna("")
        desc_text = out["job_description"].fillna("")
        combined_text = benefits_text.astype(str) + " " + desc_text.astype(str)
        out["has_equity"] = combined_text.apply(
            lambda t: 1 if EQUITY_KEYWORDS.search(t) else 0
        )
        out["has_bonus"] = combined_text.apply(
            lambda t: 1 if BONUS_KEYWORDS.search(t) else 0
        )

        # ── 9. Cost of living index (already computed in step 2b) ──
        # (cost_of_living_index was set during salary adjustment)

        # ── 10. Source website ──
        portal = df.loc[out.index, "Job Portal"].fillna("Kaggle Dataset")
        out["source_website"] = portal.apply(
            lambda p: p.strip() if pd.notna(p) and str(p).strip() else "Kaggle Dataset"
        )

        # ── 11. Skills extraction (map to SKILL_LIST) ──
        logger.info("Extracting skills...")
        out["skills_required"] = out["skills_raw"].apply(
            lambda s: extract_skills(s) if pd.notna(s) else None
        )

        # ── 12. Company size category ──
        out["company_size_category"] = out["company_size"].apply(self._size_category)

        # ── 13. Dedup key ──
        out["dedup_key"] = out.apply(
            lambda r: hashlib.md5(
                f"{str(r.get('company_name','')).lower()}"
                f"{str(r.get('job_title','')).lower()}"
                f"{str(r.get('location','')).lower()}".encode()
            ).hexdigest()[:12],
            axis=1,
        )

        # ── 14. Fill remaining pipeline columns with defaults ──
        for col in ["job_link", "linkedin_seniority_raw", "job_type_raw",
                     "salary_raw", "experience_raw", "company_industry",
                     "industry"]:
            if col not in out.columns:
                out[col] = None

        # ── 15. Drop invalid rows ──
        before = len(out)
        out = out.dropna(subset=["job_title"]).copy()
        out = out[out["job_title"].str.len() >= 3].copy()
        logger.info("Dropped %d invalid rows → %d remaining", before - len(out), len(out))

        # ── 16. Summary stats ──
        sal_fill = out["salary_usd_numeric"].notna().mean() * 100
        countries = out["country"].nunique()
        titles = out["job_title"].nunique()
        top_roles = out["role"].value_counts().head(5).to_dict() if "role" in out.columns else {}

        logger.info("Kaggle dataset: %d rows loaded", len(out))
        logger.info("Rows with salary: %d (%.1f%%)", out["salary_usd_numeric"].notna().sum(), sal_fill)
        logger.info("Countries: %d unique", countries)
        logger.info("Job titles: %d unique", titles)
        logger.info("Top 5 roles: %s", top_roles)

        print(f"\n📊 Kaggle dataset: {len(out):,} rows loaded")
        print(f"   Rows with salary: {out['salary_usd_numeric'].notna().sum():,} ({sal_fill:.1f}%)")
        print(f"   Countries: {countries} unique")
        print(f"   Job titles: {titles} unique")
        if top_roles:
            print(f"   Top 5 roles: {', '.join(list(top_roles.keys())[:5])}")

        out = out.reset_index(drop=True)
        return out

    def validate(self, df: pd.DataFrame) -> None:
        """Print column fill rates and warn on low salary fill."""
        important = [
            "job_title", "company_name", "city", "salary_usd_numeric",
            "experience_required", "seniority_level", "education_required",
            "employment_type", "remote_type", "skills_required",
            "source_website", "has_equity", "has_bonus", "company_tier_score",
        ]
        print(f"\n{'Column':<25} {'Fill Rate':>10}  {'Count':>8}")
        print("-" * 50)
        for col in important:
            if col in df.columns:
                fill = df[col].notna().mean() * 100
                count = df[col].notna().sum()
                status = "✅" if fill > 80 else "⚠️" if fill > 50 else "❌"
                print(f" {status} {col:<23} {fill:>8.1f}%  {count:>8,}")
            else:
                print(f" ❌ {col:<23}  MISSING")

        sal_fill = df["salary_usd_numeric"].notna().mean() * 100 if "salary_usd_numeric" in df.columns else 0
        if sal_fill < 80:
            logger.warning("⚠️  Salary fill rate is %.1f%% (expected ≥80%%)", sal_fill)

        # Check for REQUIRED_COLUMNS
        try:
            from scrapers.base_scraper import BaseScraper
            missing = [c for c in BaseScraper.REQUIRED_COLUMNS if c not in df.columns]
            if missing:
                logger.warning("⚠️  Missing REQUIRED_COLUMNS: %s", missing)
                print(f"\n⚠️  Missing scraper columns: {missing}")
        except ImportError:
            pass

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────
    @staticmethod
    def _parse_salary(salary_str) -> tuple:
        """Parse "$59K-$99K" → (79000.0, "$79,000 USD/yr")."""
        if pd.isna(salary_str):
            return (None, None)

        m = SALARY_REGEX.search(str(salary_str))
        if not m:
            return (None, None)

        low = int(m.group(1)) * 1000
        high = int(m.group(2)) * 1000
        mid = (low + high) / 2
        formatted = f"${mid:,.0f} USD/yr"
        return (mid, formatted)

    @staticmethod
    def _parse_experience(exp_str) -> Optional[str]:
        """Parse "5 to 15 Years" → "5-15 years"."""
        if pd.isna(exp_str):
            return None

        m = EXP_REGEX.search(str(exp_str))
        if m:
            return f"{m.group(1)}-{m.group(2)} years"

        # Fallback: try extract_experience on raw text
        return extract_experience(str(exp_str))

    @staticmethod
    def _size_category(size) -> Optional[str]:
        """Map company size int to category."""
        if pd.isna(size):
            return None
        size = int(size)
        if size < 50:
            return "Startup"
        if size <= 200:
            return "Small"
        if size <= 1000:
            return "Medium"
        return "Large"
