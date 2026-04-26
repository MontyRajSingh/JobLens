"""
Quick test: run each scraper for 5 jobs on a single city/keyword combo.
Reports pass/fail for each source.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from scrapers.indeed_scraper import IndeedScraper
from scrapers.levelsfyi_scraper import LevelsFyiScraper
from scrapers.payscale_scraper import PayScaleScraper
from scrapers.ziprecruiter_scraper import ZipRecruiterScraper

SCRAPERS = [
    ("Indeed",        IndeedScraper),
    ("Levels.fyi",    LevelsFyiScraper),
    ("PayScale",      PayScaleScraper),
    ("ZipRecruiter",  ZipRecruiterScraper),
]

KEYWORD  = "data scientist"
LOCATION = "New York, NY, USA"
MAX_JOBS = 5

print(f"\n{'='*70}")
print(f" 🧪 SCRAPER SMOKE TEST")
print(f"{'='*70}")
print(f" Keyword:  {KEYWORD}")
print(f" Location: {LOCATION}")
print(f" Max jobs: {MAX_JOBS}")
print(f"{'='*70}\n")

results = []

for name, ScraperClass in SCRAPERS:
    print(f"─── Testing {name} {'─' * (50 - len(name))}")
    start = time.time()
    try:
        scraper = ScraperClass()
        jobs = scraper.scrape(
            keyword=KEYWORD,
            location=LOCATION,
            currency="USD",
            usd_rate=1.0,
            max_jobs=MAX_JOBS,
        )
        elapsed = time.time() - start
        with_salary = sum(1 for j in jobs if j.get("salary"))
        with_company = sum(1 for j in jobs if j.get("company_name"))

        if jobs:
            status = "✅ PASS"
            sample = jobs[0]
            print(f"    Sample: {sample.get('job_title', '?')} @ {sample.get('company_name', '?')}")
            print(f"    Salary: {sample.get('salary', 'N/A')}")
        else:
            status = "❌ FAIL (0 jobs)"

        results.append((name, status, len(jobs), with_salary, f"{elapsed:.1f}s"))
        print(f"    {status} — {len(jobs)} jobs, {with_salary} with salary ({elapsed:.1f}s)\n")

    except Exception as e:
        elapsed = time.time() - start
        results.append((name, f"💥 ERROR", 0, 0, f"{elapsed:.1f}s"))
        print(f"    💥 ERROR — {e} ({elapsed:.1f}s)\n")

# Summary table
print(f"\n{'='*70}")
print(f" 📊 RESULTS SUMMARY")
print(f"{'='*70}")
print(f" {'Source':<16} {'Status':<20} {'Jobs':<6} {'Salary':<8} {'Time':<8}")
print(f" {'─'*14}   {'─'*18}   {'─'*4}   {'─'*6}   {'─'*6}")
for name, status, count, sal, elapsed in results:
    print(f" {name:<16} {status:<20} {count:<6} {sal:<8} {elapsed:<8}")
print(f"{'='*70}\n")
