"""
main.py — Pipeline orchestrator for JobLens scraping system.

Provides run_pipeline() which loops city × keyword × source, deduplicates,
and exports results to timestamped CSV/JSON files AND inserts them into
the PostgreSQL database. Includes a CLI interface with --sources and
--max-jobs flags, plus a quality report summary.

CLI usage:
    python main.py --sources linkedin
    python main.py --sources linkedin indeed glassdoor --max-jobs 50
"""

import os
import sys
import json
import hashlib
import argparse
import logging
import time
from datetime import datetime
from typing import List, Tuple, Optional
from collections import Counter

import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from config import (
    OUTPUT_DIR, MAX_JOBS_PER_SEARCH, ENABLED_SOURCES,
    SCRAPE_CITIES, KEYWORDS,
)
from scrapers.indeed_scraper import IndeedScraper
from scrapers.levelsfyi_scraper import LevelsFyiScraper
from scrapers.payscale_scraper import PayScaleScraper
from scrapers.ziprecruiter_scraper import ZipRecruiterScraper
from scrapers.base_scraper import BaseScraper
from utils.validators import validate_dataframe

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Scraper registry
# ──────────────────────────────────────────────
SCRAPER_MAP = {
    "indeed": IndeedScraper,
    "levelsfyi": LevelsFyiScraper,
    "payscale": PayScaleScraper,
    "ziprecruiter": ZipRecruiterScraper,
}

# ──────────────────────────────────────────────
# Column order for output
# ──────────────────────────────────────────────
COLUMN_ORDER = BaseScraper.REQUIRED_COLUMNS


