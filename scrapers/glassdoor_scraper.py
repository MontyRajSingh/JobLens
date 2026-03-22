"""
glassdoor_scraper.py — Glassdoor job scraper.

Scrapes job listings from Glassdoor using Selenium. Supports optional
login, modal-popup dismissal, city-ID-based search, company ratings,
and salary estimate type extraction.

Uses utilities from utils/ and constants from config.py exclusively.
"""

import re
import time
import hashlib
import logging
from typing import Dict, List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import GLASSDOOR_CITY_IDS, GLASSDOOR_EMAIL, GLASSDOOR_PASSWORD, COL_INDEX
from scrapers.base_scraper import BaseScraper
from utils.driver_utils import setup_driver
from utils.text_utils import (
    clean_text, extract_experience, infer_seniority,
    extract_skills, is_faang, seniority_to_experience,
)
from utils.salary_utils import extract_salary_from_text, extract_salary_from_page

logger = logging.getLogger(__name__)


class GlassdoorScraper(BaseScraper):
    """
    Scraper for Glassdoor job listings.

    Supports optional email/password login, city-ID-based search via
    GLASSDOOR_CITY_IDS, modal dismissal, company ratings, and salary
    estimate type tracking.
    """

    SOURCE = "Glassdoor"

    def scrape(
        self,
        keyword: str,
        location: str,
        currency: str,
        usd_rate: float,
        max_jobs: int,
    ) -> List[Dict]:
        """
        Scrape Glassdoor job listings.

        Args:
            keyword: Search keyword.
            location: Glassdoor location string (maps to city ID).
            currency: Local currency code.
            usd_rate: Currency-to-USD rate.
            max_jobs: Max jobs to collect.

        Returns:
            List of validated job dicts.
        """
        driver = None
        jobs = []
        city_id = GLASSDOOR_CITY_IDS.get(location)

        if not city_id:
            logger.warning("Glassdoor: no city ID for '%s', skipping", location)
            return []

        try:
            driver = setup_driver()

            # Optional login
            if GLASSDOOR_EMAIL and GLASSDOOR_PASSWORD:
                self._login(driver)

            # Navigate to search
            url = (
                f"https://www.glassdoor.com/Job/jobs.htm?"
                f"sc.keyword={keyword.replace(' ', '+')}"
                f"&locT=C&locId={city_id}"
            )
            driver.get(url)
            time.sleep(5)

            # Close modals
            self._close_modals(driver)

            # Collect cards
            cards = self._collect_cards(driver, max_jobs)
            logger.info("Glassdoor: collected %d cards for '%s' in '%s'", len(cards), keyword, location)

            for i, card in enumerate(cards):
                try:
                    detail = self._get_details(driver, card, currency, usd_rate)
                    job = {**card, **detail}

                    # Stamp metadata
                    job["city"] = location
                    job["currency"] = currency
                    job["source_website"] = self.SOURCE
                    job["is_faang"] = is_faang(job.get("company_name"))
                    job["cost_of_living_index"] = COL_INDEX.get(location)

                    # Dedup key
                    company = (job.get("company_name") or "").lower()
                    title = (job.get("job_title") or "").lower()
                    city = location.lower()
                    job["dedup_key"] = hashlib.md5(
                        f"{company}{title}{city}".encode()
                    ).hexdigest()[:12]

                    job = self.validate_job_record(job)
                    jobs.append(job)
                    logger.info("Glassdoor: scraped %d/%d — %s", i + 1, len(cards), job.get("job_title"))

                    # Polite delay (5-8 seconds)
                    time.sleep(5 + (hash(str(i)) % 4))

                except Exception as e:
                    logger.error("Glassdoor: error on card %d: %s", i, e)
                    continue

        except Exception as e:
            logger.error("Glassdoor scraper error: %s", e)
        finally:
            if driver:
                driver.quit()

        return self.validate_batch(jobs)

    def _login(self, driver) -> None:
        """
        Attempt to log in to Glassdoor with credentials from env vars.

        Args:
            driver: Selenium WebDriver.
        """
        try:
            driver.get("https://www.glassdoor.com/profile/login_input.htm")
            time.sleep(3)

            # Email
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "inlineUserEmail"))
            )
            email_field.clear()
            email_field.send_keys(GLASSDOOR_EMAIL)

            # Click continue
            try:
                continue_btn = driver.find_element(By.CSS_SELECTOR, "[type='submit'], .emailButton")
                continue_btn.click()
                time.sleep(2)
            except Exception:
                pass

            # Password
            try:
                password_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "inlineUserPassword"))
                )
                password_field.clear()
                password_field.send_keys(GLASSDOOR_PASSWORD)

                sign_in_btn = driver.find_element(By.CSS_SELECTOR, "[type='submit'], .signin-button")
                sign_in_btn.click()
                time.sleep(3)
                logger.info("Glassdoor: login successful")
            except Exception as e:
                logger.warning("Glassdoor: password step failed — %s", e)

        except Exception as e:
            logger.warning("Glassdoor: login failed — %s", e)

    def _close_modals(self, driver) -> None:
        """Close modal popups that Glassdoor often shows."""
        modal_selectors = [
            "[alt='Close']",
            ".modal_closeIcon",
            ".modal_closeIcon-svg",
            "[data-test='close-button']",
            ".e1jbctw80",
            "#onetrust-accept-btn-handler",
        ]
        for selector in modal_selectors:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, selector)
                btn.click()
                time.sleep(0.5)
            except Exception:
                continue

    def _collect_cards(self, driver, max_jobs: int) -> List[Dict]:
        """
        Collect job cards from Glassdoor search results.

        Args:
            driver: Selenium WebDriver.
            max_jobs: Maximum cards to collect.

        Returns:
            List of dicts with: job_title, company_name, location, salary,
            company_rating, salary_estimate_type, job_link, job_id.
        """
        cards = []
        selectors = [
            "[data-test='jobListing']",
            ".react-job-listing",
            "li.jl",
            "[data-id]",
        ]

        card_elements = []
        for sel in selectors:
            card_elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if card_elements:
                break

        for el in card_elements[:max_jobs]:
            try:
                # Title
                try:
                    title_el = el.find_element(By.CSS_SELECTOR, "[data-test='job-title'], .job-title")
                    title = clean_text(title_el.text)
                    link = title_el.get_attribute("href")
                    if link and not link.startswith("http"):
                        link = f"https://www.glassdoor.com{link}"
                except Exception:
                    title = None
                    link = None

                # Company name
                try:
                    company_el = el.find_element(By.CSS_SELECTOR, "[data-test='employer-name'], .employer-name")
                    company = clean_text(company_el.text)
                    # Remove trailing rating like "Company Name 4.2★"
                    if company:
                        company = re.sub(r"\s*[\d.]+\s*★?\s*$", "", company).strip()
                except Exception:
                    company = None

                # Location
                try:
                    loc_el = el.find_element(By.CSS_SELECTOR, "[data-test='emp-location'], .job-location")
                    loc = clean_text(loc_el.text)
                except Exception:
                    loc = None

                # Salary
                salary = None
                try:
                    salary_el = el.find_element(By.CSS_SELECTOR, "[data-test='detailSalary'], .salary-estimate")
                    salary = clean_text(salary_el.text)
                except Exception:
                    pass

                # Company rating
                company_rating = None
                try:
                    rating_el = el.find_element(By.CSS_SELECTOR, "[data-test='rating'], .employer-rating")
                    rating_text = rating_el.text.strip()
                    company_rating = float(rating_text)
                except Exception:
                    pass

                # Salary estimate type
                salary_estimate_type = None
                try:
                    est_el = el.find_element(By.CSS_SELECTOR, ".salary-estimate-type, .css-1xe2nb0")
                    salary_estimate_type = clean_text(est_el.text)
                except Exception:
                    pass

                # Job ID
                job_id = el.get_attribute("data-id") or el.get_attribute("data-job-id")
                if not job_id and link:
                    id_match = re.search(r"jobListingId=(\d+)", link)
                    if id_match:
                        job_id = id_match.group(1)

                cards.append({
                    "job_title": title,
                    "company_name": company,
                    "location": loc,
                    "salary": salary,
                    "company_rating": company_rating,
                    "salary_estimate_type": salary_estimate_type,
                    "job_link": link,
                    "job_id": job_id,
                })

            except Exception as e:
                logger.debug("Glassdoor: skipping card — %s", e)
                continue

        return cards

    def _get_details(self, driver, card: Dict, currency: str, usd_rate: float) -> Dict:
        """
        Visit a Glassdoor job detail page and extract structured data.

        Args:
            driver: Selenium WebDriver.
            card: Card dict from _collect_cards.
            currency: Local currency code.
            usd_rate: Currency-to-USD rate.

        Returns:
            Dict of extracted detail fields.
        """
        result = {
            "salary_currency": currency,
            "job_description": None,
            "skills_required": None,
            "experience_required": None,
            "seniority_level": None,
            "employment_type": None,
            "remote_type": "On-site",
            "industry": None,
            "education_required": None,
            "has_equity": 0,
            "has_bonus": 0,
            "has_remote_benefits": 0,
            "date_posted_raw": None,
            "applicant_count": None,
        }

        link = card.get("job_link")
        if not link:
            return result

        try:
            driver.get(link)
            time.sleep(4)

            # Close modals on detail page
            self._close_modals(driver)

            # Description
            description = ""
            try:
                desc_el = driver.find_element(By.CSS_SELECTOR, ".jobDescriptionContent, [data-test='jobDescription'], .desc")
                description = desc_el.text
                result["job_description"] = clean_text(description)
            except Exception:
                pass

            # Salary from card or detail page
            salary = card.get("salary")
            if salary:
                result["salary"] = extract_salary_from_text(salary, usd_rate)

            if not result.get("salary"):
                try:
                    salary_el = driver.find_element(By.CSS_SELECTOR, "[data-test='detailSalary'], .salary-estimate")
                    salary_text = salary_el.text
                    result["salary"] = extract_salary_from_text(salary_text, usd_rate)
                except Exception:
                    pass

            if not result.get("salary") and description:
                result["salary"] = extract_salary_from_text(description, usd_rate)

            # Industry
            try:
                industry_el = driver.find_element(By.CSS_SELECTOR, "[data-test='employer-sector'], .employer-sector")
                result["industry"] = clean_text(industry_el.text)
            except Exception:
                pass

            # Skills
            result["skills_required"] = extract_skills(description)

            # Experience
            result["experience_required"] = extract_experience(description)

            # Remote type
            text_lower = description.lower() if description else ""
            if "remote" in text_lower and "hybrid" in text_lower:
                result["remote_type"] = "Hybrid"
            elif "remote" in text_lower:
                result["remote_type"] = "Remote"
            elif "hybrid" in text_lower:
                result["remote_type"] = "Hybrid"

            # Employment type
            for etype in ["full-time", "full time", "part-time", "part time", "contract", "temporary", "internship"]:
                if etype in text_lower:
                    result["employment_type"] = etype.replace("-", " ").title()
                    break

            # Education
            edu_match = re.search(
                r"\b(ph\.?d|doctorate|master'?s?|bachelor'?s?|b\.?s\.?|m\.?s\.?|mba|b\.?tech|m\.?tech)\b",
                text_lower,
            )
            if edu_match:
                result["education_required"] = edu_match.group(1).title()

            # Equity / Bonus
            result["has_equity"] = 1 if re.search(r"\b(equity|stock|rsu|esop|options)\b", text_lower) else 0
            result["has_bonus"] = 1 if re.search(r"\b(bonus|incentive|commission)\b", text_lower) else 0

            # Seniority
            result["seniority_level"] = infer_seniority(card.get("job_title"))

            # Remote benefits
            if result["remote_type"] in ("Remote", "Hybrid"):
                result["has_remote_benefits"] = 1

            # Fill experience from seniority if still missing
            if not result["experience_required"] and result["seniority_level"]:
                result["experience_required"] = seniority_to_experience(result["seniority_level"])

        except Exception as e:
            logger.error("Glassdoor detail extraction error: %s", e)

        return result
