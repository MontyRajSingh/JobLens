"""
scrapers/instahyre_scraper.py
-----------------------------
Instahyre job scraper. Inherits BaseScraper.

Uses Scrapling's StealthyFetcher to scrape the dynamic job search page.
"""

import re
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


def _node_text(el) -> str:
    """
    Return an element's full descendant text.

    Instahyre nests card text one level below the labelled div, so scrapling's
    element ``.text`` (direct text node only) yields whitespace. ``get_all_text``
    concatenates descendants; fall back to ``.text`` on older scrapling.
    """
    if el is None:
        return ""
    getter = getattr(el, "get_all_text", None)
    if callable(getter):
        return getter() or ""
    return el.text or ""


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

            # Instahyre renders each listing as an Angular ".employer-block"
            # card containing .employer-job-name / .employer-company-name /
            # .employer-locations / .job-skills sub-elements.
            cards = page.css("div.employer-block")
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
                    card_text = _node_text(card)

                    # Company Name
                    company_el = card.css("div.employer-company-name")
                    company_name = clean_text(_node_text(company_el[0])) if company_el else None

                    # Job Title — the .employer-job-name element is rendered as
                    # "Company - Role"; strip the leading company name so we keep
                    # just the role.
                    title_el = card.css("div.employer-job-name")
                    job_title = clean_text(_node_text(title_el[0])) if title_el else None
                    if job_title and company_name and job_title.lower().startswith(company_name.lower()):
                        stripped = re.sub(r"^[\s\-–—|]+", "", job_title[len(company_name):]).strip()
                        job_title = stripped or job_title
                    if not job_title:
                        continue

                    # Job Link — each card links to a "/job-<id>-..." detail page.
                    link_el = card.css("a[href*='/job-']") or card.css("a[href]")
                    job_link = url
                    if link_el:
                        href = link_el[0].attrib.get("href", "")
                        if href:
                            job_link = href if href.startswith("http") else f"https://www.instahyre.com{href}"

                    # Location — rendered as "Job available in <cities>"; drop the prefix.
                    loc_el = card.css("div.employer-locations")
                    card_location = clean_text(_node_text(loc_el[0])) if loc_el else None
                    if card_location:
                        card_location = re.sub(r"^\s*job available in\s*", "", card_location, flags=re.I).strip()
                    card_location = card_location or location

                    # Salary — Instahyre does not surface salary on the card.
                    salary = extract_salary_from_text(card_text, usd_rate)

                    # Skills — newline-separated tags; drop the "+N" show-more counters.
                    skills_el = card.css("div.job-skills")
                    skills = None
                    if skills_el:
                        tags = [clean_text(t) for t in _node_text(skills_el[0]).split("\n")]
                        tags = [t for t in tags if t and not re.fullmatch(r"\+\d+", t)]
                        skills = ", ".join(dict.fromkeys(tags)) or None

                    # Experience — not shown on the card; infer from card text if present.
                    experience = extract_experience(card_text)

                    # Dedup
                    company_lower = (company_name or "").lower().strip()
                    title_lower   = (job_title or "").lower().strip()
                    loc_lower     = location.lower().strip()
                    dedup_key = hashlib.md5(
                        f"instahyre{company_lower}{title_lower}{loc_lower}".encode()
                    ).hexdigest()[:12]

                    # Description — the card carries a short "employer-notes" blurb.
                    notes_el = card.css("div.employer-notes")
                    description = clean_text(_node_text(notes_el[0])) if notes_el else None
                    if not description:
                        description = f"Instahyre listing for {job_title} at {company_name}"

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
                        "job_description":      description[:5000],
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
