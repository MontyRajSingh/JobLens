"""
scrapers/glassdoor_scraper.py
-------------------------------
Glassdoor job scraper. Inherits BaseScraper.

Uses Scrapling's StealthyFetcher to bypass Cloudflare.
Note: Glassdoor redirects to regional domain (e.g. glassdoor.co.in) based
on IP — this is expected. The DOM structure is identical across domains.
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
from config import MAX_JOBS_PER_SEARCH, COL_INDEX, GLASSDOOR_CITY_IDS


class GlassdoorScraper(BaseScraper):
    SOURCE = "Glassdoor"

    def __init__(self):
        super().__init__()

    def _build_url(self, keyword: str, location: str) -> str:
        city_id = GLASSDOOR_CITY_IDS.get(location)
        if city_id:
            return (
                f"https://www.glassdoor.com/Job/jobs.htm"
                f"?sc.keyword={quote_plus(keyword)}"
                f"&locT=C&locId={city_id}"
            )
        return (
            f"https://www.glassdoor.com/Job/jobs.htm"
            f"?sc.keyword={quote_plus(keyword)}"
            f"&locKeyword={quote_plus(location)}"
        )

    def scrape(self, keyword, location, currency="USD", usd_rate=1.0, max_jobs=None):
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        jobs: List[Dict] = []

        try:
            url = self._build_url(keyword, location)
            self.logger.info("Glassdoor: loading %s", url)
            page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

            # Confirmed card selector from live DOM inspection
            cards = page.css("li.JobsList_jobListItem__wjTHv")
            if not cards:
                for sel in ["li[data-test='jobListing']", "ul.JobsList_jobsList__lqjXs li",
                             "li[class*='JobsList_jobListItem']"]:
                    cards = page.css(sel)
                    if cards:
                        break

            if not cards:
                self.logger.warning("Glassdoor: no job cards found")
                return self.validate_batch(jobs)

            self.logger.info("Glassdoor: found %d cards", len(cards))

            for card in cards[:max_jobs]:
                try:
                    card_text = card.text or ""

                    # ── Title — anchor inside JobCard_jobTitle
                    title_el = card.css(
                        "a.JobCard_jobTitle__GLyJ1, "
                        "a[data-test='job-title'], "
                        "a[class*='jobTitle'], "
                        "div[class*='JobCard'] a"
                    )
                    job_title = clean_text(title_el[0].text) if title_el else None
                    if not job_title:
                        continue

                    # ── Link + Job ID
                    job_link = None
                    job_id   = None
                    if title_el:
                        href = title_el[0].attrib.get("href", "")
                        base_domain = "https://www.glassdoor.co.in" if "co.in" in (page.url or "") else "https://www.glassdoor.com"
                        job_link = href if href.startswith("http") else f"{base_domain}{href}"
                        id_match = re.search(r'jobListingId=(\d+)', job_link)
                        if not id_match:
                            id_match = re.search(r'-(\d+)\.htm', job_link)
                        if id_match:
                            job_id = id_match.group(1)

                    # ── Company — confirmed: span.EmployerProfile_compactEmployerName__9MGcV
                    company_el = card.css(
                        "span.EmployerProfile_compactEmployerName__9MGcV, "
                        "span[class*='compactEmployerName'], "
                        "div[class*='EmployerProfile'] span, "
                        "[data-test='emp-name']"
                    )
                    company_name = clean_text(company_el[0].text) if company_el else None

                    # ── Rating
                    rating_el = card.css(
                        "span.rating-single-star_RatingText__5fdjN, "
                        "span[class*='RatingText'], "
                        "[class*='rating']"
                    )
                    rating = clean_text(rating_el[0].text) if rating_el else None

                    # ── Location — JobCard_location
                    loc_el = card.css(
                        "div.JobCard_location__Ds1fM, "
                        "[data-test='emp-location'], "
                        "span[class*='location'], "
                        "div[class*='location']"
                    )
                    card_location = clean_text(loc_el[0].text) if loc_el else location

                    # ── Salary estimate — JobCard_salaryEstimate or salary containers
                    salary_el = card.css(
                        "div.JobCard_salaryEstimate__arV5J, "
                        "span[class*='salaryEstimate'], "
                        "div[class*='salaryEstimate'], "
                        "[data-test='detailSalary'], "
                        "[class*='salary']"
                    )
                    salary = None
                    if salary_el:
                        salary = extract_salary_from_text(salary_el[0].get_all_text() or salary_el[0].text, usd_rate)
                    # Fallback: scan full card text
                    if not salary:
                        salary = extract_salary_from_text(card.get_all_text() or card_text, usd_rate)

                    # ── Description snippet
                    desc_el = card.css(
                        "div.JobCard_jobDescriptionSnippet__l0exx, "
                        "div[class*='jobDescriptionSnippet'], "
                        "[class*='description']"
                    )
                    description = clean_text(desc_el[0].text) if desc_el else None

                    # ── Date posted
                    date_el = card.css(
                        "div.JobCard_listingAge__KPi3s, "
                        "[class*='listingAge'], "
                        "[data-test='job-age'], "
                        "span[class*='age']"
                    )
                    date_raw = clean_text(date_el[0].text) if date_el else None

                    # ── Remote detection
                    text_lower = card_text.lower()
                    remote_type = "On-site"
                    if "remote" in text_lower:
                        remote_type = "Remote"
                    elif "hybrid" in text_lower:
                        remote_type = "Hybrid"

                    # ── Dedup
                    company_lower = (company_name or "").lower().strip()
                    title_lower   = (job_title or "").lower().strip()
                    loc_lower     = location.lower().strip()
                    dedup_key = hashlib.md5(
                        f"glassdoor{company_lower}{title_lower}{loc_lower}".encode()
                    ).hexdigest()[:12]

                    # Build description with rating context
                    desc_text = description or f"Glassdoor listing for {job_title}"
                    if rating and company_name:
                        desc_text = f"{company_name} ({rating}★). {desc_text}"

                    job = {
                        "job_title":            job_title,
                        "company_name":         company_name,
                        "location":             card_location,
                        "salary":               salary,
                        "salary_currency":      currency,
                        "seniority_level":      infer_seniority(job_title, None),
                        "experience_required":  extract_experience(desc_text) if description else None,
                        "employment_type":      "Full-time",
                        "remote_type":          remote_type,
                        "industry":             None,
                        "education_required":   None,
                        "has_equity":           "equity" in text_lower or "stock" in text_lower,
                        "has_bonus":            "bonus" in text_lower,
                        "has_remote_benefits":  remote_type in ("Remote", "Hybrid"),
                        "skills_required":      extract_skills(desc_text) if description else None,
                        "job_description":      desc_text[:5000],
                        "job_link":             job_link,
                        "job_id":               job_id or dedup_key,
                        "source_website":       self.SOURCE,
                        "dedup_key":            dedup_key,
                        "is_faang":             is_faang(company_name or ""),
                        "cost_of_living_index": COL_INDEX.get(location, 80),
                        "date_posted_raw":      date_raw,
                        "applicant_count":      None,
                        "currency":             currency,
                    }

                    jobs.append(self.validate_job_record(job))
                    self.logger.info(
                        "Glassdoor: scraped %d/%d — %s @ %s (%s)",
                        len(jobs), max_jobs, job_title, company_name,
                        salary or "no salary",
                    )

                except Exception as e:
                    self.logger.debug("Glassdoor: card error — %s", e)
                    continue

        except Exception as e:
            self.logger.error("Glassdoor scraper failed: %s", e)

        return self.validate_batch(jobs)
