"""
config.py — Single source of truth for all constants used across the JobLens platform.

Contains: scrape targets, search keywords, Chrome options, skill taxonomy,
FAANG set, seniority mappings, cost-of-living indices, Indeed domains,
Glassdoor city IDs, and environment-based credentials.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# Output & limits
# ──────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
MAX_JOBS_PER_SEARCH = 5
# Indeed and ZipRecruiter were dropped: both hard-block GitHub's datacenter
# IPs (HTTP 403) and can't be scraped from free CI without paid residential
# proxies. See COOKIE_SOURCES for the login-walled boards we keep via cookies.
ENABLED_SOURCES = ["levelsfyi", "payscale", "linkedin", "wellfound", "instahyre", "naukri"]

# Login-walled sources that require an authenticated session cookie (supplied
# via a GitHub secret named "<SOURCE>_COOKIE") to return any data. When the
# cookie is missing/expired these scrapers return nothing and the run summary
# flags them — they never crash the run.
COOKIE_SOURCES = {"wellfound", "instahyre", "naukri"}

# ──────────────────────────────────────────────
# Salary & Currency Conventions:
# - `salary` field: formatted display string (e.g. "$X USD/yr", converted to USD)
# - `salary_currency`: the original currency of the salary source
# - `currency`: the local currency of the search city
# - `salary_usd_numeric`: numeric USD value (float), set during cleaning
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# Cities to scrape: (search_location, linkedin_location, currency, usd_rate)
# ──────────────────────────────────────────────
SCRAPE_CITIES = [
    ("New York, NY, USA",       "New York City Metropolitan Area",    "USD", 1.00),
    ("London, UK",              "London, England, United Kingdom",    "GBP", 1.27),
    ("Toronto, Canada",         "Toronto, Ontario, Canada",           "CAD", 0.74),
    ("Sydney, Australia",       "Sydney, New South Wales, Australia", "AUD", 0.65),
    ("Singapore",               "Singapore",                          "SGD", 0.74),
    ("Bengaluru, India",        "Bengaluru, Karnataka",               "INR", 0.012),
    ("Gurugram, India",         "Gurugram, Haryana",                  "INR", 0.012),
    ("Hyderabad, India",        "Hyderabad, Telangana",               "INR", 0.012),
    ("Pune, India",             "Pune, Maharashtra",                  "INR", 0.012),
]

# ──────────────────────────────────────────────
# Job search keywords
# ──────────────────────────────────────────────
KEYWORDS = [
    "data scientist", 
    "machine learning engineer", 
    "software engineer",
    "data analyst",
    "data engineer",
    "ui/ux designer",
    "full stack developer",
    "backend engineer",
    "frontend engineer",
    "devops engineer",
    "cyber security engineer",
    "ai research scientist"
]

# ──────────────────────────────────────────────
# Chrome / Selenium options
# ──────────────────────────────────────────────
CHROME_OPTIONS = [
    "--headless",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--window-size=1920,1080",
    "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ──────────────────────────────────────────────
# Skills taxonomy for extraction
# ──────────────────────────────────────────────
SKILL_LIST = [
    "Python", "Java", "JavaScript", "TypeScript", "SQL", "R", "C++", "C#",
    "Go", "Rust", "Scala", "Ruby", "PHP", "Swift", "Kotlin",
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Keras",
    "Scikit-learn", "NLP", "Computer Vision", "LLM", "GenAI", "RAG",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Git", "Terraform",
    "React", "Angular", "Vue", "Node.js", "Django", "Flask", "Spring Boot",
    "MongoDB", "PostgreSQL", "MySQL", "Redis", "Elasticsearch",
    "Tableau", "Power BI", "Excel", "Spark", "Hadoop", "Kafka", "Airflow",
    "Data Science", "Data Analysis", "Data Engineering", "MLOps",
    "ML", "AI", "AI/ML", "REST", "API", "CI/CD", "DevOps", "Security",
    "Figma", "Adobe XD", "Photoshop", "Illustrator", "Sketch", "InVision",
    "Product Management", "Agile", "Scrum", "Jira", "Confluence",
    "Selenium", "Cypress", "Appium", "JMeter", "Postman",
    "Cyber Security", "Penetration Testing", "Firewall", "SIEM",
    "Cloud Computing", "Infrastructure as Code", "Linux", "Unix"
]

# ──────────────────────────────────────────────
# FAANG-tier companies
# ──────────────────────────────────────────────
FAANG = {
    "google", "meta", "apple", "amazon", "microsoft", "netflix",
    "openai", "anthropic", "deepmind", "nvidia",
}

# ──────────────────────────────────────────────
# LinkedIn seniority label → standardised seniority string
# ──────────────────────────────────────────────
SENIORITY_FROM_LINKEDIN = {
    "internship":       "Internship (0 years)",
    "entry level":      "Entry Level (0-2 years)",
    "associate":        "Associate (1-3 years)",
    "mid-senior level": "Senior (4-7 years)",
    "senior":           "Senior (5+ years)",
    "director":         "Director (8+ years)",
    "executive":        "Executive (10+ years)",
}

# ──────────────────────────────────────────────
# Cost-of-living index by city
# ──────────────────────────────────────────────
COL_INDEX = {
    "New York, NY, USA": 100,
    "San Francisco, CA, USA": 105,
    "Seattle, WA, USA": 88,
    "Austin, TX, USA": 75,
    "Chicago, IL, USA": 80,
    "London, UK": 90,
    "Toronto, Canada": 78,
    "Sydney, Australia": 85,
    "Berlin, Germany": 70,
    "Singapore": 88,
    "Dubai, UAE": 68,
    "Bengaluru, India": 28,
    "Gurugram, India": 30,
    "Hyderabad, India": 26,
    "Pune, India": 25,
    "Mumbai, India": 32,
}

# ──────────────────────────────────────────────
# Indeed domain per currency
# ──────────────────────────────────────────────
INDEED_DOMAINS = {
    "USD": "https://www.indeed.com",
    "GBP": "https://uk.indeed.com",
    "CAD": "https://ca.indeed.com",
    "AUD": "https://au.indeed.com",
    "EUR": "https://de.indeed.com",
    "INR": "https://www.indeed.co.in",
    "SGD": "https://sg.indeed.com",
}