def run_pipeline(
    sources: List[str],
    cities: Optional[List[tuple]] = None,
    keywords: Optional[List[str]] = None,
    max_jobs: int = MAX_JOBS_PER_SEARCH,
) -> Tuple[List[dict], List[str]]:
    """
    Run the full scraping pipeline across sources × cities × keywords.

    Steps:
    1. Instantiate scrapers for each requested source
    2. Loop through every (city, keyword, source) combination
    3. Stamp city metadata on every job record
    4. Generate dedup_key if missing
    5. Deduplicate (keep row with salary when duplicates exist)
    6. Save to timestamped CSV and JSON in OUTPUT_DIR

    Args:
        sources: List of source names ("linkedin", "indeed", "glassdoor").
        cities: List of (search_loc, linkedin_loc, currency, usd_rate) tuples.
        keywords: List of search keywords.
        max_jobs: Max jobs per search query.

    Returns:
        Tuple of (all_jobs list, [csv_path, json_path]).
    """
    cities = cities or SCRAPE_CITIES
    keywords = keywords or KEYWORDS

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Instantiate scrapers
    scrapers = {}
    for src in sources:
        src_lower = src.lower()
        if src_lower in SCRAPER_MAP:
            scrapers[src_lower] = SCRAPER_MAP[src_lower]()
        else:
            logger.warning("Unknown source '%s', skipping", src)

    if not scrapers:
        logger.error("No valid scrapers to run!")
        return [], []

    all_jobs = []
    health_events = []

    # Main loop: city × keyword × source
    for city_search, city_linkedin, currency, usd_rate in cities:
        for keyword in keywords:
            for src_name, scraper in scrapers.items():
                logger.info(
                    "═══ Scraping: [%s] '%s' in '%s' (max=%d) ═══",
                    src_name.upper(), keyword, city_search, max_jobs,
                )

                try:
                    started_at = time.time()
                    # Choose location format based on scraper
                    if src_name == "linkedin":
                        location = city_linkedin
                    else:
                        location = city_search

                    jobs = scraper.scrape(
                        keyword=keyword,
                        location=location,
                        currency=currency,
                        usd_rate=usd_rate,
                        max_jobs=max_jobs,
                    )
                    duration_sec = round(time.time() - started_at, 2)

                    # Stamp city on every job
                    for job in jobs:
                        job["city"] = city_search

                    # --- Incremental Save ---
                    if jobs:
                        try:
                            # 1. Generate dedup keys
                            import hashlib
                            for job in jobs:
                                if not job.get("dedup_key"):
                                    company = (job.get("company_name") or "").lower()
                                    title = (job.get("job_title") or "").lower()
                                    city = (job.get("city") or "").lower()
                                    job["dedup_key"] = hashlib.md5(
                                        f"{company}{title}{city}".encode()
                                    ).hexdigest()[:12]
                            
                            # 2. Update Database
                            from api.db.loader import save_jobs_to_db
                            db_count = save_jobs_to_db(jobs)
                            
                            # 3. Append to master CSV
                            import pandas as pd
                            master_path = os.path.join(OUTPUT_DIR, "jobs_master.csv")
                            pd.DataFrame(jobs).to_csv(master_path, mode='a', index=False, header=not os.path.exists(master_path))
                            
                            logger.info("✅ [%s] Saved %d jobs (DB + CSV)", src_name.upper(), len(jobs))
                        except Exception as save_err:
                            logger.warning("⚠️  Incremental save failed: %s", save_err)

                    all_jobs.extend(jobs)
                    salary_hits = sum(1 for job in jobs if job.get("salary") or job.get("salary_usd_numeric"))
                    health_events.append({
                        "source": src_name,
                        "keyword": keyword,
                        "city": city_search,
                        "status": "success",
                        "jobs_found": len(jobs),
                        "salary_hits": salary_hits,
                        "salary_hit_rate_pct": round((salary_hits / len(jobs) * 100), 2) if jobs else 0.0,
                        "duration_sec": duration_sec,
                        "error": None,
                        "scraped_at": datetime.utcnow().isoformat(),
                    })

                except Exception as e:
                    logger.error("❌ [%s] '%s' in '%s' failed: %s", src_name.upper(), keyword, city_search, e)
                    health_events.append({
                        "source": src_name,
                        "keyword": keyword,
                        "city": city_search,
                        "status": "failed",
                        "jobs_found": 0,
                        "salary_hits": 0,
                        "salary_hit_rate_pct": 0.0,
                        "duration_sec": round(time.time() - started_at, 2) if "started_at" in locals() else 0.0,
                        "error": str(e),
                        "scraped_at": datetime.utcnow().isoformat(),
                    })

    if health_events:
        health_path = os.path.join(OUTPUT_DIR, "scraper_health_latest.json")
        with open(health_path, "w") as f:
            json.dump({
                "generated_at": datetime.utcnow().isoformat(),
                "events": health_events,
                "summary": _summarize_scraper_health(health_events),
            }, f, indent=2)
        logger.info("🩺 Saved scraper health report → %s", health_path)

    # Generate dedup_key where missing
    for job in all_jobs:
        if not job.get("dedup_key"):
            company = (job.get("company_name") or "").lower()
            title = (job.get("job_title") or "").lower()
            city = (job.get("city") or "").lower()
            job["dedup_key"] = hashlib.md5(
                f"{company}{title}{city}".encode()
            ).hexdigest()[:12]

    # Deduplicate: keep row with salary when duplicates exist
    if all_jobs:
        df = pd.DataFrame(all_jobs)

        # Sort so rows with salary come first (non-null before null)
        df["_has_salary"] = df["salary"].notna().astype(int)
        df = df.sort_values("_has_salary", ascending=False)
        df = df.drop_duplicates(subset=["dedup_key"], keep="first")
        df = df.drop(columns=["_has_salary"])

        # Reorder columns
        existing_cols = [c for c in COLUMN_ORDER if c in df.columns]
        extra_cols = [c for c in df.columns if c not in COLUMN_ORDER]
        df = df[existing_cols + extra_cols]

        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(OUTPUT_DIR, f"jobs_{timestamp}.csv")
        json_path = os.path.join(OUTPUT_DIR, f"jobs_{timestamp}.json")

        df.to_csv(csv_path, index=False)
        df.to_json(json_path, orient="records", indent=2)

        all_jobs = df.to_dict(orient="records")

        logger.info("📁 Saved %d jobs → %s", len(df), csv_path)
        logger.info("📁 Saved %d jobs → %s", len(df), json_path)

        # Insert into database
        try:
            from dotenv import load_dotenv
            load_dotenv()
            from api.db.loader import save_jobs_to_db
            db_count = save_jobs_to_db(all_jobs)
            logger.info("🗄️  Inserted %d new jobs into database", db_count)
        except Exception as e:
            logger.warning("⚠️  Database insert failed (CSV backup available): %s", e)

        return all_jobs, [csv_path, json_path]

    logger.warning("No jobs collected!")
    return [], []


