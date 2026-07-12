"""
scrapers/ — Job scraper package.

Exports all scraper classes for convenient importing:
- BaseScraper: Abstract base class
- IndeedScraper: Indeed multi-page scraper (StealthyFetcher)
- LevelsFyiScraper: Levels.fyi tech salary scraper (Fetcher/HTTP)
- PayScaleScraper: PayScale per-company salary scraper (StealthyFetcher)
- ZipRecruiterScraper: ZipRecruiter job listing scraper (StealthyFetcher)
- LinkedInScraper: LinkedIn public job search scraper (StealthyFetcher)
- NaukriScraper, InstahyreScraper, WellfoundScraper: additional source adapters
"""

from scrapers.base_scraper import BaseScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.levelsfyi_scraper import LevelsFyiScraper
from scrapers.payscale_scraper import PayScaleScraper
from scrapers.ziprecruiter_scraper import ZipRecruiterScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.naukri_scraper import NaukriScraper
from scrapers.instahyre_scraper import InstahyreScraper
from scrapers.wellfound_scraper import WellfoundScraper

__all__ = [
    "BaseScraper",
    "IndeedScraper",
    "LevelsFyiScraper",
    "PayScaleScraper",
    "ZipRecruiterScraper",
    "LinkedInScraper",
    "NaukriScraper",
    "InstahyreScraper",
    "WellfoundScraper",
]
