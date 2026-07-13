"""
scrapers/instahyre_scraper.py
-----------------------------
Instahyre job scraper. Inherits BaseScraper.

Uses Scrapling's StealthyFetcher to scrape the dynamic job search page.
"""

import hashlib
from typing import Dict, List
from urllib.parse import quote_plus

from scrapling.fetchers import StealthyFetcher

from scrapers.base_scraper import BaseScraper
from utils.text_utils import (
    clean_text, extract_skills, extract_experience,
    infer_seniority, is_faang,
)
from utils.salary_utils import extract_salary_from_text
from config import MAX_JOBS_PER_SEARCH, COL_INDEX


class InstahyreScraper(BaseScraper):
    SOURCE = "Instahyre"

    def __init__(self):
        super().__init__()

    def scrape(self, keyword, location, currency="INR", usd_rate=0.012, max_jobs=None):
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        jobs: List[Dict] = []

        try:
            # Build search URL
            url = f"https://www.instahyre.com/jobs/?search=true&keywords={quote_plus(keyword)}"
            self.logger.info("Instahyre: loading %s", url)

            # Instahyre redirects anonymous searches to a login page — inject the
            # session cookie from the INSTAHYRE_COOKIE secret. Missing cookie is
            # warned by load_cookies(); empty results with a cookie present means
            # it expired.
            cookies = self.load_cookies("INSTAHYRE_COOKIE", ".instahyre.com")
            page = StealthyFetcher.fetch(url, headless=True, network_idle=True, cookies=cookies)

            # Instahyre's job cards are company-card or job-card structures
            cards = page.css(
                "div.company-card, "
                "div[id^='job-card'], "
                "div[class*='job-card'], "
                "div.employer-details"
            )
            if not cards:
                if cookies:
                    self.logger.warning(
                        "Instahyre: no job cards — INSTAHYRE_COOKIE may be expired "
                        "(redirected to login) or selectors changed."
                    )
                return self.validate_batch(jobs)

            self.logger.info("Instahyre: found %d cards", len(cards))

            for card in cards[:max_jobs]:
                try:
                    card_text = card.text or ""

                    # Job Title
                    title_el = card.css("a.job-title, a.position, [class*='title'], [class*='position']")
                    job_title = clean_text(title_el[0].text) if title_el else None
                    if not job_title:
                        continue

                    # Job Link
                    job_link = url
                    if title_el:
                        href = title_el[0].attrib.get("href", "")
                        if href:
                            job_link = href if href.startswith("http") else f"https://www.instahyre.com{href}"

                    # Company Name
                    company_el = card.css("div.company-name, [class*='company-name'], [class*='company']")
                    company_name = clean_text(company_el[0].text) if company_el else None

                    # Location
                    loc_el = card.css("span.location, [class*='location'], [class*='loc']")
                    card_location = clean_text(loc_el[0].text) if loc_el else location

                    # Salary
                    salary = extract_salary_from_text(card_text, usd_rate)

                    # Skills
                    skills_el = card.css("div.skills, span.tag, [class*='skills'], [class*='tag']")
                    skills = None
                    if skills_el:
                        skills = ", ".join(clean_text(el.text) for el in skills_el if el.text)

                    # Experience
                    exp_el = card.css("span.experience, [class*='experience'], [class*='exp']")
                    experience = clean_text(exp_el[0].text) if exp_el else None

                    # Dedup
                    company_lower = (company_name or "").lower().strip()
                    title_lower   = (job_title or "").lower().strip()
                    loc_lower     = location.lower().strip()
                    dedup_key = hashlib.md5(
                        f"instahyre{company_lower}{title_lower}{loc_lower}".encode()
                    ).hexdigest()[:12]

                    # Remote
                    remote_type = "On-site"
                    text_lower = card_text.lower()
                    if "remote" in text_lower or "work from home" in text_lower:
                        remote_type = "Remote"
                    elif "hybrid" in text_lower:
                        remote_type = "Hybrid"

                    job = {
                        "job_title":            job_title,
                        "company_name":         company_name,
                        "location":             card_location,
                        "salary":               salary,
                        "salary_currency":      currency,
                        "seniority_level":      infer_seniority(job_title, None),
                        "experience_required":  experience,
                        "employment_type":      "Full-time",
                        "remote_type":          remote_type,
                        "industry":             None,
                        "education_required":   None,
                        "has_equity":           "equity" in text_lower or "stock" in text_lower,
                        "has_bonus":            "bonus" in text_lower,
                        "has_remote_benefits":  remote_type in ("Remote", "Hybrid"),
                        "skills_required":      skills,
                        "job_description":      f"Instahyre listing for {job_title} at {company_name}",
                        "job_link":             job_link,
                        "job_id":               dedup_key,
                        "source_website":       self.SOURCE,
                        "dedup_key":            dedup_key,
                        "is_faang":             is_faang(company_name or ""),
                        "cost_of_living_index": COL_INDEX.get(location, 80),
                        "date_posted_raw":      None,
                        "applicant_count":      None,
                        "currency":             currency,
                    }

                    jobs.append(self.validate_job_record(job))
                    self.logger.info(
                        "Instahyre: scraped %d/%d — %s @ %s",
                        len(jobs), max_jobs, job_title, company_name,
                    )

                except Exception as card_err:
                    self.logger.debug("Instahyre: item error — %s", card_err)
                    continue

        except Exception as e:
            self.logger.error("Instahyre scraper failed: %s", e)

        return self.validate_batch(jobs)
