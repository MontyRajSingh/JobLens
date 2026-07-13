"""
scrapers/naukri_scraper.py
--------------------------
Naukri job scraper. Inherits BaseScraper.

Uses Scrapling's StealthyFetcher to query Naukri's internal job search API.
"""

import json
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


class NaukriScraper(BaseScraper):
    SOURCE = "Naukri"

    def __init__(self):
        super().__init__()

    def scrape(self, keyword, location, currency="INR", usd_rate=0.012, max_jobs=None):
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        jobs: List[Dict] = []

        try:
            # Build API URL
            # Note: Naukri's internal job search API v3
            api_url = (
                f"https://www.naukri.com/jobapi/v3/search"
                f"?keyword={quote_plus(keyword)}"
                f"&location={quote_plus(location)}"
                f"&pageNo=1"
                f"&noOfResults={max_jobs}"
                f"&urlType=search_by_keyword"
            )
            self.logger.info("Naukri: calling internal API %s", api_url)

            # Set headers to mimic a browser
            headers = {
                "appid": "109",
                "systemid": "109",
                "clientid": "d3skt0p",
                "accept": "application/json",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            # Naukri's search API requires an authenticated session — inject the
            # cookie from the NAUKRI_COOKIE secret. Missing cookie is warned by
            # load_cookies(); an empty body with a cookie present means it expired.
            cookies = self.load_cookies("NAUKRI_COOKIE", ".naukri.com")

            # Use StealthyFetcher to perform the request
            page = StealthyFetcher.fetch(api_url, headers=headers, headless=True, network_idle=True, cookies=cookies)

            # Since the response is JSON, parse page text
            content_text = page.text
            if not content_text:
                if cookies:
                    self.logger.warning(
                        "Naukri: empty response — NAUKRI_COOKIE may be expired "
                        "or the API rejected the session."
                    )
                return self.validate_batch(jobs)

            try:
                data = json.loads(content_text)
            except json.JSONDecodeError as e:
                self.logger.error("Naukri: failed to parse JSON response: %s", e)
                return self.validate_batch(jobs)

            job_listings = data.get("jobDetails", [])
            self.logger.info("Naukri: API returned %d jobs", len(job_listings))

            for item in job_listings[:max_jobs]:
                try:
                    job_title = clean_text(item.get("title"))
                    if not job_title:
                        continue

                    company_name = clean_text(item.get("companyName"))
                    job_id = clean_text(item.get("jobId"))

                    # Location
                    locations_list = item.get("placeholders", [])
                    job_location = location
                    if locations_list:
                        # Extract location label from list e.g. [{'label': 'Pune'}]
                        job_location = ", ".join(clean_text(loc.get("label")) for loc in locations_list if loc.get("label"))
                    
                    if not job_location:
                        job_location = location

                    # Salary
                    salary_raw = item.get("salaryPlaceholder", {}).get("label") or item.get("salary")
                    salary = None
                    if salary_raw:
                        salary = extract_salary_from_text(salary_raw, usd_rate)

                    # Experience
                    experience_raw = item.get("experiencePlaceholder", {}).get("label") or item.get("experience")
                    experience = clean_text(experience_raw)

                    # Skills
                    skills_list = item.get("tagsAndSkills", [])
                    skills = None
                    if skills_list:
                        skills = ", ".join(clean_text(str(s)) for s in skills_list if s)

                    # Job Link
                    href = item.get("jdURL", "")
                    job_link = href if href.startswith("http") else f"https://www.naukri.com{href}"

                    # Description Snippet
                    desc = clean_text(item.get("jobDescription") or item.get("jdPlaceholder"))
                    if not desc:
                        desc = f"Naukri listing for {job_title} at {company_name}"

                    # Dedup Key
                    company_lower = (company_name or "").lower().strip()
                    title_lower = (job_title or "").lower().strip()
                    loc_lower = location.lower().strip()
                    dedup_key = hashlib.md5(
                        f"naukri{company_lower}{title_lower}{loc_lower}".encode()
                    ).hexdigest()[:12]

                    # Remote arrangement
                    remote_type = "On-site"
                    desc_lower = desc.lower()
                    if "remote" in desc_lower or "work from home" in desc_lower:
                        remote_type = "Remote"
                    elif "hybrid" in desc_lower:
                        remote_type = "Hybrid"

                    job = {
                        "job_title":            job_title,
                        "company_name":         company_name,
                        "location":             job_location,
                        "salary":               salary,
                        "salary_currency":      currency,
                        "seniority_level":      infer_seniority(job_title, None),
                        "experience_required":  experience,
                        "employment_type":      "Full-time",
                        "remote_type":          remote_type,
                        "industry":             None,
                        "education_required":   None,
                        "has_equity":           False,
                        "has_bonus":            False,
                        "has_remote_benefits":  remote_type in ("Remote", "Hybrid"),
                        "skills_required":      skills,
                        "job_description":      desc[:5000],
                        "job_link":             job_link,
                        "job_id":               job_id or dedup_key,
                        "source_website":       self.SOURCE,
                        "dedup_key":            dedup_key,
                        "is_faang":             is_faang(company_name or ""),
                        "cost_of_living_index": COL_INDEX.get(location, 80),
                        "date_posted_raw":      item.get("postDuration"),
                        "applicant_count":      None,
                        "currency":             currency,
                    }

                    jobs.append(self.validate_job_record(job))
                    self.logger.info(
                        "Naukri: scraped %d/%d — %s @ %s",
                        len(jobs), max_jobs, job_title, company_name,
                    )

                except Exception as card_err:
                    self.logger.debug("Naukri: item error — %s", card_err)
                    continue

        except Exception as e:
            self.logger.error("Naukri scraper failed: %s", e)

        return self.validate_batch(jobs)
