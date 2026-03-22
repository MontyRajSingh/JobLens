"""
text_utils.py — Shared text-processing utilities for job data extraction.

Functions for cleaning text, extracting experience levels, inferring seniority,
extracting skills, and parsing platform-specific metadata blocks from LinkedIn
and Indeed job descriptions.

All constants (SKILL_LIST, FAANG, SENIORITY_FROM_LINKEDIN) are imported from config.py.
"""

import re
import logging
from typing import Optional, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import SKILL_LIST, FAANG, SENIORITY_FROM_LINKEDIN

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Basic text cleaning
# ──────────────────────────────────────────────

def clean_text(text: str) -> Optional[str]:
    """
    Strip extra whitespace and return None for empty / None input.

    Args:
        text: Raw text string.

    Returns:
        Cleaned text or None if empty.
    """
    if not text:
        return None
    cleaned = " ".join(str(text).split()).strip()
    return cleaned if cleaned else None


# ──────────────────────────────────────────────
# Salary-pattern stripping (pre-experience extraction)
# ──────────────────────────────────────────────

def strip_salary_patterns(text: str) -> str:
    """
    Remove salary-like patterns (e.g. $80,000, £60k, ₹12 LPA, USD 140,000)
    from text so that experience-extraction regex doesn't confuse salary
    numbers with years of experience.

    Args:
        text: Raw description text.

    Returns:
        Text with salary patterns removed.
    """
    if not text:
        return ""
    patterns = [
        r"[\$£€₹]\s*[\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*[\$£€₹]?\s*[\d,]+\.?\d*\s*[kK]?)?\s*(?:per\s+(?:year|annum|month|hour))?",
        r"(?:USD|CAD|AUD|GBP|EUR|INR|SGD|AED)\s*[\d,]+\.?\d*\s*[kK]?\s*(?:[-–to]+\s*[\d,]+\.?\d*\s*[kK]?)?",
        r"[\d,]+\.?\d*\s*(?:LPA|CTC|lakhs?|lacs?)\s*(?:[-–to]+\s*[\d,]+\.?\d*\s*(?:LPA|CTC|lakhs?|lacs?)?)?",
    ]
    result = text
    for pat in patterns:
        result = re.sub(pat, " ", result, flags=re.IGNORECASE)
    return result


# ──────────────────────────────────────────────
# Experience extraction
# ──────────────────────────────────────────────

def extract_experience(text: str) -> Optional[str]:
    """
    Extract experience requirement from job description text.

    Strips salary patterns first to avoid false positives, then checks for:
    - "fresher" → "Fresher"
    - "intern"  → "Internship"
    - "entry level" → "Entry Level"
    - "3-5 years" range patterns (both numbers < 30)
    - "5+ years" patterns (number < 30)

    Args:
        text: Job description text.

    Returns:
        Experience string or None if not found.
    """
    if not text:
        return None
    cleaned = strip_salary_patterns(text).lower()

    # Keyword matches
    if re.search(r"\bfresher\b", cleaned):
        return "Fresher"
    if re.search(r"\bintern\b", cleaned):
        return "Internship"
    if re.search(r"\bentry\s+level\b", cleaned):
        return "Entry Level"

    # Range: "3-5 years"
    match = re.search(r"(\d{1,2})\s*[-–to]+\s*(\d{1,2})\s*(?:\+\s*)?years?", cleaned)
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        if low < 30 and high < 30:
            return f"{low}-{high} years"

    # Single: "5+ years" or "5 years"
    match = re.search(r"(\d{1,2})\s*\+?\s*years?", cleaned)
    if match:
        num = int(match.group(1))
        if num < 30:
            return f"{num}+ years" if "+" in match.group(0) else f"{num} years"

    return None


# ──────────────────────────────────────────────
# Seniority inference
# ──────────────────────────────────────────────

