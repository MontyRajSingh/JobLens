"""
scrapers/wellfound_scraper.py
-----------------------------
Wellfound job scraper. Inherits BaseScraper.

Uses Scrapling's StealthyFetcher to fetch role category pages from Wellfound.
"""

import re
import hashlib
from typing import Dict, List
from urllib.parse import quote

from scrapling.fetchers import StealthyFetcher

from scrapers.base_scraper import BaseScraper
from utils.text_utils import (
    clean_text, extract_skills, extract_experience,
    infer_seniority, is_faang,
)
from utils.salary_utils import extract_salary_from_text
from config import MAX_JOBS_PER_SEARCH, COL_INDEX


class WellfoundScraper(BaseScraper):
    SOURCE = "Wellfound"

    def __init__(self):
        super().__init__()

    def _get_slugs(self, keyword: str, location: str) -> tuple:
        """Standardise keyword and location into Wellfound URL slugs."""
        # Keyword slug
        kw_slug = keyword.lower().strip().replace(" ", "-").replace("/", "-")
        
        # Location slug mapping
        loc_lower = location.lower()
        if "new york" in loc_lower:
            loc_slug = "new-york"
        elif "london" in loc_lower:
            loc_slug = "london"
        elif "toronto" in loc_lower:
            loc_slug = "toronto"
        elif "sydney" in loc_lower:
            loc_slug = "sydney"
        elif "singapore" in loc_lower:
            loc_slug = "singapore"
        elif "bengaluru" in loc_lower or "bangalore" in loc_lower:
            loc_slug = "bengaluru"
        elif "gurugram" in loc_lower or "gurgaon" in loc_lower:
            loc_slug = "gurugram"
        elif "hyderabad" in loc_lower:
            loc_slug = "hyderabad"
        elif "pune" in loc_lower:
            loc_slug = "pune"
        else:
            # Fallback slugification
            loc_slug = re.sub(r'[^a-z0-9]+', '-', loc_lower).strip('-')

        return kw_slug, loc_slug

    def scrape(self, keyword, location, currency="USD", usd_rate=1.0, max_jobs=None):
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        jobs: List[Dict] = []

        try:
            kw_slug, loc_slug = self._get_slugs(keyword, location)
            url = f"https://wellfound.com/role/l/{kw_slug}/{loc_slug}"
            self.logger.info("Wellfound: loading %s", url)

            # Wellfound gates listings behind login — inject the session cookie
            # from the WELLFOUND_COOKIE secret. Missing cookie is warned by
            # load_cookies(); empty results with a cookie present means it expired.
            cookies = self.load_cookies("WELLFOUND_COOKIE", ".wellfound.com")
            page = StealthyFetcher.fetch(url, headless=True, network_idle=True, cookies=cookies)

            # Wellfound listings reside in result cards
            cards = page.css(
                "div[data-test='StartupResult'], "
                "div[class*='styles_result'], "
                "div.styles_result__"
            )
            if not cards:
                if cookies:
                    self.logger.warning(
                        "Wellfound: no job cards — WELLFOUND_COOKIE may be expired "
                        "(hit the login wall) or selectors changed."
                    )
                return self.validate_batch(jobs)

            self.logger.info("Wellfound: found %d cards", len(cards))

            for card in cards[:max_jobs]:
                try:
                    card_text = card.text or ""

                    # Company Name
                    company_el = card.css(
                        "h4, "
                        "span[class*='styles_companyName'], "
                        "div[class*='styles_name']"
                    )
                    company_name = clean_text(company_el[0].text) if company_el else None

                    # Job Link + Title
                    title_el = card.css("a[data-test='JobLink'], a[class*='styles_title'], a[href*='/jobs/']")
                    job_title = clean_text(title_el[0].text) if title_el else None
                    if not job_title:
                        # Fallback to parsing text for any link inside card
                        title_el = card.css("a")
                        job_title = clean_text(title_el[0].text) if title_el else None

                    if not job_title:
                        continue

                    job_link = url
                    if title_el:
                        href = title_el[0].attrib.get("href", "")
                        if href:
                            job_link = href if href.startswith("http") else f"https://wellfound.com{href}"

                    # Salary
                    salary = extract_salary_from_text(card_text, usd_rate)

                    # Remote
                    remote_type = "On-site"
                    text_lower = card_text.lower()
                    if "remote" in text_lower:
                        remote_type = "Remote"
                    elif "hybrid" in text_lower:
                        remote_type = "Hybrid"

                    # Location
                    loc_el = card.css("span[class*='styles_location'], span.location")
                    card_location = clean_text(loc_el[0].text) if loc_el else location

                    # Dedup
                    company_lower = (company_name or "").lower().strip()
                    title_lower   = (job_title or "").lower().strip()
                    loc_lower     = location.lower().strip()
                    dedup_key = hashlib.md5(
                        f"wellfound{company_lower}{title_lower}{loc_lower}".encode()
                    ).hexdigest()[:12]

                    job = {
                        "job_title":            job_title,
                        "company_name":         company_name,
                        "location":             card_location,
                        "salary":               salary,
                        "salary_currency":      currency,
                        "seniority_level":      infer_seniority(job_title, None),
                        "experience_required":  extract_experience(card_text),
                        "employment_type":      "Full-time",
                        "remote_type":          remote_type,
                        "industry":             None,
                        "education_required":   None,
                        "has_equity":           "equity" in text_lower or "stock" in text_lower or "rsu" in text_lower,
                        "has_bonus":            "bonus" in text_lower,
                        "has_remote_benefits":  remote_type in ("Remote", "Hybrid"),
                        "skills_required":      extract_skills(card_text),
                        "job_description":      f"Wellfound listing for {job_title} at {company_name}",
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
                        "Wellfound: scraped %d/%d — %s @ %s",
                        len(jobs), max_jobs, job_title, company_name,
                    )

                except Exception as card_err:
                    self.logger.debug("Wellfound: item error — %s", card_err)
                    continue

        except Exception as e:
            self.logger.error("Wellfound scraper failed: %s", e)

        return self.validate_batch(jobs)
