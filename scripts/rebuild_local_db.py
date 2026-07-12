"""Rebuild the local SQLite database from output/jobs_master.csv."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        default="output/jobs_master.csv",
        help="Source CSV to clean and load into the local database.",
    )
    parser.add_argument(
        "--db",
        default="data/jobs.db",
        help="SQLite database path to create or replace.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    csv_path = (repo_root / args.csv).resolve()
    db_path = (repo_root / args.db).resolve()

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    sys.path.insert(0, str(repo_root))

    from api.db.loader import reseed_jobs_from_csv

    loaded = reseed_jobs_from_csv(str(csv_path))
    print(f"Rebuilt {db_path} with {loaded} jobs from {csv_path}")


if __name__ == "__main__":
    main()
