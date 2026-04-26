"""
scrapers/ziprecruiter_scraper.py
---------------------------------
ZipRecruiter job scraper. Inherits BaseScraper.

Scrapes job listings from ZipRecruiter.com, which aggregates postings
from multiple sources and often includes salary estimates even when
employers don't explicitly provide them.
"""

import re
import time
import random
import hashlib
from typing import Dict, List
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from scrapers.base_scraper import BaseScraper
from utils.driver_utils import setup_driver
from utils.text_utils import (
    clean_text, extract_skills, extract_experience,
    infer_seniority, is_faang,
)
from utils.salary_utils import extract_salary_from_text, extract_salary_from_page
from config import MAX_JOBS_PER_SEARCH, COL_INDEX


class ZipRecruiterScraper(BaseScraper):
    """
    ZipRecruiter scraper.

    Scrapes ZipRecruiter job search results including salary estimates,
    company info, and job descriptions. ZipRecruiter often provides
    AI-estimated salaries even when employers don't list them.
    """

    SOURCE = "ZipRecruiter"

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
                f"https://www.ziprecruiter.com/jobs-search"
                f"?search={quote_plus(keyword)}"
                f"&location={quote_plus(location)}"
            )
            self.logger.info("ZipRecruiter: loading %s", url)
            driver.get(url)
            time.sleep(random.uniform(4, 6))

            # Scroll to load more results
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.0, 2.0))

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # ZipRecruiter job card selectors
            card_selectors = [
                "article[class*='job_result']",
                "div[class*='job_result']",
                "article[class*='JobCard']",
                "div[class*='job-listing']",
                "li[class*='job-listing']",
                "div[data-testid*='job']",
            ]

            cards = []
            for sel in card_selectors:
                cards = soup.select(sel)
                if cards:
                    self.logger.info("ZipRecruiter: found %d cards with '%s'", len(cards), sel)
                    break

            if not cards:
                self.logger.warning("ZipRecruiter: no job cards found")
                return self.validate_batch(jobs)

            for i, card in enumerate(cards[:max_jobs]):
                try:
                    card_text = card.get_text(separator=" ", strip=True)

                    # Title
                    title_el = card.select_one(
                        "h2[class*='title'], a[class*='job_link'], "
                        "[class*='job_title'], [data-testid*='title'], h2, h3"
                    )
                    job_title = clean_text(title_el.get_text()) if title_el else None
                    if not job_title:
                        continue

                    # Company
                    company_el = card.select_one(
                        "[class*='company'], [class*='employer'], "
                        "[data-testid*='company'], span[class*='name']"
                    )
                    company_name = clean_text(company_el.get_text()) if company_el else None

                    # Salary
                    salary = extract_salary_from_text(card_text, usd_rate)

                    # Location
                    loc_el = card.select_one("[class*='location'], [data-testid*='location']")
                    card_location = clean_text(loc_el.get_text()) if loc_el else location

                    # Link
                    link_el = card.select_one("a[href]")
                    job_link = None
                    if link_el:
                        href = link_el.get("href", "")
                        job_link = href if href.startswith("http") else f"https://www.ziprecruiter.com{href}"

                    # Description snippet
                    desc_el = card.select_one("[class*='snippet'], [class*='description'], p")
                    description = clean_text(desc_el.get_text()) if desc_el else card_text

                    # Remote detection
                    remote_type = "On-site"
                    text_lower = card_text.lower()
                    if "remote" in text_lower:
                        remote_type = "Remote"
                    elif "hybrid" in text_lower:
                        remote_type = "Hybrid"

                    company = (company_name or "").lower().strip()
                    title = (job_title or "").lower().strip()
                    loc = location.lower().strip()
                    dedup_key = hashlib.md5(f"{company}{title}{loc}".encode()).hexdigest()[:12]

                    job = {
                        "job_title": job_title,
                        "company_name": company_name,
                        "location": card_location,
                        "salary": salary,
                        "salary_currency": currency,
                        "seniority_level": infer_seniority(job_title, None),
                        "experience_required": extract_experience(description) if description else None,
                        "employment_type": "Full-time",
                        "remote_type": remote_type,
                        "industry": None,
                        "education_required": None,
                        "has_equity": False,
                        "has_bonus": "bonus" in text_lower,
                        "has_remote_benefits": remote_type in ("Remote", "Hybrid"),
                        "skills_required": extract_skills(description) if description else None,
                        "job_description": description[:5000] if description else None,
                        "job_link": job_link,
                        "job_id": dedup_key,
                        "source_website": self.SOURCE,
                        "dedup_key": dedup_key,
                        "is_faang": is_faang(company_name or ""),
                        "cost_of_living_index": COL_INDEX.get(location, 80),
                        "date_posted_raw": None,
                        "applicant_count": None,
                        "currency": currency,
                    }

                    jobs.append(self.validate_job_record(job))
                    self.logger.info("ZipRecruiter: scraped %d/%d — %s @ %s", i + 1, len(cards[:max_jobs]), job_title, company_name)

                    time.sleep(random.uniform(0.5, 1.0))

                except Exception as e:
                    self.logger.debug("ZipRecruiter: card parse error — %s", e)
                    continue

        except Exception as e:
            self.logger.error("ZipRecruiter scraper failed: %s", e)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        return self.validate_batch(jobs)
