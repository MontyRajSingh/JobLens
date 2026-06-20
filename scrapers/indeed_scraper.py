"""
scrapers/indeed_scraper.py
---------------------------
Indeed job scraper. Inherits BaseScraper.

Uses Scrapling's StealthyFetcher to bypass Indeed's aggressive anti-bot
systems (CAPTCHAs, Cloudflare Turnstile).
"""

import re
import time
import random
import hashlib
from typing import Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from scrapling.fetchers import StealthyFetcher

from scrapers.base_scraper import BaseScraper
from utils.text_utils import (
    clean_text, extract_experience, extract_skills,
    infer_seniority, parse_indeed_metadata,
    is_faang, seniority_to_experience,
)
from utils.salary_utils import extract_salary_from_text
from config import INDEED_DOMAINS, COL_INDEX, MAX_JOBS_PER_SEARCH


class IndeedScraper(BaseScraper):
    SOURCE    = "Indeed"
    MAX_PAGES = 3

    def __init__(self):
        super().__init__()

    def scrape(self, keyword, location, currency="USD", usd_rate=1.0, max_jobs=None):
        if max_jobs is None:
            max_jobs = MAX_JOBS_PER_SEARCH

        base_url = INDEED_DOMAINS.get(currency, "https://www.indeed.com")
        jobs: List[Dict] = []
        collected = 0

        try:
            for page_num in range(self.MAX_PAGES):
                if collected >= max_jobs:
                    break

                url = (
                    f"{base_url}/jobs?"
                    f"q={quote_plus(keyword)}"
                    f"&l={quote_plus(location)}"
                    f"&sort=date"
                    f"&start={page_num * 15}"
                )
                self.logger.info("Indeed: loading page %d — %s", page_num, url)
                page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

                # Block detection
                page_text = (page.css("body::text").get() or "")
                if any(w in page_text.lower()[:3000] for w in ["captcha", "unusual traffic", "are you a robot"]):
                    self.logger.warning("Indeed: blocked on page %d", page_num)
                    continue

                cards = self._collect_cards(page, base_url)
                self.logger.info("Indeed: page %d — %d cards for '%s'", page_num, len(cards), keyword)

                if not cards:
                    break

                for card in cards:
                    if collected >= max_jobs:
                        break
                    try:
                        details = self._get_details(card, currency, usd_rate)
                        job = {**card, **details,
                               "currency": currency,
                               "source_website": self.SOURCE,
                               "is_faang": is_faang(card.get("company_name", "")),
                               "cost_of_living_index": COL_INDEX.get(location, 80)}
                        company = (job.get("company_name") or "").lower().strip()
                        title   = (job.get("job_title")    or "").lower().strip()
                        job["dedup_key"] = hashlib.md5(
                            f"{company}{title}{location.lower()}".encode()
                        ).hexdigest()[:12]
                        jobs.append(self.validate_job_record(job))
                        collected += 1
                        self.logger.info("Indeed: %d/%d — %s @ %s",
                                         collected, max_jobs,
                                         job.get("job_title", "?"),
                                         job.get("company_name", "?"))
                        time.sleep(random.uniform(1.5, 3.0))
                    except Exception as e:
                        self.logger.debug("Indeed: card error: %s", e)
        except Exception as e:
            self.logger.error("Indeed scraper failed: %s", e)

        return self.validate_batch(jobs)

    def _collect_cards(self, page, base_url: str) -> List[Dict]:
        # .job_seen_beacon is the confirmed working selector
        card_els = page.css(".job_seen_beacon")
        if not card_els:
            for sel in [".tapItem", "[data-jk]", ".resultContent"]:
                card_els = page.css(sel)
                if card_els:
                    break

        cards = []
        for el in card_els:
            try:
                # Title — span inside a.jcs-JobTitle
                title_el = el.css("h2.jobTitle a span, a.jcs-JobTitle span, h2 a span, h2 span")
                job_title = clean_text(title_el[0].text) if title_el else None
                if not job_title:
                    # fallback: text of the whole h2
                    h2 = el.css("h2.jobTitle, h2")
                    job_title = clean_text(h2[0].text) if h2 else None
                if not job_title:
                    continue

                # Link
                link_el = el.css("h2.jobTitle a, a.jcs-JobTitle, h2 a")
                job_link = None
                job_id   = None
                if link_el:
                    href = link_el[0].attrib.get("href", "")
                    if href and not href.startswith("http"):
                        href = urljoin(base_url, href)
                    job_link = href
                    jk = re.search(r"jk=([a-f0-9]+)", href)
                    if jk:
                        job_id = jk.group(1)
                # Also try data-jk on parent
                if not job_id:
                    job_id = el.attrib.get("data-jk")

                # Company
                company_el = el.css(
                    "[data-testid='company-name'], .companyName, "
                    "span[class*='companyName'], a[data-tn-element='companyName']"
                )
                company_name = clean_text(company_el[0].text) if company_el else None

                # Location
                loc_el = el.css(
                    "[data-testid='text-location'], .companyLocation, "
                    "div[class*='companyLocation']"
                )
                card_location = clean_text(loc_el[0].text) if loc_el else None

                # Salary on card
                sal_el = el.css(
                    ".salary-snippet-container, .salaryText, "
                    ".estimated-salary, [data-testid='attribute_snippet_testid']"
                )
                salary_raw = None
                if sal_el:
                    raw = clean_text(sal_el[0].text)
                    if raw and any(c in raw for c in ["$", "£", "€", "K", "k"]):
                        salary_raw = raw

                # Date
                date_el = el.css(".date, [data-testid='myJobsStateDate'], span.date")
                date_raw = None
                if date_el:
                    dt = clean_text(date_el[0].text)
                    if dt and any(w in dt.lower() for w in ["posted", "today", "ago", "just"]):
                        date_raw = dt

                # Employment type from snippets
                employment_type = None
                snippets = el.css(".attribute_snippet, [data-testid='attribute_snippet_testid']")
                for snip in snippets:
                    t = (snip.text or "").lower()
                    for etype in ["full-time", "part-time", "contract", "temporary", "internship"]:
                        if etype in t:
                            employment_type = etype.replace("-", " ").title()
                            break
                    if employment_type:
                        break

                cards.append({
                    "job_title":       job_title,
                    "company_name":    company_name,
                    "location":        card_location,
                    "salary":          salary_raw,
                    "employment_type": employment_type,
                    "job_link":        job_link,
                    "job_id":          job_id,
                    "date_posted_raw": date_raw,
                })
            except Exception as e:
                self.logger.debug("Indeed: card parse error — %s", e)
        return cards

    def _get_details(self, card: Dict, currency: str, usd_rate: float) -> Dict:
        details: Dict = {
            "salary":              None,
            "salary_currency":     currency,
            "seniority_level":     None,
            "experience_required": None,
            "employment_type":     card.get("employment_type"),
            "remote_type":         "On-site",
            "industry":            None,
            "education_required":  None,
            "has_equity":          False,
            "has_bonus":           False,
            "has_remote_benefits": False,
            "date_posted_raw":     card.get("date_posted_raw"),
            "applicant_count":     None,
            "skills_required":     None,
            "job_description":     None,
        }

        # Build card text for fallback extraction (when detail page is blocked)
        card_text = f"{card.get('job_title', '')} {card.get('company_name', '')} {card.get('salary', '')} {card.get('location', '')}".lower()

        # Get salary from card
        salary_raw = card.get("salary")
        if salary_raw:
            details["salary"] = extract_salary_from_text(salary_raw, usd_rate)

        job_link = card.get("job_link")
        if not job_link:
            return details

        try:
            page = StealthyFetcher.fetch(job_link, headless=True, network_idle=True)

            # Description - updated selectors
            description = None
            for sel in [
                ".jobsearch-JobComponent-description",
                ".jobsearch-jobDescriptionText",
                "#jobDescriptionText",
                "div[data-testid='jobDescriptionText']",
            ]:
                desc_els = page.css(sel)
                if desc_els:
                    # Use get_all_text() for nested content
                    text = desc_els[0].get_all_text() or desc_els[0].text or ""
                    text = clean_text(text)
                    if text and len(text) > 50:
                        description = text
                        details["job_description"] = description[:5000]
                        break

            # Salary: card → detail element → description scan
            salary_raw = card.get("salary")
            if salary_raw:
                details["salary"] = extract_salary_from_text(salary_raw, usd_rate)

            if not details["salary"]:
                for sel in ["#salaryInfoAndJobType",
                             "[data-testid='attribute_snippet_testid']",
                             ".jobsearch-JobMetadataHeader-item"]:
                    sal_els = page.css(sel)
                    if sal_els:
                        sal_text = clean_text(sal_els[0].text)
                        if sal_text and any(c in sal_text for c in ["$", "£", "€", "K", "k"]):
                            parsed = extract_salary_from_text(sal_text, usd_rate)
                            if parsed:
                                details["salary"] = parsed
                                break

            if not details["salary"] and description:
                details["salary"] = extract_salary_from_text(description, usd_rate)

            # Extract from description if available, otherwise fallback to card_text
            extract_from = description or card_text

            if extract_from:
                details["skills_required"]     = extract_skills(extract_from)
                details["experience_required"] = extract_experience(extract_from)
                meta = parse_indeed_metadata(extract_from)
                details["remote_type"]         = meta.get("remote_type", "On-site")
                details["education_required"]  = meta.get("education_required")
                details["has_equity"]          = meta.get("has_equity", False)
                details["has_bonus"]           = meta.get("has_bonus", False)
                if not details["employment_type"]:
                    details["employment_type"] = meta.get("employment_type")
                if not details["salary"]:
                    details["salary"] = extract_salary_from_text(extract_from, usd_rate)

            details["seniority_level"] = infer_seniority(card.get("job_title"))
            if details["remote_type"] in ("Remote", "Hybrid"):
                details["has_remote_benefits"] = True
            if not details["experience_required"] and details["seniority_level"]:
                details["experience_required"] = seniority_to_experience(details["seniority_level"])

        except Exception as e:
            self.logger.error("Indeed: detail page error for %s — %s", job_link, e)

        return details