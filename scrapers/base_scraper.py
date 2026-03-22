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

    def validate_batch(self, jobs: List[Dict]) -> List[Dict]:
        """
        Validate and normalise a batch of job dicts.

        Applies validate_job_record() to every job and filters out records
        with a missing job_title (indicates a failed scrape).

        Args:
            jobs: List of raw job dicts.

        Returns:
            List of normalised, valid job dicts.
        """
        validated = []
        for job in jobs:
            job = self.validate_job_record(job)
            if job.get("job_title"):
                validated.append(job)
            else:
                self.logger.warning(
                    "Dropping job with missing title: %s", job.get("job_link")
                )
        self.logger.info(
            "Batch validation: %d/%d jobs passed", len(validated), len(jobs)
        )
        return validated