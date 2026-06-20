"""
scrapers/linkedin_scraper.py
------------------------------
LinkedIn job scraper. Inherits BaseScraper.

Scrapes public job search results from LinkedIn without requiring login.
LinkedIn's guest job search exposes job cards with title, company,
location, and sometimes salary data. Detail pages are also accessible
for public listings.

Uses Scrapling's StealthyFetcher to bypass LinkedIn's anti-bot protections.
"""

import re
import time
import random
import hashlib
from typing import Dict, List
from urllib.parse import quote_plus

from scrapling.fetchers import StealthyFetcher

from scrapers.base_scraper import BaseScraper
from utils.text_utils import (
    clean_text,
    extract_experience,
    extract_skills,
    infer_seniority,
    parse_linkedin_metadata,
    is_faang,
    seniority_to_experience,
)
from utils.salary_utils import extract_salary_from_text
from config import MAX_JOBS_PER_SEARCH, COL_INDEX


class LinkedInScraper(BaseScraper):
    """
    LinkedIn job scraper.

    Scrapes public LinkedIn job search results. Guest access exposes
    job cards with title, company, location, and posting date.
    Detail pages provide full descriptions, salary (when shown),
    seniority level, employment type, and industry metadata.
    """

    SOURCE = "LinkedIn"

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

        jobs: List[Dict] = []

        try:
            # LinkedIn guest job search URL (past week, sorted by date)
            url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={quote_plus(keyword)}"
                f"&location={quote_plus(location)}"
                f"&f_TPR=r604800"
                f"&sortBy=DD"
            )
            self.logger.info("LinkedIn: loading %s", url)

            page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

            # LinkedIn guest search card selectors
            card_selectors = [
                "div.base-card",
                "li.jobs-search__results-list-item",
                "div.job-search-card",
                "ul.jobs-search__results-list li",
            ]

            cards = []
            for sel in card_selectors:
                cards = page.css(sel)
                if cards:
                    self.logger.info("LinkedIn: found %d cards with '%s'", len(cards), sel)
                    break

            if not cards:
                self.logger.warning("LinkedIn: no job cards found")
                return self.validate_batch(jobs)

            for i, card in enumerate(cards[:max_jobs]):
                try:
                    # ── Title (h3 with the job title text)
                    title_el = card.css("h3.base-search-card__title")
                    if not title_el:
                        title_el = card.css("h3")
                    job_title = clean_text(title_el[0].text) if title_el else None
                    if not job_title:
                        continue

                    # ── Company (text is inside a nested <a> within <h4>)
                    company_el = card.css("a.hidden-nested-link")
                    if not company_el:
                        company_el = card.css("h4.base-search-card__subtitle a")
                    if not company_el:
                        company_el = card.css("h4 a")
                    company_name = clean_text(company_el[0].text) if company_el else None

                    # ── Location
                    loc_el = card.css("span.job-search-card__location")
                    if not loc_el:
                        loc_el = card.css("span.base-search-card__metadata")
                    card_location = clean_text(loc_el[0].text) if loc_el else location

                    # ── Link
                    link_el = card.css("a.base-card__full-link")
                    if not link_el:
                        link_el = card.css("a[href*='/jobs/view/']")
                    job_link = None
                    job_id = None
                    if link_el:
                        href = link_el[0].attrib.get("href", "")
                        job_link = href if href.startswith("http") else f"https://www.linkedin.com{href}"

                    # ── Job ID from data-entity-urn attribute
                    urn = card.attrib.get("data-entity-urn", "")
                    urn_match = re.search(r"jobPosting:(\d+)", urn)
                    if urn_match:
                        job_id = urn_match.group(1)
                    elif job_link:
                        id_match = re.search(r'-(\d+)\?', job_link)
                        if id_match:
                            job_id = id_match.group(1)

                    # ── Date
                    date_el = card.css("time.job-search-card__listdate, time")
                    date_raw = None
                    if date_el:
                        date_raw = date_el[0].attrib.get("datetime") or clean_text(date_el[0].text)

                    # ── Salary from card (LinkedIn sometimes shows this)
                    salary_el = card.css(
                        "span.job-search-card__salary-info, "
                        "[class*='salary']"
                    )
                    salary = None
                    if salary_el:
                        salary = extract_salary_from_text(salary_el[0].text, usd_rate)

                    # ── Fetch detail page for description
                    description = None
                    seniority_raw = None
                    employment_type = None
                    industry = None
                    remote_type = "On-site"
                    education_required = None
                    has_equity = False
                    has_bonus = False

                    if job_link:
                        try:
                            time.sleep(random.uniform(1.5, 3.0))
                            detail_page = StealthyFetcher.fetch(
                                job_link, headless=True, network_idle=True
                            )

                            # Description
                            desc_el = detail_page.css(
                                "div.description__text, "
                                "div.show-more-less-html__markup, "
                                "section.description div"
                            )
                            if desc_el:
                                description = clean_text(desc_el[0].text)
                                if description:
                                    description = description[:5000]

                                    # Parse LinkedIn metadata block
                                    meta = parse_linkedin_metadata(description)
                                    seniority_raw = meta.get("seniority_raw")
                                    employment_type = meta.get("employment_type")
                                    industry = meta.get("industry")
                                    remote_type = meta.get("remote_type", "On-site")
                                    education_required = meta.get("education_required")
                                    has_equity = meta.get("has_equity", 0)
                                    has_bonus = meta.get("has_bonus", 0)

                            # Salary from detail page
                            if not salary:
                                sal_el = detail_page.css(
                                    "div.salary, "
                                    "[class*='compensation'], "
                                    "[class*='salary']"
                                )
                                if sal_el:
                                    salary = extract_salary_from_text(sal_el[0].text, usd_rate)

                            # Last resort: scan description
                            if not salary and description:
                                salary = extract_salary_from_text(description, usd_rate)

                        except Exception as e:
                            self.logger.debug("LinkedIn: detail page error — %s", e)

                    # Seniority
                    seniority_level = infer_seniority(job_title, seniority_raw)

                    # ── Dedup — use job_id if available, else title+company+location
                    company_lower = (company_name or "").lower().strip()
                    title_lower = (job_title or "").lower().strip()
                    loc_lower = location.lower().strip()
                    dedup_key = hashlib.md5(
                        f"linkedin{job_id or ''}{company_lower}{title_lower}{loc_lower}".encode()
                    ).hexdigest()[:12]

                    job = {
                        "job_title": job_title,
                        "company_name": company_name,
                        "location": card_location,
                        "salary": salary,
                        "salary_currency": currency,
                        "seniority_level": seniority_level,
                        "experience_required": (
                            extract_experience(description) if description
                            else seniority_to_experience(seniority_level)
                        ),
                        "employment_type": employment_type,
                        "remote_type": remote_type,
                        "industry": industry,
                        "education_required": education_required,
                        "has_equity": has_equity,
                        "has_bonus": has_bonus,
                        "has_remote_benefits": remote_type in ("Remote", "Hybrid"),
                        "skills_required": extract_skills(description) if description else None,
                        "job_description": description,
                        "job_link": job_link,
                        "job_id": job_id or dedup_key,
                        "source_website": self.SOURCE,
                        "dedup_key": dedup_key,
                        "is_faang": is_faang(company_name or ""),
                        "cost_of_living_index": COL_INDEX.get(location, 80),
                        "date_posted_raw": date_raw,
                        "applicant_count": None,
                        "currency": currency,
                    }

                    jobs.append(self.validate_job_record(job))
                    self.logger.info(
                        "LinkedIn: scraped %d/%d — %s @ %s (%s)",
                        i + 1, max_jobs, job_title, company_name,
                        salary or "no salary",
                    )

                except Exception as e:
                    self.logger.debug("LinkedIn: card parse error — %s", e)
                    continue

        except Exception as e:
            self.logger.error("LinkedIn scraper failed: %s", e)

        return self.validate_batch(jobs)
