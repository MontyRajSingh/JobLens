"""
scrapers/indeed_scraper.py
---------------------------
Indeed job scraper. Inherits BaseScraper.

Paginates through up to 3 pages of search results per query.
Handles CAPTCHA detection, consent-modal dismissal, and country-specific
domains mapped by currency code from config.py.

Indeed is the best source for employment_type and date_posted_raw
since it shows those on both the card and the detail page.
Salary fill rate is lower than LinkedIn for US jobs but higher for UK (£).

Imports all utilities from utils/ and constants from config.py.
No logic is duplicated here.
"""

import re
import time
import random
import hashlib
import logging
from typing import Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
)

from scrapers.base_scraper import BaseScraper
from utils.driver_utils import setup_driver
from utils.text_utils import (
    clean_text,
    extract_experience,
    extract_skills,
    infer_seniority,
    parse_indeed_metadata,
    is_faang,
    seniority_to_experience,
)
from utils.salary_utils import extract_salary_from_text
from config import INDEED_DOMAINS, COL_INDEX, MAX_JOBS_PER_SEARCH


class IndeedScraper(BaseScraper):
    """
    Indeed job scraper.

    Paginates through search results (up to MAX_PAGES), collects job cards,
    then visits each detail page for full description and salary extraction.
    Uses self.logger (from BaseScraper.__init__) for named log output.
    """

    SOURCE   = "Indeed"
    MAX_PAGES = 3           # 15 jobs/page × 3 pages = up to 45 per query

    def __init__(self):
        super().__init__()  # initialises self.logger

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
        Scrape Indeed jobs for a keyword/location combination.

        Args:
            keyword:   Job search keyword e.g. "data scientist"
            location:  Location string e.g. "New York, NY"
            currency:  Currency code — used to select the correct Indeed domain
            usd_rate:  Conversion rate to USD
            max_jobs:  Max jobs to collect (defaults to MAX_JOBS_PER_SEARCH)

        Returns:
            List of validated job dicts matching BaseScraper.REQUIRED_COLUMNS
        """
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        base_url = INDEED_DOMAINS.get(currency, "https://www.indeed.com")
        driver   = None
        jobs: List[Dict] = []
        collected = 0

        try:
            driver = setup_driver()

            for page in range(self.MAX_PAGES):
                if collected >= max_jobs:
                    break

                url = (
                    f"{base_url}/jobs?"
                    f"q={quote_plus(keyword)}"
                    f"&l={quote_plus(location)}"
                    f"&sort=date"
                    f"&start={page * 15}"
                )
                self.logger.info("Indeed: loading page %d — %s", page, url)
                driver.get(url)
                time.sleep(random.uniform(3, 5))

                # CAPTCHA check — skip page if blocked
                if "captcha" in driver.title.lower():
                    self.logger.warning(
                        "Indeed: CAPTCHA detected on page %d, skipping", page
                    )
                    continue

                # Also check for robot/block pages in body
                page_text = driver.page_source.lower()
                if "unusual traffic" in page_text or "blocked" in page_text[:2000]:
                    self.logger.warning(
                        "Indeed: blocked page detected on page %d, skipping", page
                    )
                    continue

                # Close any consent/cookie modals
                self._close_modals(driver)

                # Collect cards from this results page
                cards = self._collect_cards(driver, base_url)
                self.logger.info(
                    "Indeed: page %d — found %d cards for '%s' in '%s'",
                    page, len(cards), keyword, location,
                )

                if not cards:
                    self.logger.info("Indeed: no cards found on page %d, stopping", page)
                    break

                for card in cards:
                    if collected >= max_jobs:
                        break

                    try:
                        details = self._get_details(driver, card, currency, usd_rate)
                        job = {**card, **details}

                        # Stamp metadata.
                        # NOTE: "city" (display name) is stamped by main.py after
                        # scrape() returns — do not set it here.
                        job["currency"]             = currency
                        job["source_website"]       = self.SOURCE
                        job["is_faang"]             = is_faang(job.get("company_name", ""))
                        job["cost_of_living_index"] = COL_INDEX.get(location, 80)

                        # Dedup key
                        company = (job.get("company_name") or "").lower().strip()
                        title   = (job.get("job_title")    or "").lower().strip()
                        loc     = location.lower().strip()
                        job["dedup_key"] = hashlib.md5(
                            f"{company}{title}{loc}".encode()
                        ).hexdigest()[:12]

                        jobs.append(self.validate_job_record(job))
                        collected += 1
                        self.logger.info(
                            "Indeed: scraped %d/%d — %s @ %s",
                            collected, max_jobs,
                            job.get("job_title", "?"),
                            job.get("company_name", "?"),
                        )

                        # Polite delay between detail page fetches
                        time.sleep(random.uniform(2.5, 5.0))

                    except Exception as e:
                        self.logger.error("Indeed: error processing card: %s", e)
                        continue

        except Exception as e:
            self.logger.error("Indeed scraper failed: %s", e)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        return self.validate_batch(jobs)

    # ── Modal dismissal ────────────────────────────────────────────────────────
    def _close_modals(self, driver) -> None:
        """Close consent, cookie, and signup modals that Indeed often shows."""
        selectors = [
            "#onetrust-accept-btn-handler",
            "[aria-label='close']",
            "[aria-label='Close']",
            ".icl-CloseButton",
            "#close-btn",
            ".popover-x-button",
            "[data-testid='modal-close-btn']",
        ]
        for sel in selectors:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                btn.click()
                time.sleep(0.5)
            except Exception:
                continue

    # ── Card collection ────────────────────────────────────────────────────────
    def _collect_cards(self, driver, base_url: str) -> List[Dict]:
        """
        Collect job cards from the current Indeed search results page.

        Tries multiple CSS selector patterns to handle Indeed's frequent
        HTML structure changes.

        Returns list of dicts with keys:
            job_title, company_name, location, salary,
            job_link, job_id, date_posted_raw
        """
        # Try selectors in order — Indeed changes class names frequently
        card_elements = []
        for sel in [
            ".job_seen_beacon",
            ".tapItem",
            "[data-jk]",
            ".resultContent",
            "li.css-5lfssm",        # newer Indeed layout
        ]:
            card_elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if card_elements:
                break

        cards: List[Dict] = []

        for el in card_elements:
            try:
                # ── Title + link ───────────────────────────────────────────────
                job_title = None
                job_link  = None
                for sel in [
                    "h2.jobTitle a",
                    "h2 a[data-jk]",
                    "h2 a",
                    ".jcs-JobTitle a",
                    "[data-testid='job-title'] a",
                ]:
                    try:
                        title_el  = el.find_element(By.CSS_SELECTOR, sel)
                        job_title = clean_text(title_el.text)
                        job_link  = title_el.get_attribute("href")
                        if job_title and job_link:
                            break
                    except NoSuchElementException:
                        continue

                # Skip card with no title or link
                if not job_title or not job_link:
                    continue

                # Resolve relative URLs
                if job_link and not job_link.startswith("http"):
                    job_link = urljoin(base_url, job_link)

                # ── Company ────────────────────────────────────────────────────
                company_name = None
                for sel in [
                    ".companyName",
                    "[data-testid='company-name']",
                    ".css-1ioi40n",     # newer layout
                    "span.companyName",
                ]:
                    try:
                        company_name = clean_text(
                            el.find_element(By.CSS_SELECTOR, sel).text
                        )
                        if company_name:
                            break
                    except NoSuchElementException:
                        continue

                # ── Location ───────────────────────────────────────────────────
                card_location = None
                for sel in [
                    ".companyLocation",
                    "[data-testid='text-location']",
                    ".css-1p0sjhy",     # newer layout
                ]:
                    try:
                        card_location = clean_text(
                            el.find_element(By.CSS_SELECTOR, sel).text
                        )
                        if card_location:
                            break
                    except NoSuchElementException:
                        continue

                # ── Salary on card (Indeed shows this more often than LinkedIn) ─
                salary_raw = None
                for sel in [
                    ".salary-snippet-container",
                    ".salaryText",
                    ".estimated-salary",
                    "[data-testid='attribute_snippet_testid']",
                    ".css-1cvvo1r",
                ]:
                    try:
                        salary_raw = clean_text(
                            el.find_element(By.CSS_SELECTOR, sel).text
                        )
                        if salary_raw and any(
                            c in salary_raw for c in ["$", "£", "€", "₹", "K", "k"]
                        ):
                            break
                        else:
                            salary_raw = None
                    except NoSuchElementException:
                        continue

                # ── Employment type on card ────────────────────────────────────
                employment_type = None
                for sel in [
                    ".attribute_snippet",
                    "[data-testid='attribute_snippet_testid']",
                ]:
                    try:
                        snippets = el.find_elements(By.CSS_SELECTOR, sel)
                        for snippet in snippets:
                            text = (snippet.text or "").lower()
                            for etype in [
                                "full-time", "part-time", "contract",
                                "temporary", "internship", "permanent",
                            ]:
                                if etype in text:
                                    employment_type = etype.replace("-", " ").title()
                                    break
                            if employment_type:
                                break
                    except NoSuchElementException:
                        continue

                # ── Job ID ─────────────────────────────────────────────────────
                job_id = el.get_attribute("data-jk")
                if not job_id and job_link:
                    jk_match = re.search(r"jk=([a-f0-9]+)", job_link)
                    if jk_match:
                        job_id = jk_match.group(1)

                # ── Date posted on card ────────────────────────────────────────
                date_raw = None
                for sel in [
                    ".date",
                    "[data-testid='myJobsStateDate']",
                    "span.date",
                ]:
                    try:
                        date_text = clean_text(
                            el.find_element(By.CSS_SELECTOR, sel).text
                        )
                        # Only keep if it looks like a date ("Posted X days ago")
                        if date_text and any(
                            w in date_text.lower()
                            for w in ["posted", "today", "ago", "just"]
                        ):
                            date_raw = date_text
                            break
                    except NoSuchElementException:
                        continue

                cards.append({
                    "job_title":       job_title,
                    "company_name":    company_name,
                    "location":        card_location,
                    "salary":          salary_raw,       # raw string — normalised in _get_details
                    "employment_type": employment_type,
                    "job_link":        job_link,
                    "job_id":          job_id,
                    "date_posted_raw": date_raw,
                })

            except Exception as e:
                self.logger.debug("Indeed: skipping card — %s", e)
                continue

        return cards

    # ── Detail page ────────────────────────────────────────────────────────────
    def _get_details(
        self,
        driver,
        card: Dict,
        currency: str,
        usd_rate: float,
    ) -> Dict:
        """
        Visit an Indeed job detail page and extract all enriched fields.

        Safe to call — never raises. Returns defaults if extraction fails.

        Args:
            driver:   Selenium WebDriver
            card:     Card dict from _collect_cards
            currency: Local currency code
            usd_rate: Conversion rate to USD

        Returns:
            Dict with all detail fields. Missing fields default to None/False.
        """
        details: Dict = {
            "salary":              None,
            "salary_currency":     currency,
            "seniority_level":     None,
            "experience_required": None,
            "employment_type":     card.get("employment_type"),  # carry forward from card
            "remote_type":         "On-site",
            "industry":            None,
            "education_required":  None,
            "has_equity":          False,
            "has_bonus":           False,
            "has_remote_benefits": False,
            "date_posted_raw":     card.get("date_posted_raw"),  # carry forward from card
            "applicant_count":     None,
            "skills_required":     None,
            "job_description":     None,
        }

        job_link = card.get("job_link")
        if not job_link:
            return details

        try:
            driver.get(job_link)
            time.sleep(random.uniform(2.5, 4.0))

            # ── Description ────────────────────────────────────────────────────
            description = None
            for sel in [
                "#jobDescriptionText",
                ".jobsearch-jobDescriptionText",
                ".jobDescription",
                "[data-testid='jobDescriptionText']",
            ]:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, sel)
                    text = clean_text(elem.text)
                    if text and len(text) > 50:
                        description = text
                        details["job_description"] = description[:5000]
                        break
                except NoSuchElementException:
                    continue

            # ── Salary — 3-layer: card → detail element → description text ─────
            # Layer 1: salary already on card
            salary_raw = card.get("salary")
            if salary_raw:
                parsed = extract_salary_from_text(salary_raw, usd_rate)
                if parsed:
                    details["salary"] = parsed

            # Layer 2: structured salary element on detail page
            if not details["salary"]:
                for sel in [
                    "#salaryInfoAndJobType",
                    "[data-testid='attribute_snippet_testid']",
                    ".jobsearch-JobMetadataHeader-item",
                    ".js-match-insights-provider-hardcoded-content",
                    ".css-1cvvo1r",
                ]:
                    try:
                        sal_text = clean_text(
                            driver.find_element(By.CSS_SELECTOR, sel).text
                        )
                        if sal_text and any(
                            c in sal_text for c in ["$", "£", "€", "₹", "K", "k"]
                        ):
                            parsed = extract_salary_from_text(sal_text, usd_rate)
                            if parsed:
                                details["salary"] = parsed
                                break
                    except NoSuchElementException:
                        continue

            # Layer 3: scan description text as last resort
            if not details["salary"] and description:
                details["salary"] = extract_salary_from_text(description, usd_rate)

            # ── Employment type from detail page ───────────────────────────────
            if not details["employment_type"]:
                for sel in [
                    "#jobDetailsSection",
                    ".jobsearch-JobDescriptionSection-sectionItem",
                    "[data-testid='jobDetailsSection']",
                ]:
                    try:
                        type_text = driver.find_element(
                            By.CSS_SELECTOR, sel
                        ).text.lower()
                        for etype in [
                            "full-time", "part-time", "contract",
                            "temporary", "internship", "permanent",
                        ]:
                            if etype in type_text:
                                details["employment_type"] = etype.replace("-", " ").title()
                                break
                        if details["employment_type"]:
                            break
                    except NoSuchElementException:
                        continue

            if description:
                # Skills from SKILL_LIST matching
                details["skills_required"] = extract_skills(description)

                # Experience — salary patterns stripped first
                details["experience_required"] = extract_experience(description)

                # Indeed metadata: remote, equity, bonus, education
                meta = parse_indeed_metadata(description)
                details["remote_type"]        = meta.get("remote_type", "On-site")
                details["education_required"] = meta.get("education_required")
                details["has_equity"]         = meta.get("has_equity", False)
                details["has_bonus"]          = meta.get("has_bonus", False)

                # employment_type from description if still missing
                if not details["employment_type"]:
                    details["employment_type"] = meta.get("employment_type")

            # ── Seniority from job title ───────────────────────────────────────
            details["seniority_level"] = infer_seniority(card.get("job_title"))

            # Remote benefits flag
            if details["remote_type"] in ("Remote", "Hybrid"):
                details["has_remote_benefits"] = True

            # Experience fallback from seniority
            if not details["experience_required"] and details["seniority_level"]:
                details["experience_required"] = seniority_to_experience(
                    details["seniority_level"]
                )

        except Exception as e:
            self.logger.error(
                "Indeed: detail page error for %s — %s", job_link, e
            )

        return details