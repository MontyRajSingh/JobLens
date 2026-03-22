"""
scrapers/linkedin_scraper.py
-----------------------------
LinkedIn job scraper. Inherits BaseScraper.

Scrapes job cards from LinkedIn's public job search page, then visits
each detail page to extract salary, description, skills, seniority,
and metadata from the LinkedIn footer block.

Imports all utilities from utils/ and constants from config.py.
No logic is duplicated here.
"""

import re
import time
import random
import hashlib
import logging
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
)

from scrapers.base_scraper import BaseScraper
from utils.driver_utils import setup_driver
from utils.text_utils import (
    clean_text,
    extract_experience,
    extract_skills,
    infer_seniority,
    parse_linkedin_metadata,
    is_faang,
    seniority_to_experience,
)
from utils.salary_utils import extract_salary_from_page, extract_salary_from_text
from config import MAX_JOBS_PER_SEARCH, COL_INDEX


class LinkedInScraper(BaseScraper):
    """
    LinkedIn job scraper.

    Scrolls the public LinkedIn jobs search page to collect job cards,
    then visits each job's detail page to extract all fields.
    Uses self.logger (from BaseScraper.__init__) for named log output.
    """

    SOURCE = "LinkedIn"

    def __init__(self):
        super().__init__()  # initialises self.logger as scrapers.linkedin_scraper.LinkedInScraper

    # ── Public interface ───────────────────────────────────────────────────────
    def scrape(
        self,
        keyword: str,
        location: str,
        currency: str = "USD",
        usd_rate: float = 1.0,
        max_jobs: int = None,
    ) -> List[Dict]:
        """
        Scrape LinkedIn jobs for a keyword/location combination.

        Args:
            keyword:   Job search keyword e.g. "data scientist"
            location:  LinkedIn location string e.g. "New York City Metropolitan Area"
            currency:  Local currency code e.g. "USD", "GBP"
            usd_rate:  Conversion rate to USD
            max_jobs:  Max jobs to collect (defaults to MAX_JOBS_PER_SEARCH)

        Returns:
            List of validated job dicts matching BaseScraper.REQUIRED_COLUMNS
        """
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        driver = None
        jobs: List[Dict] = []

        try:
            driver = setup_driver()

            # Step 1: collect basic info from search result cards
            cards = self._collect_cards(driver, keyword, location, max_jobs)
            self.logger.info(
                "LinkedIn: collected %d cards for '%s' in '%s'",
                len(cards), keyword, location,
            )

            # Step 2: visit each job detail page
            for i, card in enumerate(cards):
                try:
                    details = self._get_details(
                        driver=driver,
                        job_link=card["job_link"],
                        search_location=location,
                        job_title=card["job_title"],
                        currency=currency,
                        usd_rate=usd_rate,
                    )

                    # Merge card fields with detail fields.
                    # Detail page company takes priority over card company.
                    job = {**card, **details}
                    if not job.get("company_name"):
                        job["company_name"] = card.get("company_name")

                    # Stamp metadata.
                    # NOTE: "city" (display name) is stamped by main.py after scrape()
                    # returns, so we don't set it here. "location" is the raw
                    # card/search location string and is already in the dict.
                    job["currency"]             = currency
                    job["source_website"]       = self.SOURCE
                    job["is_faang"]             = is_faang(job.get("company_name", ""))
                    job["cost_of_living_index"] = COL_INDEX.get(location, 80)

                    # Dedup key: hash of company + title + location
                    company = (job.get("company_name") or "").lower().strip()
                    title   = (job.get("job_title")    or "").lower().strip()
                    loc     = location.lower().strip()
                    job["dedup_key"] = hashlib.md5(
                        f"{company}{title}{loc}".encode()
                    ).hexdigest()[:12]

                    jobs.append(self.validate_job_record(job))
                    self.logger.info(
                        "LinkedIn: scraped %d/%d — %s @ %s",
                        i + 1, len(cards),
                        job.get("job_title", "?"),
                        job.get("company_name", "?"),
                    )

                    time.sleep(random.uniform(1.5, 3.0))

                except Exception as e:
                    self.logger.error("LinkedIn: error on card %d: %s", i, e)
                    continue

        except Exception as e:
            self.logger.error("LinkedIn scraper failed: %s", e)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        return self.validate_batch(jobs)

    # ── Card collection ────────────────────────────────────────────────────────
    def _collect_cards(
        self,
        driver,
        keyword: str,
        location: str,
        max_jobs: int,
    ) -> List[Dict]:
        """
        Load LinkedIn job search results and collect basic card data.

        Scrolls the page 4× to trigger lazy-loading of additional cards.

        Returns list of dicts with keys:
            job_title, company_name, location, job_link, job_id
        """
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={quote_plus(keyword)}"
            f"&location={quote_plus(location)}"
            f"&sortBy=DD"
        )
        self.logger.info("LinkedIn: loading %s", url)
        driver.get(url)
        time.sleep(random.uniform(3, 5))

        # Scroll to trigger lazy-loading
        for _ in range(4):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1.0, 1.5))

        # Wait for at least one card to appear
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".job-search-card"))
            )
        except TimeoutException:
            self.logger.warning("LinkedIn: timed out waiting for job cards")
            return []

        card_elements = driver.find_elements(By.CSS_SELECTOR, ".job-search-card")
        self.logger.info("LinkedIn: found %d cards on page", len(card_elements))

        cards: List[Dict] = []

        for el in card_elements[:max_jobs]:
            try:
                # ── Title ──────────────────────────────────────────────────────
                job_title = None
                for sel in [
                    ".base-search-card__title",
                    "h3.base-search-card__title",
                    "h3",
                ]:
                    try:
                        job_title = clean_text(
                            el.find_element(By.CSS_SELECTOR, sel).text
                        )
                        if job_title:
                            break
                    except NoSuchElementException:
                        continue

                # ── Link ───────────────────────────────────────────────────────
                job_link = None
                for sel in [
                    "a.base-card__full-link",
                    "a.base-search-card__link",
                    "a",
                ]:
                    try:
                        job_link = el.find_element(
                            By.CSS_SELECTOR, sel
                        ).get_attribute("href")
                        if job_link:
                            break
                    except NoSuchElementException:
                        continue

                # Skip card if we can't get both title and link
                if not job_title or not job_link:
                    self.logger.debug("LinkedIn: skipping card — missing title or link")
                    continue

                # ── Company ────────────────────────────────────────────────────
                company_name = None
                for sel in [
                    ".base-search-card__subtitle",
                    "h4.base-search-card__subtitle",
                    "h4 a",
                    "h4",
                ]:
                    try:
                        company_name = clean_text(
                            el.find_element(By.CSS_SELECTOR, sel).text
                        )
                        if company_name and len(company_name) > 1:
                            break
                    except NoSuchElementException:
                        continue

                # BeautifulSoup fallback for company
                if not company_name:
                    try:
                        soup = BeautifulSoup(
                            el.get_attribute("innerHTML"), "html.parser"
                        )
                        h4 = soup.find("h4")
                        if h4:
                            company_name = clean_text(h4.get_text())
                    except Exception:
                        pass

                # ── Location ───────────────────────────────────────────────────
                card_location = None
                for sel in [
                    ".job-search-card__location",
                    "[class*='location']",
                ]:
                    try:
                        card_location = clean_text(
                            el.find_element(By.CSS_SELECTOR, sel).text
                        )
                        if card_location:
                            break
                    except NoSuchElementException:
                        continue

                # ── Job ID from URL ────────────────────────────────────────────
                job_id = None
                id_match = re.search(r"-(\d{5,})(?:\?|$)", job_link)
                if id_match:
                    job_id = id_match.group(1)

                cards.append({
                    "job_title":    job_title,
                    "company_name": company_name,
                    "location":     card_location or location,
                    "job_link":     job_link,
                    "job_id":       job_id,
                })

            except StaleElementReferenceException:
                continue
            except Exception as e:
                self.logger.debug("LinkedIn: card parse error — %s", e)
                continue

        return cards

    # ── Detail page ────────────────────────────────────────────────────────────
    def _get_details(
        self,
        driver,
        job_link: str,
        search_location: str,
        job_title: str,
        currency: str,
        usd_rate: float,
    ) -> Dict:
        """
        Visit a LinkedIn job detail page and extract all enriched fields.

        Safe to call — never raises. Returns default values if extraction fails.

        Args:
            driver:          Selenium WebDriver
            job_link:        Full URL to the job detail page
            search_location: Location string used for the search
            job_title:       Job title from the search card (used for seniority fallback)
            currency:        Local currency code
            usd_rate:        Conversion rate to USD

        Returns:
            Dict with all detail fields. Missing fields default to None/False.
        """
        details: Dict = {
            "salary":              None,
            "salary_currency":     currency,
            "seniority_level":     None,
            "experience_required": None,
            "employment_type":     None,
            "remote_type":         "On-site",
            "industry":            None,
            "education_required":  None,
            "has_equity":          False,
            "has_bonus":           False,
            "has_remote_benefits": False,
            "date_posted_raw":     None,
            "applicant_count":     None,
            "skills_required":     None,
            "job_description":     None,
            "company_name":        None,
            "location":            search_location,
        }

        if not job_link:
            return details

        try:
            driver.get(job_link)
            time.sleep(random.uniform(2.5, 4.0))
            wait = WebDriverWait(driver, 10)

            # ── Salary from structured page elements ───────────────────────────
            details["salary"] = extract_salary_from_page(driver, usd_rate)

            # ── Description ────────────────────────────────────────────────────
            description = None
            for sel in [
                ".jobs-description-content",
                ".job-details__container",
                ".show-more-less-html__markup",
                ".description__text",
                "#job-details",
                "[class*='description']",
            ]:
                try:
                    elem = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    text = clean_text(elem.text)
                    if text and len(text) > 50:
                        description = text
                        details["job_description"] = description[:5000]
                        break
                except (TimeoutException, Exception):
                    continue

            if description:
                # Skills from SKILL_LIST keyword matching
                details["skills_required"] = extract_skills(description)

                # Salary fallback — scan description text
                if not details["salary"]:
                    details["salary"] = extract_salary_from_text(description, usd_rate)

                # Experience — salary patterns stripped first to avoid false matches
                details["experience_required"] = extract_experience(description)

                # All LinkedIn metadata from description footer block
                # e.g. "Seniority level Mid-Senior level Employment type Full-time ..."
                meta = parse_linkedin_metadata(description)
                details["employment_type"]    = meta.get("employment_type")
                details["remote_type"]        = meta.get("remote_type", "On-site")
                details["industry"]           = meta.get("industry")
                details["education_required"] = meta.get("education_required")
                details["has_equity"]         = meta.get("has_equity", False)
                details["has_bonus"]          = meta.get("has_bonus", False)
                details["date_posted_raw"]    = meta.get("date_posted_raw")
                details["applicant_count"]    = meta.get("applicant_count")

                # Seniority: LinkedIn metadata badge wins; title inference as fallback
                details["seniority_level"] = infer_seniority(
                    job_title, meta.get("seniority_raw")
                )

                # Remote benefits flag
                if details["remote_type"] in ("Remote", "Hybrid"):
                    details["has_remote_benefits"] = True

                # Experience fallback: derive from seniority if text gave nothing
                if not details["experience_required"] and details["seniority_level"]:
                    details["experience_required"] = seniority_to_experience(
                        details["seniority_level"]
                    )

            # ── Company from detail page (more accurate than card) ─────────────
            for sel in [
                ".topcard__org-name-link",
                ".job-details-jobs-unified-top-card__company-name",
                ".topcard__flavor--black-link",
                "a[data-tracking-control-name*='org-name']",
            ]:
                try:
                    text = clean_text(
                        driver.find_element(By.CSS_SELECTOR, sel).text
                    )
                    if text:
                        details["company_name"] = text
                        break
                except NoSuchElementException:
                    continue

        except Exception as e:
            self.logger.error(
                "LinkedIn: detail page error for %s — %s", job_link, e
            )

        return details