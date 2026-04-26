"""
scrapers/payscale_scraper.py
-----------------------------
PayScale salary scraper. Inherits BaseScraper.

Scrapes salary research data from PayScale.com. Instead of looking for
individual job listings, this scraper extracts the rich structured salary
data from PayScale's research pages: median salary, salary range, and
per-company salary breakdowns (often 50-100+ companies per job title).
"""

import re
import time
import random
import hashlib
from typing import Dict, List
from urllib.parse import quote

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException

from scrapers.base_scraper import BaseScraper
from utils.driver_utils import setup_driver
from utils.text_utils import clean_text, infer_seniority, is_faang
from utils.salary_utils import parse_salary_to_usd
from config import MAX_JOBS_PER_SEARCH, COL_INDEX


class PayScaleScraper(BaseScraper):
    """
    PayScale scraper.

    Scrapes PayScale's salary research pages. These pages contain:
    - The median/average salary for a job title
    - Per-company salary averages (50-100+ companies)
    - Per-city salary breakdowns
    - Per-experience-level salary data

    Each company+salary pair becomes a separate job record.
    """

    SOURCE = "PayScale"

    # PayScale uses Job=Title_With_Underscores format
    EXPERIENCE_MAP = {
        "Entry-Level": "Entry Level (0-2 years)",
        "Early-Career": "Entry Level (0-2 years)",
        "Mid-Career": "Mid-Level (2-5 years)",
        "Experienced": "Senior (5+ years)",
        "Late-Career": "Senior (5+ years)",
    }

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

            # PayScale URL format: Job=Data_Scientist
            formatted_keyword = keyword.strip().replace(" ", "_").title()
            url = f"https://www.payscale.com/research/US/Job={quote(formatted_keyword, safe='')}/Salary"
            self.logger.info("PayScale: loading %s", url)
            driver.get(url)
            time.sleep(random.uniform(3, 5))

            # Scroll to load all content
            for _ in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(0.8, 1.2))

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # 1. Extract the median/average salary from the main chart
            median_salary = None
            median_el = soup.select_one("span.paycharts__value")
            if median_el:
                median_salary = parse_salary_to_usd(median_el.get_text(strip=True), usd_rate)
                self.logger.info("PayScale: median salary = %s", median_salary)

            # 2. Extract salary range from percentile chart
            range_min = None
            range_max = None
            for div in soup.select("div.tablerow__value"):
                text = div.get_text(strip=True)
                # First tablerow__value is usually "Base Salary: $73k - $145k"
                range_match = re.search(r'\$(\d+[\d,]*)[kK]?\s*[-–]\s*\$(\d+[\d,]*)[kK]?', text)
                if range_match and not range_min:
                    low_str, high_str = range_match.group(1), range_match.group(2)
                    try:
                        range_min = int(low_str.replace(",", "")) * (1000 if "k" in text.lower() or int(low_str.replace(",", "")) < 1000 else 1)
                        range_max = int(high_str.replace(",", "")) * (1000 if "k" in text.lower() or int(high_str.replace(",", "")) < 1000 else 1)
                    except ValueError:
                        pass

            # 3. Extract per-company salary data from employer links
            # These are <a> tags with href containing /Salary/ and company name
            company_links = soup.select("a[href*='/Salary/']")
            seen_companies = set()

            for link in company_links:
                if len(jobs) >= max_jobs:
                    break

                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Filter: must be a company-specific salary page
                # Format: /research/US/Job=Data_Scientist/Salary/HASH/Company-Name
                if not re.search(r'/Salary/[a-f0-9]+/', href):
                    continue

                # Extract company name and salary from the link text
                # Text format: "Amazon.com IncAvg. Salary: $107,588"
                salary_match = re.search(r'Avg\.\s*Salary:\s*\$([\d,]+)', text)
                if not salary_match:
                    continue

                salary_str = salary_match.group(1)
                company_name = text[:text.index("Avg.")].strip()

                if not company_name or company_name in seen_companies:
                    continue
                seen_companies.add(company_name)

                salary_amount = salary_str.replace(",", "")
                try:
                    salary_usd = f"${int(salary_amount):,} USD/yr"
                except ValueError:
                    continue

                company_lower = company_name.lower().strip()
                title_lower = keyword.lower().strip()
                loc_lower = location.lower().strip()
                dedup_key = hashlib.md5(
                    f"payscale{company_lower}{title_lower}{loc_lower}".encode()
                ).hexdigest()[:12]

                job = {
                    "job_title": keyword.title(),
                    "company_name": company_name,
                    "location": location,
                    "salary": salary_usd,
                    "salary_currency": currency,
                    "seniority_level": infer_seniority(keyword, None),
                    "experience_required": None,
                    "employment_type": "Full-time",
                    "remote_type": "On-site",
                    "industry": None,
                    "education_required": None,
                    "has_equity": False,
                    "has_bonus": False,
                    "has_remote_benefits": False,
                    "skills_required": None,
                    "job_description": f"PayScale average salary for {keyword} at {company_name}",
                    "job_link": f"https://www.payscale.com{href}" if href.startswith("/") else href,
                    "job_id": dedup_key,
                    "source_website": self.SOURCE,
                    "dedup_key": dedup_key,
                    "is_faang": is_faang(company_name),
                    "cost_of_living_index": COL_INDEX.get(location, 80),
                    "date_posted_raw": None,
                    "applicant_count": None,
                    "currency": currency,
                }

                jobs.append(self.validate_job_record(job))
                self.logger.info(
                    "PayScale: scraped %d — %s @ %s (%s)",
                    len(jobs), keyword.title(), company_name, salary_usd,
                )

            # 4. Fallback: if no per-company data, use the median
            if not jobs and median_salary:
                dedup_key = hashlib.md5(
                    f"payscale{keyword.lower()}{location.lower()}".encode()
                ).hexdigest()[:12]
                job = {
                    "job_title": keyword.title(),
                    "company_name": None,
                    "location": location,
                    "salary": median_salary,
                    "salary_currency": currency,
                    "seniority_level": infer_seniority(keyword, None),
                    "experience_required": None,
                    "employment_type": "Full-time",
                    "remote_type": "On-site",
                    "industry": None,
                    "education_required": None,
                    "has_equity": False,
                    "has_bonus": False,
                    "has_remote_benefits": False,
                    "skills_required": None,
                    "job_description": f"PayScale median salary for {keyword}: {median_salary}",
                    "job_link": url,
                    "job_id": dedup_key,
                    "source_website": self.SOURCE,
                    "dedup_key": dedup_key,
                    "is_faang": False,
                    "cost_of_living_index": COL_INDEX.get(location, 80),
                    "date_posted_raw": None,
                    "applicant_count": None,
                    "currency": currency,
                }
                jobs.append(self.validate_job_record(job))

        except Exception as e:
            self.logger.error("PayScale scraper failed: %s", e)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        return self.validate_batch(jobs)
