"""
scrapers/levelsfyi_scraper.py
------------------------------
Levels.fyi salary/job scraper. Inherits BaseScraper.

Extracts job data from the __NEXT_DATA__ JSON embedded in the page HTML.
Levels.fyi is a Next.js app that pre-renders job data in a script tag,
giving us structured salary, company, and location data without needing
to parse the DOM.
"""

import json
import time
import random
import hashlib
from typing import Dict, List
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from utils.driver_utils import setup_driver
from utils.text_utils import clean_text, infer_seniority, is_faang
from config import MAX_JOBS_PER_SEARCH, COL_INDEX


class LevelsFyiScraper(BaseScraper):
    """
    Levels.fyi scraper.

    Extracts structured job data from the __NEXT_DATA__ JSON payload
    embedded in the page. Each result contains company info and nested
    job objects with base salary, total comp, location, and work arrangement.
    """

    SOURCE = "Levels.fyi"

    def __init__(self):
        super().__init__()

    def scrape(
        self,
        keyword: str,
        location: str,
        currency: str = "USD",
        usd_rate: float = 1.0,
        max_jobs: int = None,
    ) -> List[Dict]:
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        driver = None
        jobs: List[Dict] = []

        try:
            driver = setup_driver()

            url = (
                f"https://www.levels.fyi/jobs"
                f"?searchText={quote_plus(keyword)}"
                f"&location={quote_plus(location)}"
            )
            self.logger.info("Levels.fyi: loading %s", url)
            driver.get(url)
            time.sleep(random.uniform(4, 6))

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Extract __NEXT_DATA__ JSON
            next_data_el = soup.select_one("script#__NEXT_DATA__")
            if not next_data_el or not next_data_el.string:
                self.logger.warning("Levels.fyi: __NEXT_DATA__ not found")
                return self.validate_batch(jobs)

            try:
                data = json.loads(next_data_el.string)
            except json.JSONDecodeError as e:
                self.logger.error("Levels.fyi: failed to parse __NEXT_DATA__: %s", e)
                return self.validate_batch(jobs)

            # Navigate to job results
            jobs_data = (
                data.get("props", {})
                .get("pageProps", {})
                .get("initialJobsData", {})
            )
            results = jobs_data.get("results", [])
            total = jobs_data.get("totalMatchingJobs", 0)

            self.logger.info(
                "Levels.fyi: found %d companies (%d total matching jobs)",
                len(results), total,
            )

            for company_data in results:
                if len(jobs) >= max_jobs:
                    break

                company_name = company_data.get("companyName", "")
                company_type = company_data.get("companyType", "")
                employee_count = company_data.get("employeeCount")

                for job_data in company_data.get("jobs", []):
                    if len(jobs) >= max_jobs:
                        break

                    job_title = job_data.get("title")
                    if not job_title:
                        continue

                    # Salary: use total comp (base + bonus + equity) midpoint
                    min_total = job_data.get("minTotalSalary")
                    max_total = job_data.get("maxTotalSalary")
                    min_base = job_data.get("minBaseSalary")
                    max_base = job_data.get("maxBaseSalary")
                    salary_currency = job_data.get("baseSalaryCurrency", "USD")

                    # Prefer total comp, fall back to base
                    salary_str = None
                    if min_total and max_total:
                        midpoint = (min_total + max_total) / 2
                        salary_str = f"${midpoint:,.0f} USD/yr"
                    elif min_base and max_base:
                        midpoint = (min_base + max_base) / 2
                        salary_str = f"${midpoint:,.0f} USD/yr"

                    # Location
                    locations = job_data.get("locations", [])
                    job_location = locations[0] if locations else location

                    # Work arrangement
                    work_arr = (job_data.get("workArrangement") or "").lower()
                    if "remote" in work_arr:
                        remote_type = "Remote"
                    elif "hybrid" in work_arr:
                        remote_type = "Hybrid"
                    else:
                        remote_type = "On-site"

                    # Link
                    job_link = job_data.get("applicationUrl", "")
                    job_id = job_data.get("id", "")

                    # Dedup
                    company_lower = company_name.lower().strip()
                    title_lower = job_title.lower().strip()
                    dedup_key = hashlib.md5(
                        f"levelsfyi{company_lower}{title_lower}{job_id}".encode()
                    ).hexdigest()[:12]

                    # Posting date
                    posting_date = job_data.get("postingDate")

                    job = {
                        "job_title": job_title,
                        "company_name": company_name,
                        "location": job_location,
                        "salary": salary_str,
                        "salary_currency": salary_currency,
                        "seniority_level": infer_seniority(job_title, None),
                        "experience_required": None,
                        "employment_type": "Full-time",
                        "remote_type": remote_type,
                        "industry": "Technology",
                        "education_required": None,
                        "has_equity": True,  # Levels.fyi tracks total comp (includes equity)
                        "has_bonus": True,
                        "has_remote_benefits": remote_type in ("Remote", "Hybrid"),
                        "skills_required": None,
                        "job_description": (
                            f"{company_name} ({company_type}, "
                            f"{employee_count or '?'} employees). "
                            f"Base: ${min_base:,}-${max_base:,}. "
                            f"Total: ${min_total:,}-${max_total:,}."
                            if min_base and max_base and min_total and max_total
                            else f"Levels.fyi listing for {job_title} at {company_name}"
                        ),
                        "job_link": job_link,
                        "job_id": job_id,
                        "source_website": self.SOURCE,
                        "dedup_key": dedup_key,
                        "is_faang": is_faang(company_name),
                        "cost_of_living_index": COL_INDEX.get(location, 80),
                        "date_posted_raw": posting_date,
                        "applicant_count": None,
                        "currency": currency,
                    }

                    jobs.append(self.validate_job_record(job))
                    self.logger.info(
                        "Levels.fyi: scraped %d/%d — %s @ %s (%s)",
                        len(jobs), max_jobs, job_title, company_name,
                        salary_str or "no salary",
                    )

        except Exception as e:
            self.logger.error("Levels.fyi scraper failed: %s", e)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        return self.validate_batch(jobs)
