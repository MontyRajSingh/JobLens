"""
run_scraper.py — Daily accumulation script for JobLens.

Designed to be run on a schedule (e.g. cron: 0 9 * * * python run_scraper.py).
Steps:
1. Run run_pipeline() to scrape new jobs
2. Load output/jobs_master.csv if it exists
3. Append new jobs to master
4. Deduplicate entire master on dedup_key (keep rows with salary)
5. Save back to output/jobs_master.csv
6. Print summary: new unique jobs added, duplicates dropped, total in master
"""

import os
import sys
import logging
from datetime import datetime

import pandas as pd

from config import OUTPUT_DIR, ENABLED_SOURCES, MAX_JOBS_PER_SEARCH
from main import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MASTER_CSV = os.path.join(OUTPUT_DIR, "jobs_master.csv")


def run_daily():
    """
    Execute the daily scraping accumulation workflow.

    1. Runs the full scraping pipeline with all enabled sources
    2. Loads or initialises the master CSV
    3. Appends new results and deduplicates
    4. Prints a summary of the run
    """
    logger.info("=" * 60)
    logger.info("JobLens Daily Runner — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("=" * 60)

    # Step 1: Scrape new jobs
    new_jobs, _ = run_pipeline(
        sources=ENABLED_SOURCES,
        max_jobs=MAX_JOBS_PER_SEARCH,
    )

    if not new_jobs:
        logger.warning("No new jobs scraped today.")
        return

    new_df = pd.DataFrame(new_jobs)
    new_count = len(new_df)

    # Step 2: Load existing master (or start fresh)
    if os.path.exists(MASTER_CSV):
        master_df = pd.read_csv(MASTER_CSV)
        before_count = len(master_df)
        logger.info("Loaded existing master: %d records", before_count)
    else:
        master_df = pd.DataFrame()
        before_count = 0
        logger.info("No existing master — starting fresh")

    # Step 3: Append new jobs
    combined_df = pd.concat([master_df, new_df], ignore_index=True)

    # Step 4: Deduplicate (keep rows with salary first)
    combined_df["_has_salary"] = combined_df["salary"].notna().astype(int)
    combined_df = combined_df.sort_values("_has_salary", ascending=False)
    combined_df = combined_df.drop_duplicates(subset=["dedup_key"], keep="first")
    combined_df = combined_df.drop(columns=["_has_salary"])

    after_count = len(combined_df)
    unique_added = after_count - before_count
    dupes_dropped = (before_count + new_count) - after_count

    # Step 5: Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    combined_df.to_csv(MASTER_CSV, index=False)

    # Step 6: Summary
    print("\n" + "=" * 60)
    print(" 📊 DAILY RUN SUMMARY")
    print("=" * 60)
    print(f" 🆕 New jobs scraped:     {new_count}")
    print(f" ✅ Unique jobs added:    {unique_added}")
    print(f" 🔁 Duplicates dropped:  {dupes_dropped}")
    print(f" 📁 Total in master:     {after_count}")
    print(f" 💾 Saved to:            {MASTER_CSV}")
    print("=" * 60 + "\n")

    logger.info("Daily run complete: +%d unique, -%d dupes, %d total", unique_added, dupes_dropped, after_count)


if __name__ == "__main__":
    run_daily()
