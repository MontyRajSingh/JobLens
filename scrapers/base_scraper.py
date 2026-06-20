"""
scrapers/base_scraper.py
------------------------
Abstract base class for all job scrapers.

Enforces a fixed output schema (REQUIRED_COLUMNS) that every scraper must
return. Provides validation helpers to normalise and validate individual
job records and batches.

All scraper subclasses must:
  1. Inherit from BaseScraper
  2. Implement the scrape() method
  3. Return dicts with REQUIRED_COLUMNS keys
  4. Call validate_batch() before returning results
"""

from abc import ABC, abstractmethod
from typing import Dict, List
import logging


class BaseScraper(ABC):
    """
    Abstract base class for job-board scrapers.

    Subclasses must implement the `scrape()` method and return a list of dicts
    conforming to REQUIRED_COLUMNS.
    """

    REQUIRED_COLUMNS = [
        "job_title",
        "company_name",
        "city",
        "location",
        "salary",
        "salary_currency",
        "seniority_level",
        "experience_required",
        "employment_type",
        "remote_type",
        "industry",
        "education_required",
        "has_equity",
        "has_bonus",
        "has_remote_benefits",
        "skills_required",
        "job_description",
        "job_link",
        "job_id",
        "source_website",
        "dedup_key",
        "is_faang",
        "cost_of_living_index",
        "date_posted_raw",
        "applicant_count",
        "currency",
    ]

    def __init__(self):
        # Named logger per subclass so logs show e.g. "scrapers.linkedin_scraper"
        # instead of "scrapers.base_scraper" for every message
        self.logger = logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

    @abstractmethod
    def scrape(
        self,
        keyword: str,
        location: str,
        currency: str,
        usd_rate: float,
        max_jobs: int,
    ) -> List[Dict]:
        """
        Scrape job listings from the source.

        Args:
            keyword:   Job search keyword e.g. "data scientist"
            location:  Location string for the search
            currency:  Local currency code e.g. "USD", "GBP"
            usd_rate:  Multiplier to convert local currency to USD
            max_jobs:  Maximum number of jobs to collect

        Returns:
            List of job dicts with all REQUIRED_COLUMNS keys present.
        """
        pass

    def validate_job_record(self, job: Dict) -> Dict:
        """
        Ensure a job dict has all REQUIRED_COLUMNS.

        Missing columns are filled with None. Extra columns are kept as-is.

        Args:
            job: Raw job dictionary from a scraper.

        Returns:
            Normalised job dictionary with all required keys present.
        """
        for col in self.REQUIRED_COLUMNS:
            if col not in job:
                job[col] = None
        return job

    # Fields shown in the terminal report
    REPORT_FIELDS = [
        "job_title", "company_name", "location", "salary",
        "seniority_level", "employment_type", "remote_type",
        "skills_required", "experience_required", "job_link", "date_posted_raw",
    ]

    def validate_batch(self, jobs: List[Dict]) -> List[Dict]:
        """
        Validate a batch, deduplicate by dedup_key, and print a terminal report.
        """
        # Validate + filter missing titles
        validated = []
        seen_dedup: set = set()
        for job in jobs:
            job = self.validate_job_record(job)
            if not job.get("job_title"):
                self.logger.warning("Dropping job with missing title: %s", job.get("job_link"))
                continue
            # Within-batch dedup
            dk = job.get("dedup_key")
            if dk and dk in seen_dedup:
                self.logger.debug("Deduplicating: %s @ %s", job.get("job_title"), job.get("company_name"))
                continue
            if dk:
                seen_dedup.add(dk)
            validated.append(job)

        self._print_report(validated)
        return validated

    def _print_report(self, jobs: List[Dict]) -> None:
        """Print a human-readable scrape report to the terminal."""
        source = getattr(self, "SOURCE", self.__class__.__name__)
        total  = len(jobs)

        # Field fill counts
        fill: Dict[str, int] = {f: 0 for f in self.REPORT_FIELDS}
        for job in jobs:
            for f in self.REPORT_FIELDS:
                if job.get(f) is not None:
                    fill[f] += 1

        # ── Header
        print(f"\n{'─'*58}")
        print(f"  📋  {source} — Scrape Report  ({total} jobs)")
        print(f"{'─'*58}")

        if total == 0:
            print("  ⚠️  No jobs collected.\n")
            return

        # ── Per-job summary
        for i, job in enumerate(jobs, 1):
            title   = (job.get("job_title")    or "?")[:45]
            company = (job.get("company_name") or "?")[:30]
            salary  = job.get("salary") or "—"
            print(f"  {i:2}. {title}")
            print(f"      @ {company}  |  {salary}")

        # ── Field coverage table
        print(f"\n  {'Field':<22} {'Filled':>6}  {'%':>5}  Status")
        print(f"  {'─'*50}")
        for field in self.REPORT_FIELDS:
            count = fill[field]
            pct   = (count / total * 100) if total else 0
            icon  = "✅" if pct == 100 else ("⚠️ " if pct > 0 else "❌")
            print(f"  {field:<22} {count:>6}/{total:<4} {pct:>4.0f}%  {icon}")

        # ── Missing fields summary
        missing = [f for f in self.REPORT_FIELDS if fill[f] == 0]
        partial = [f for f in self.REPORT_FIELDS if 0 < fill[f] < total]
        if missing:
            print(f"\n  ❌ Fully missing:  {', '.join(missing)}")
        if partial:
            print(f"  ⚠️  Partially filled: {', '.join(partial)}")
        if not missing and not partial:
            print(f"\n  ✅ All fields fully populated!")
        print(f"{'─'*58}\n")