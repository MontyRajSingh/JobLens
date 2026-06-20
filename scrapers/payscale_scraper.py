"""
scrapers/payscale_scraper.py
-----------------------------
PayScale salary scraper. Inherits BaseScraper.

PayScale's research pages contain per-company salary data in a structured
format. We extract the median salary and fall back to company-specific data
from the page's internal API response embedded in __NEXT_DATA__.

Uses Scrapling's StealthyFetcher for JS rendering.
"""

import re
import json
import hashlib
from typing import Dict, List, Optional
from urllib.parse import quote

from scrapling.fetchers import StealthyFetcher

from scrapers.base_scraper import BaseScraper
from utils.text_utils import infer_seniority, is_faang
from utils.salary_utils import extract_salary_from_text
from config import MAX_JOBS_PER_SEARCH, COL_INDEX


class PayScaleScraper(BaseScraper):
    SOURCE = "PayScale"

    def __init__(self):
        super().__init__()

    def scrape(self, keyword, location, currency="USD", usd_rate=1.0, max_jobs=None):
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        jobs: List[Dict] = []

        try:
            formatted_keyword = keyword.strip().replace(" ", "_").title()
            url = f"https://www.payscale.com/research/US/Job={quote(formatted_keyword, safe='')}/Salary"
            self.logger.info("PayScale: loading %s", url)

            page = StealthyFetcher.fetch(url, headless=True, wait_until="load")

            # ── Try to extract structured data from __NEXT_DATA__ first
            next_data_el = page.css("script#__NEXT_DATA__::text")
            company_salaries = []
            median_salary_str = None

            if next_data_el:
                try:
                    data = json.loads(next_data_el.get())
                    # Navigate into common PayScale data paths
                    props = data.get("props", {}).get("pageProps", {})
                    # Try "salaryData" or "jobData"
                    salary_data = props.get("salaryData") or props.get("jobData") or {}
                    median = salary_data.get("nationalSalaryMedian") or salary_data.get("medianPay")
                    if median:
                        median_salary_str = f"${int(median):,} USD/yr"
                        self.logger.info("PayScale: median from JSON: %s", median_salary_str)
                    # Per-company breakdown
                    companies = salary_data.get("companySalaries") or []
                    for c in companies:
                        name = c.get("companyName") or c.get("name")
                        pay  = c.get("medianSalary") or c.get("salary")
                        if name and pay:
                            company_salaries.append({"company": name, "salary": int(pay)})
                except Exception as e:
                    self.logger.debug("PayScale: __NEXT_DATA__ parse failed: %s", e)

            # ── Fallback 1: CSS selector for median salary display
            if not median_salary_str:
                for sel in [
                    "span.paycharts__value",
                    "[class*='paycharts__value']",
                    "[class*='salary-value']",
                    "span[class*='pay-value']",
                    "div[class*='salary'] span",
                ]:
                    el = page.css(sel)
                    if el:
                        text = clean_text(el[0].text)
                        if text:
                            parsed = extract_salary_from_text(text, usd_rate)
                            if parsed:
                                median_salary_str = parsed
                                self.logger.info("PayScale: median from CSS '%s': %s", sel, parsed)
                                break

            # ── Fallback 2: scan full page text for salary patterns
            if not median_salary_str:
                page_text = page.css("body::text").get() or ""
                # Look for patterns like "median salary of $120,000"
                m = re.search(r'median\s+(?:salary|pay)(?:\s+of)?\s+\$?([\d,]+)', page_text, re.I)
                if m:
                    amount = int(m.group(1).replace(",", ""))
                    if 20_000 < amount < 1_000_000:
                        median_salary_str = f"${amount:,} USD/yr"
                        self.logger.info("PayScale: median from text scan: %s", median_salary_str)

            # ── Fallback 3: CSS for per-company rows on the page
            if not company_salaries:
                # PayScale renders employer rows with salary averages
                company_rows = page.css(
                    "li[class*='employer'], div[class*='employer-row'], "
                    "tr[class*='employer'], [class*='company-salary-row']"
                )
                for row in company_rows:
                    row_text = row.text or ""
                    # Pattern: "Company Name ... $123,456"
                    salary_match = re.search(r'\$([\d,]+)', row_text)
                    if not salary_match:
                        continue
                    # Company name: first meaningful text chunk before the dollar sign
                    name_match = re.match(r'^([A-Za-z][^$\n]{3,60}?)\s+\$', row_text.strip())
                    company_nm = name_match.group(1).strip() if name_match else None
                    if not company_nm:
                        # Try fetching from a link within the row
                        link_el = row.css("a")
                        if link_el:
                            company_nm = clean_text(link_el[0].text)
                    if company_nm:
                        salary_val = int(salary_match.group(1).replace(",", ""))
                        if 20_000 < salary_val < 1_000_000:
                            company_salaries.append({"company": company_nm, "salary": salary_val})

            self.logger.info(
                "PayScale: median=%s, %d per-company entries",
                median_salary_str, len(company_salaries)
            )

            # ── Build job records from per-company data
            seen = set()
            for entry in company_salaries[:max_jobs]:
                company_name = entry["company"]
                if company_name in seen:
                    continue
                seen.add(company_name)

                salary_usd = f"${entry['salary']:,} USD/yr"
                company_lower = company_name.lower().strip()
                title_lower   = keyword.lower().strip()
                loc_lower     = location.lower().strip()
                dedup_key = hashlib.md5(
                    f"payscale{company_lower}{title_lower}{loc_lower}".encode()
                ).hexdigest()[:12]

                job = {
                    "job_title":            keyword.title(),
                    "company_name":         company_name,
                    "location":             location,
                    "salary":               salary_usd,
                    "salary_currency":      currency,
                    "seniority_level":      infer_seniority(keyword, None),
                    "experience_required":  None,
                    "employment_type":      "Full-time",
                    "remote_type":          "On-site",
                    "industry":             None,
                    "education_required":   None,
                    "has_equity":           False,
                    "has_bonus":            False,
                    "has_remote_benefits":  False,
                    "skills_required":      None,
                    "job_description":      f"PayScale average salary for {keyword} at {company_name}",
                    "job_link":             url,
                    "job_id":               dedup_key,
                    "source_website":       self.SOURCE,
                    "dedup_key":            dedup_key,
                    "is_faang":             is_faang(company_name),
                    "cost_of_living_index": COL_INDEX.get(location, 80),
                    "date_posted_raw":      None,
                    "applicant_count":      None,
                    "currency":             currency,
                }
                jobs.append(self.validate_job_record(job))
                self.logger.info("PayScale: %s @ %s (%s)", keyword.title(), company_name, salary_usd)

            # ── If no per-company data, emit single median record
            if not jobs and median_salary_str:
                dedup_key = hashlib.md5(
                    f"payscale{keyword.lower()}{location.lower()}".encode()
                ).hexdigest()[:12]
                job = {
                    "job_title":            keyword.title(),
                    "company_name":         "Industry Average (PayScale)",
                    "location":             location,
                    "salary":               median_salary_str,
                    "salary_currency":      currency,
                    "seniority_level":      infer_seniority(keyword, None),
                    "experience_required":  None,
                    "employment_type":      "Full-time",
                    "remote_type":          "On-site",
                    "industry":             None,
                    "education_required":   None,
                    "has_equity":           False,
                    "has_bonus":            False,
                    "has_remote_benefits":  False,
                    "skills_required":      None,
                    "job_description":      f"PayScale national median salary for {keyword}: {median_salary_str}",
                    "job_link":             url,
                    "job_id":               dedup_key,
                    "source_website":       self.SOURCE,
                    "dedup_key":            dedup_key,
                    "is_faang":             False,
                    "cost_of_living_index": COL_INDEX.get(location, 80),
                    "date_posted_raw":      None,
                    "applicant_count":      None,
                    "currency":             currency,
                }
                jobs.append(self.validate_job_record(job))
                self.logger.info("PayScale: median fallback: %s", median_salary_str)

        except Exception as e:
            self.logger.error("PayScale scraper failed: %s", e)

        return self.validate_batch(jobs)


def clean_text(text):
    if not text:
        return None
    cleaned = " ".join(str(text).split()).strip()
    return cleaned if cleaned else None
