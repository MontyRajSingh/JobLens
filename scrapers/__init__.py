"""
scrapers/ — Job scraper package.

Exports all scraper classes for convenient importing:
- BaseScraper: Abstract base class
- IndeedScraper: Indeed multi-page scraper
- LevelsFyiScraper: Levels.fyi tech salary scraper (JSON extraction)
- PayScaleScraper: PayScale per-company salary scraper
- ZipRecruiterScraper: ZipRecruiter job listing scraper
"""

from scrapers.base_scraper import BaseScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.levelsfyi_scraper import LevelsFyiScraper
from scrapers.payscale_scraper import PayScaleScraper
from scrapers.ziprecruiter_scraper import ZipRecruiterScraper

__all__ = [
    "BaseScraper",
    "IndeedScraper",
    "LevelsFyiScraper",
    "PayScaleScraper",
    "ZipRecruiterScraper",
]