def infer_seniority(title: str, linkedin_seniority_raw: Optional[str] = None) -> str:
    """
    Infer seniority level from job title and optional LinkedIn metadata.

    Priority order:
    1. Map linkedin_seniority_raw via SENIORITY_FROM_LINKEDIN
    2. Title keyword matching (VP/Director, Principal/Staff, Senior/Lead, etc.)
    3. Default to "Mid-Level (2-5 years)"

    Args:
        title: Job title string.
        linkedin_seniority_raw: Raw seniority label from LinkedIn metadata.

    Returns:
        Standardised seniority string.
    """
    # Priority 1: LinkedIn metadata
    if linkedin_seniority_raw:
        key = linkedin_seniority_raw.strip().lower()
        if key in SENIORITY_FROM_LINKEDIN:
            return SENIORITY_FROM_LINKEDIN[key]

    if not title:
        return "Mid-Level (2-5 years)"

    t = title.lower()

    # Priority 2: title keywords
    if any(kw in t for kw in ["vp", "vice president", "director"]):
        return "Director (8+ years)"
    if any(kw in t for kw in ["principal", "staff", "distinguished"]):
        return "Staff (8+ years)"
    if any(kw in t for kw in ["senior", "lead", "sr.", "sr "]):
        return "Senior (5+ years)"
    if any(kw in t for kw in ["junior", "jr.", "jr ", "intern", "fresher", "entry", "trainee", "graduate"]):
        return "Entry Level (0-2 years)"

    # Roman numeral levels
    if re.search(r"\biii\b", t):
        return "Senior (5+ years)"
    if re.search(r"\bii\b", t):
        return "Mid-Level (2-5 years)"
    if re.search(r"\bi\b", t) and "senior" not in t:
        return "Entry Level (0-2 years)"

    return "Mid-Level (2-5 years)"


# ──────────────────────────────────────────────
# Skills extraction
# ──────────────────────────────────────────────

def extract_skills(text: str) -> Optional[str]:
    """
    Extract known skills from text by matching against SKILL_LIST.

    Uses word-boundary matching for each skill keyword (case-insensitive).
    Returns a comma-separated string of matched skills, or None if none found.

    Args:
        text: Job description or requirements text.

    Returns:
        Comma-separated skills string or None.
    """
    if not text:
        return None
    matched = []
    text_lower = text.lower()
    for skill in SKILL_LIST:
        # Use word-boundary regex for accurate matching
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            matched.append(skill)
    return ", ".join(matched) if matched else None


# ──────────────────────────────────────────────
# LinkedIn metadata parsing
# ──────────────────────────────────────────────

def parse_linkedin_metadata(desc: str) -> Dict:
    """
    Parse LinkedIn description footer block for structured metadata.

    Extracts seniority level, employment type, industry, remote type,
    education requirements, equity/bonus indicators, date posted, and
    applicant count from the standard LinkedIn footer format:
    "Seniority level X Employment type Y Industries Z"

    Args:
        desc: Full job description text from LinkedIn.

    Returns:
        Dict with keys: seniority_raw, employment_type, industry,
        remote_type, education_required, has_equity, has_bonus,
        date_posted_raw, applicant_count.
    """
    result = {
        "seniority_raw": None,
        "employment_type": None,
        "industry": None,
        "remote_type": "On-site",
        "education_required": None,
        "has_equity": 0,
        "has_bonus": 0,
        "date_posted_raw": None,
        "applicant_count": None,
    }

    if not desc:
        return result

    text = str(desc)

    # Seniority level
    match = re.search(r"Seniority level\s*(.+?)(?:Employment type|$)", text, re.IGNORECASE | re.DOTALL)
    if match:
        result["seniority_raw"] = clean_text(match.group(1))

    # Employment type
    match = re.search(r"Employment type\s*(.+?)(?:Job function|Industries|$)", text, re.IGNORECASE | re.DOTALL)
    if match:
        result["employment_type"] = clean_text(match.group(1))

    # Industry
    match = re.search(r"Industries?\s*(.+?)(?:Referrals|Show more|$)", text, re.IGNORECASE | re.DOTALL)
    if match:
        result["industry"] = clean_text(match.group(1))

    # Remote type
    text_lower = text.lower()
    if "remote" in text_lower and "hybrid" in text_lower:
        result["remote_type"] = "Hybrid"
    elif "remote" in text_lower:
        result["remote_type"] = "Remote"
    elif "hybrid" in text_lower:
        result["remote_type"] = "Hybrid"

    # Education
    edu_match = re.search(
        r"\b(ph\.?d|doctorate|master'?s?|bachelor'?s?|b\.?s\.?|m\.?s\.?|mba|b\.?tech|m\.?tech)\b",
        text_lower,
    )
    if edu_match:
        result["education_required"] = edu_match.group(1).title()

    # Equity / Bonus flags
    result["has_equity"] = 1 if re.search(r"\b(equity|stock|rsu|esop|options)\b", text_lower) else 0
    result["has_bonus"] = 1 if re.search(r"\b(bonus|incentive|commission)\b", text_lower) else 0

    # Date posted
    date_match = re.search(r"Posted\s+([\w\s]+ago)", text, re.IGNORECASE)
    if date_match:
        result["date_posted_raw"] = clean_text(date_match.group(1))

    # Applicant count
    app_match = re.search(r"(\d[\d,]*)\s*applicants?", text, re.IGNORECASE)
    if app_match:
        result["applicant_count"] = int(app_match.group(1).replace(",", ""))

    return result


