"""
salary_utils.py — Salary parsing and currency-conversion utilities.

Handles diverse salary formats ($120k, £60,000, €70k, ₹12 LPA, hourly,
monthly, ranges) and normalises them to annual USD strings.

Provides three layers of extraction:
1. parse_salary_to_usd — parse a single raw salary string
2. extract_salary_from_text — regex scan free-form text for salary patterns
3. extract_salary_from_page — scrape salary from a Selenium-driven page via CSS selectors
"""

import re
import logging
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _parse_number(raw: str) -> Optional[float]:
    """Strip formatting and convert a numeric string to float."""
    if not raw:
        return None
    cleaned = raw.replace(",", "").replace(" ", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _annualise(amount: float, period: str) -> float:
    """Convert hourly/monthly amounts to annual."""
    period = period.lower() if period else ""
    if "hour" in period or "hr" in period:
        return amount * 2080
    if "month" in period:
        return amount * 12
    if "week" in period:
        return amount * 52
    if "day" in period:
        return amount * 260
    return amount


def _format_usd(amount: float) -> Optional[str]:
    """Format a numeric salary to '$X,XXX USD/yr'. Returns None if out of range."""
    if amount < 5_000 or amount > 5_000_000:
        return None
    return f"${amount:,.0f} USD/yr"


# ──────────────────────────────────────────────
# Core: parse a single raw salary string
# ──────────────────────────────────────────────

def parse_salary_to_usd(raw: str, usd_rate: float = 1.0) -> Optional[str]:
    """
    Parse a raw salary string and convert to annual USD.

    Handles:
    - $120k, £60,000, €70k, ₹12 LPA
    - Ranges like "$80,000 - $120,000"
    - Hourly ($50/hr × 2080), monthly ($5,000/month × 12)
    - LPA (× 100,000) for Indian salaries

    Args:
        raw: Raw salary string.
        usd_rate: Multiplier to convert local currency to USD.

    Returns:
        Formatted string like "$120,000 USD/yr" or None if invalid.
    """
    if not raw:
        return None
    text = str(raw).strip()

    # Detect period for annualisation
    period = ""
    period_match = re.search(r"(?:per|/)\s*(hour|hr|month|week|day|year|annum)", text, re.IGNORECASE)
    if period_match:
        period = period_match.group(1)

    # Handle LPA / lakhs (Indian format)
    lpa_match = re.search(r"([\d,.]+)\s*(?:[-–to]+\s*([\d,.]+)\s*)?(?:LPA|CTC|lakhs?|lacs?)", text, re.IGNORECASE)
    if lpa_match:
        low = _parse_number(lpa_match.group(1))
        high = _parse_number(lpa_match.group(2)) if lpa_match.group(2) else None
        if low is not None:
            amount = ((low + high) / 2 if high else low) * 100_000
            return _format_usd(amount * usd_rate)

    # Handle "k" suffix
    text_k = re.sub(r"(\d)\s*[kK]", lambda m: m.group(1) + "000", text)

    # Extract numbers (with possible range)
    numbers = re.findall(r"[\d,]+\.?\d*", text_k)
    if not numbers:
        return None

    values = [_parse_number(n) for n in numbers[:2]]
    values = [v for v in values if v is not None and v > 0]
    if not values:
        return None

    amount = sum(values) / len(values)  # midpoint of range
    amount = _annualise(amount, period)
    return _format_usd(amount * usd_rate)


# ──────────────────────────────────────────────
# Extract salary from free-form text
# ──────────────────────────────────────────────

def extract_salary_from_text(text: str, usd_rate: float = 1.0) -> Optional[str]:
    """
    Scan free-form text for salary patterns and return the first match as USD.

    Checks 9 regex patterns covering £, €, $, USD/CAD/AUD/SGD keyword formats,
    Indian LPA/CTC/lakhs, per-year, per-month, and hourly patterns.

    Args:
        text: Free-form text (job description, salary snippet, etc.).
        usd_rate: Currency-to-USD multiplier.

    Returns:
        Formatted USD salary string or None.
    """
    if not text:
        return None
    text = str(text)

    patterns = [
        # £ GBP
        r"£\s*([\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*£?\s*[\d,]+\.?\d*\s*[kK]?)?(?:\s*(?:per|/)\s*(?:year|annum|month|hour|hr))?)",
        # € EUR
        r"€\s*([\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*€?\s*[\d,]+\.?\d*\s*[kK]?)?(?:\s*(?:per|/)\s*(?:year|annum|month|hour|hr))?)",
        # $ USD
        r"\$\s*([\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*\$?\s*[\d,]+\.?\d*\s*[kK]?)?(?:\s*(?:per|/)\s*(?:year|annum|month|hour|hr))?)",
        # Currency keyword (USD, CAD, AUD, SGD)
        r"(?:USD|CAD|AUD|SGD)\s*([\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*[\d,]+\.?\d*\s*[kK]?)?)",
        # Indian LPA/CTC
        r"([\d,.]+\s*(?:[-–to]+\s*[\d,.]+\s*)?(?:LPA|CTC|lakhs?|lacs?))",
        # Per year / annum
        r"([\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*[\d,]+\.?\d*\s*[kK]?)?\s*(?:per|/)\s*(?:year|annum))",
        # Per month
        r"([\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*[\d,]+\.?\d*\s*[kK]?)?\s*(?:per|/)\s*month)",
        # Per hour
        r"([\d,]+\.?\d*\s*(?:[-–to]+\s*[\d,]+\.?\d*)?\s*(?:per|/)\s*(?:hour|hr))",
        # AED (UAE)
        r"AED\s*([\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*[\d,]+\.?\d*\s*[kK]?)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result = parse_salary_to_usd(match.group(0), usd_rate)
            if result:
                return result

    return None


# ──────────────────────────────────────────────
# Extract salary from Selenium page
# ──────────────────────────────────────────────

def extract_salary_from_page(driver, usd_rate: float = 1.0) -> Optional[str]:
    """
    3-layer salary extraction from a Selenium-driven page:
    1. CSS selectors targeting common salary elements
    2. Insight/span elements with salary-related classes
    3. Full-page BeautifulSoup scan

    Args:
        driver: Selenium WebDriver with a loaded page.
        usd_rate: Currency-to-USD multiplier.

    Returns:
        Formatted USD salary string or None.
    """
    from selenium.webdriver.common.by import By

    # Layer 1: CSS selectors for salary elements
    salary_selectors = [
        "#salaryInfoAndJobType",
        ".salary-snippet-container",
        "[data-test='detailSalary']",
        ".salaryEstimate",
        ".css-1bluz6i",
        ".jobsearch-JobMetadataHeader-item",
        ".salary-estimate",
        ".compensation__salary",
    ]

    for selector in salary_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                text = el.text.strip()
                if text:
                    result = extract_salary_from_text(text, usd_rate)
                    if result:
                        logger.debug("Salary found via CSS '%s': %s", selector, result)
                        return result
        except Exception:
            continue

    # Layer 2: Insight span elements
    try:
        spans = driver.find_elements(By.CSS_SELECTOR, "span")
        for span in spans:
            try:
                text = span.text.strip()
                if text and re.search(r"[\$£€₹]|salary|compensation|LPA", text, re.IGNORECASE):
                    result = extract_salary_from_text(text, usd_rate)
                    if result:
                        logger.debug("Salary found via span scan: %s", result)
                        return result
            except Exception:
                continue
    except Exception:
        pass

    # Layer 3: BeautifulSoup full-page scan
    try:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_text = soup.get_text(separator=" ", strip=True)
        result = extract_salary_from_text(page_text, usd_rate)
        if result:
            logger.debug("Salary found via BS4 page scan: %s", result)
            return result
    except Exception:
        pass

    return None
