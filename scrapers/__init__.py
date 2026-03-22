"""
scrapers/ — Job scraper package.

Exports all scraper classes for convenient importing:
- BaseScraper: Abstract base class
- LinkedInScraper: LinkedIn public search scraper
- IndeedScraper: Indeed multi-page scraper
- GlassdoorScraper: Glassdoor scraper with optional login
"""

from scrapers.base_scraper import BaseScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.glassdoor_scraper import GlassdoorScraper

__all__ = ["BaseScraper", "LinkedInScraper", "IndeedScraper", "GlassdoorScraper"]