def _summarize_scraper_health(events: List[dict]) -> dict:
    """Aggregate per-run scraper health metrics."""
    summary = {}
    for event in events:
        source = event["source"]
        bucket = summary.setdefault(source, {
            "tasks": 0,
            "successes": 0,
            "failures": 0,
            "jobs_found": 0,
            "salary_hits": 0,
            "avg_duration_sec": 0.0,
        })
        bucket["tasks"] += 1
        bucket["successes"] += 1 if event["status"] == "success" else 0
        bucket["failures"] += 1 if event["status"] == "failed" else 0
        bucket["jobs_found"] += event["jobs_found"]
        bucket["salary_hits"] += event["salary_hits"]
        bucket["avg_duration_sec"] += event["duration_sec"]

    for bucket in summary.values():
        tasks = bucket["tasks"] or 1
        jobs = bucket["jobs_found"]
        bucket["avg_duration_sec"] = round(bucket["avg_duration_sec"] / tasks, 2)
        bucket["success_rate_pct"] = round(bucket["successes"] / tasks * 100, 2)
        bucket["salary_hit_rate_pct"] = round(bucket["salary_hits"] / jobs * 100, 2) if jobs else 0.0

    return summary


def print_quality_report(jobs: List[dict]) -> None:
    """
    Print a quality summary report for scraped jobs.

    Includes: fill rates, salary by source/city, seniority distribution,
    and top 15 skills.
    """
    if not jobs:
        print("\n⚠️  No jobs to report on.\n")
        return

    df = pd.DataFrame(jobs)

    print("\n" + "=" * 70)
    print(" 📊 SCRAPING QUALITY REPORT")
    print("=" * 70)

    # Basic stats
    print(f"\n 📋 Total jobs: {len(df)}")
    print(f" 🔗 Sources:    {df['source_website'].nunique()}")
    print(f" 🌍 Cities:     {df['city'].nunique()}")

    # Fill rates
    validate_dataframe(df)

    # Salary by source
    if "salary" in df.columns:
        salary_filled = df.groupby("source_website")["salary"].apply(
            lambda x: f"{x.notna().sum()}/{len(x)} ({x.notna().mean()*100:.0f}%)"
        )
        print("\n 💰 Salary fill by source:")
        for src, rate in salary_filled.items():
            print(f"    {src}: {rate}")

    # Salary by city
    if "salary" in df.columns:
        salary_city = df.groupby("city")["salary"].apply(
            lambda x: f"{x.notna().sum()}/{len(x)} ({x.notna().mean()*100:.0f}%)"
        )
        print("\n 🌍 Salary fill by city:")
        for city, rate in salary_city.items():
            print(f"    {city}: {rate}")

    # Seniority distribution
    if "seniority_level" in df.columns:
        seniority_counts = df["seniority_level"].value_counts()
        print("\n 📈 Seniority distribution:")
        for level, count in seniority_counts.items():
            print(f"    {level}: {count}")

    # Top 15 skills
    if "skills_required" in df.columns:
        all_skills = df["skills_required"].dropna().str.split(", ").explode()
        top_skills = all_skills.value_counts().head(15)
        print("\n 🛠  Top 15 skills:")
        for skill, count in top_skills.items():
            print(f"    {skill}: {count}")

    print("\n" + "=" * 70 + "\n")


def main():
    """CLI entry point for the scraping pipeline."""
    parser = argparse.ArgumentParser(
        description="JobLens — Global Job Market Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py --sources indeed levelsfyi payscale ziprecruiter
    python main.py --sources levelsfyi --max-jobs 20
    python main.py --sources indeed payscale --max-jobs 50
        """,
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=ENABLED_SOURCES,
        choices=["indeed", "levelsfyi", "payscale", "ziprecruiter"],
        help="Sources to scrape (default: all enabled)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=MAX_JOBS_PER_SEARCH,
        help=f"Max jobs per search query (default: {MAX_JOBS_PER_SEARCH})",
    )
    args = parser.parse_args()

    # Log configuration
    logger.info("=" * 60)
    logger.info("JobLens Scraper — Starting pipeline")
    logger.info("=" * 60)
    logger.info("Sources:   %s", args.sources)
    logger.info("Cities:    %d", len(SCRAPE_CITIES))
    logger.info("Keywords:  %s", KEYWORDS)
    logger.info("Max jobs:  %d per query", args.max_jobs)
    logger.info("Output:    %s", OUTPUT_DIR)

    # Run pipeline
    jobs, files = run_pipeline(
        sources=args.sources,
        max_jobs=args.max_jobs,
    )

    # Print report
    print_quality_report(jobs)

    if files:
        print("📁 Output files:")
        for f in files:
            print(f"    {f}")


if __name__ == "__main__":
    main()
