"""
scrapers/ziprecruiter_scraper.py
---------------------------------
ZipRecruiter job scraper. Inherits BaseScraper.

Uses Scrapling's StealthyFetcher for anti-bot bypass.
Filters out promoted "Be Seen First" ad cards (identified by <h3> presence).
Deduplicates the duplicate card+detail-panel pairs ZipRecruiter renders.
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


class ZipRecruiterScraper(BaseScraper):
    SOURCE = "ZipRecruiter"

    def __init__(self):
        super().__init__()

    def scrape(self, keyword, location, currency="USD", usd_rate=1.0, max_jobs=None):
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        jobs: List[Dict] = []

        try:
            url = (
                f"https://www.ziprecruiter.com/jobs-search"
                f"?search={quote_plus(keyword)}"
                f"&location={quote_plus(location)}"
            )
            self.logger.info("ZipRecruiter: loading %s", url)
            page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

            # Each job appears as an <article> — confirmed from live DOM inspection.
            # ZipRecruiter renders each job TWICE (card + expanded detail panel),
            # so we deduplicate by title.
            cards = page.css("article[class*='relative flex flex-col']")
            if not cards:
                cards = page.css("article")

            if not cards:
                self.logger.warning("ZipRecruiter: no job cards found")
                return self.validate_batch(jobs)

            self.logger.info("ZipRecruiter: found %d articles", len(cards))
            seen_titles: set = set()

            for card in cards:
                if len(jobs) >= max_jobs:
                    break
                try:
                    # ── Ad cards have <h3> ("Be Seen First for this job") — skip them
                    if card.css("h3"):
                        continue

                    card_text = card.text or ""

                    # ── Title — always in <h2>
                    h2 = card.css("h2")
                    job_title = clean_text(h2[0].text) if h2 else None
                    if not job_title:
                        continue

                    # Deduplicate the duplicated card+panel pairs
                    if job_title in seen_titles:
                        continue
                    seen_titles.add(job_title)

                    # ── Company — <a> with /co/ in href
                    company_name = None
                    for a_el in card.css("a"):
                        if "/co/" in a_el.attrib.get("href", ""):
                            company_name = clean_text(a_el.text)
                            break

                    # ── Location — <a> with /jobs-search?location= in href
                    card_location = location
                    for a_el in card.css("a"):
                        if "location=" in a_el.attrib.get("href", "") and "/jobs-search" in a_el.attrib.get("href", ""):
                            card_location = clean_text(a_el.text) or location
                            break

                    # ── Job link — <a> with /k/ in href (direct job URL)
                    job_link = None
                    for a_el in card.css("a"):
                        href = a_el.attrib.get("href", "")
                        if "/k/" in href:
                            job_link = href if href.startswith("http") else f"https://www.ziprecruiter.com{href}"
                            break
                    # Fallback: any job-listing link
                    if not job_link:
                        for a_el in card.css("a"):
                            href = a_el.attrib.get("href", "")
                            if href.startswith("/"):
                                job_link = f"https://www.ziprecruiter.com{href}"
                                break

                    # ── Salary - try multiple selectors + full card text
                    salary = None
                    for sel in ["[class*='salary']", "[class*='compensation']",
                                "p[class*='text-success']", "span[class*='pay']",
                                "[class*='Salary']", "[class*='Compensation']"]:
                        sal_els = card.css(sel)
                        if sal_els:
                            sal_text = sal_els[0].get_all_text() or sal_els[0].text or ""
                            salary = extract_salary_from_text(sal_text, usd_rate)
                            if salary:
                                break
                    # Also scan full card text for salary patterns
                    if not salary:
                        salary = extract_salary_from_text(card_text, usd_rate)

                    # ── Description snippet - use get_all_text() for nested content
                    desc_el = card.css(
                        "p[class*='text-body'], [class*='snippet'], [class*='description'], "
                        "[class*='Summary'], [class*='snippet']"
                    )
                    description = None
                    if desc_el:
                        desc_text = desc_el[0].get_all_text() or desc_el[0].text or ""
                        description = clean_text(desc_text)
                    if not description:
                        description = clean_text(card_text[:500])

                    # ── Extract skills and experience from full card text
                    full_text = description or card_text
                    if not full_text:
                        full_text = f"{job_title} {company_name or ''}".lower()

                    # ── Remote detection
                    text_lower = card_text.lower()
                    remote_type = "On-site"
                    if "remote" in text_lower:
                        remote_type = "Remote"
                    elif "hybrid" in text_lower:
                        remote_type = "Hybrid"

                    # ── Dedup key
                    dedup_key = hashlib.md5(
                        f"{(company_name or '').lower()}{(job_title or '').lower()}{location.lower()}".encode()
                    ).hexdigest()[:12]

                    job = {
                        "job_title":            job_title,
                        "company_name":         company_name,
                        "location":             card_location,
                        "salary":               salary,
                        "salary_currency":      currency,
                        "seniority_level":      infer_seniority(job_title, None),
                        "experience_required":  extract_experience(full_text) if full_text else None,
                        "employment_type":      "Full-time",
                        "remote_type":          remote_type,
                        "industry":             None,
                        "education_required":   None,
                        "has_equity":           "equity" in text_lower or "stock" in text_lower,
                        "has_bonus":            "bonus" in text_lower or "incentive" in text_lower,
                        "has_remote_benefits":  remote_type in ("Remote", "Hybrid"),
                        "skills_required":      extract_skills(full_text) if full_text else None,
                        "job_description":      (description or card_text)[:5000] if (description or card_text) else None,
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
                        "ZipRecruiter: %d/%d — %s @ %s",
                        len(jobs), max_jobs, job_title, company_name,
                    )

                except Exception as e:
                    self.logger.debug("ZipRecruiter: card error — %s", e)
                    continue

        except Exception as e:
            self.logger.error("ZipRecruiter scraper failed: %s", e)

        return self.validate_batch(jobs)