# ──────────────────────────────────────────────
# Indeed metadata parsing
# ──────────────────────────────────────────────

def parse_indeed_metadata(desc: str) -> Dict:
    """
    Parse Indeed description text for structured metadata.

    Extracts remote type, employment type, education requirements,
    and equity/bonus indicators from Indeed job descriptions.

    Args:
        desc: Full job description text from Indeed.

    Returns:
        Dict with keys: remote_type, employment_type, education_required,
        has_equity, has_bonus.
    """
    result = {
        "remote_type": "On-site",
        "employment_type": None,
        "education_required": None,
        "has_equity": 0,
        "has_bonus": 0,
    }

    if not desc:
        return result

    text_lower = str(desc).lower()

    # Remote type
    if "remote" in text_lower and "hybrid" in text_lower:
        result["remote_type"] = "Hybrid"
    elif "remote" in text_lower:
        result["remote_type"] = "Remote"
    elif "hybrid" in text_lower:
        result["remote_type"] = "Hybrid"

    # Employment type
    for etype in ["full-time", "full time", "part-time", "part time", "contract", "temporary", "internship"]:
        if etype in text_lower:
            result["employment_type"] = etype.replace("-", " ").title()
            break

    # Education
    edu_match = re.search(
        r"\b(ph\.?d|doctorate|master'?s?|bachelor'?s?|b\.?s\.?|m\.?s\.?|mba|b\.?tech|m\.?tech)\b",
        text_lower,
    )
    if edu_match:
        result["education_required"] = edu_match.group(1).title()

    # Equity / Bonus
    result["has_equity"] = 1 if re.search(r"\b(equity|stock|rsu|esop|options)\b", text_lower) else 0
    result["has_bonus"] = 1 if re.search(r"\b(bonus|incentive|commission)\b", text_lower) else 0

    return result


# ──────────────────────────────────────────────
# FAANG check
# ──────────────────────────────────────────────

def is_faang(company_name: str) -> int:
    """
    Check if a company is in the FAANG-tier set.

    Args:
        company_name: Company name string.

    Returns:
        1 if FAANG-tier, 0 otherwise.
    """
    if not company_name:
        return 0
    return 1 if company_name.strip().lower() in FAANG else 0


# ──────────────────────────────────────────────
# Seniority → experience mapping
# ──────────────────────────────────────────────

def seniority_to_experience(seniority_label: str) -> Optional[str]:
    """
    Convert a standardised seniority label to an experience range string.

    Args:
        seniority_label: Seniority string (e.g. "Senior (5+ years)").

    Returns:
        Experience range string or None.
    """
    if not seniority_label:
        return None

    mapping = {
        "Internship (0 years)": "0 years",
        "Entry Level (0-2 years)": "0-2 years",
        "Associate (1-3 years)": "1-3 years",
        "Mid-Level (2-5 years)": "2-5 years",
        "Senior (4-7 years)": "4-7 years",
        "Senior (5+ years)": "5+ years",
        "Staff (8+ years)": "8+ years",
        "Director (8+ years)": "8+ years",
        "Executive (10+ years)": "10+ years",
    }
    return mapping.get(seniority_label)
