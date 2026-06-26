"""
train.py — Training entry point for the JobLens salary prediction model.

Orchestrates the full training pipeline:
1. Load data from CSV or PostgreSQL database
2. Check minimum salary rows
3. FeatureEngineer().fit_transform() → feature matrix
4. SalaryPredictor().train(X, y)
5. Save all artifacts to pipeline/models/
6. Save cleaned and feature CSVs to output/

CLI:
    python -m pipeline.train
    python -m pipeline.train --data output/jobs_master.csv --min-rows 100
    python -m pipeline.train --use-db
"""

import os
import sys
import argparse
import logging
import json
import csv

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import OUTPUT_DIR
from pipeline.data_cleaner import DataCleaner
from pipeline.preprocessing import FeatureEngineer
from pipeline.model import SalaryPredictor
from pipeline.data_quality import evaluate_training_readiness

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_DATA = os.path.join(OUTPUT_DIR, "jobs_master.csv")
DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")


def _load_existing_metadata(model_dir: str) -> dict:
    metadata_path = os.path.join(model_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        return {}
    try:
        with open(metadata_path, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Could not read existing model metadata: %s", exc)
        return {}


def _assert_model_promotion_allowed(args, new_metrics: dict, model_name: str) -> None:
    """Stop accidental promotion when a new model is clearly worse."""
    if args.force_promote:
        return

    existing = _load_existing_metadata(args.model_dir)
    previous_r2 = existing.get("r2")
    new_r2 = new_metrics.get(model_name, {}).get("r2")
    if previous_r2 is None or new_r2 is None:
        return

    allowed_floor = float(previous_r2) - args.max_r2_drop
    if float(new_r2) < allowed_floor:
        print("\n❌ Model promotion blocked.")
        print(f"   Previous R²: {previous_r2:.3f}")
        print(f"   New R²:      {new_r2:.3f}")
        print(f"   Allowed min: {allowed_floor:.3f}")
        print("   Re-run with --force-promote only if you intentionally want this model.")
        sys.exit(1)


def load_data(args) -> pd.DataFrame:
    """
    Load data based on CLI flags.

    Priority:
      1. --use-db → load from PostgreSQL database
      2. (default) → load scraped CSV from --data path
    """
    if args.use_db:
        # Load from PostgreSQL database
        from dotenv import load_dotenv
        load_dotenv()
        from api.db.loader import load_training_data
        df = load_training_data()
        if df.empty:
            logger.error("Database returned no data.")
            print("\n❌ No data in the database.")
            print("   Run the scraper first: python main.py --sources linkedin --max-jobs 30")
            print("   Or use --data to load from a CSV file.")
            sys.exit(1)
        logger.info("Loaded %d rows from database", len(df))
        print(f"   Database rows: {len(df):,}")
        return df

    else:
        # Default: load scraped data from CSV
        data_path = args.data
        if not os.path.exists(data_path):
            logger.error("Data file not found: %s", data_path)
            print(f"\n❌ Data file not found: {data_path}")
            print("   Run the scraper first: python main.py --sources linkedin --max-jobs 30")
            print("   Or use --use-db to train from the database.")
            sys.exit(1)

        df = pd.read_csv(data_path)
        logger.info("Loaded %d rows from %s", len(df), data_path)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# AUTORESEARCH: Experiment logger
# Logs every training run to results.csv for the agent to track progress.
# ─────────────────────────────────────────────────────────────────────────────
def _log_experiment(model_name: str, metrics: dict, rows: int, features: int) -> None:
    """Append this experiment's results to results.csv."""
    results_path = os.path.join(os.path.dirname(__file__), "..", "results.csv")

    # Read next experiment ID
    experiment_id = 1
    if os.path.exists(results_path):
        try:
            existing = pd.read_csv(results_path)
            if not existing.empty:
                experiment_id = int(existing["experiment_id"].max()) + 1
        except Exception:
            pass

    row = {
        "experiment_id": experiment_id,
        "model_name":    model_name,
        "rmse":          round(metrics.get("rmse", 0), 2),
        "mae":           round(metrics.get("mae", 0), 2),
        "r2":            round(metrics.get("r2", 0), 4),
        "rows":          rows,
        "features":      features,
        "change_made":   "see git diff",   # agent should update this description
    }

    file_exists = os.path.exists(results_path)
    with open(results_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    logger.info("Experiment #%d logged to results.csv", experiment_id)


def train_pipeline(args) -> None:
    """
    Execute the full training pipeline.
    """
    model_dir = args.model_dir
    min_rows = args.min_rows

    source = "PostgreSQL database" if args.use_db else args.data
    print(f"\n{'='*70}")
    print(f" JOBLENS TRAINING PIPELINE")
    print(f"{'='*70}")
    print(f" Source:    {source}")
    print(f" Model dir: {model_dir}")
    print(f" Min rows:  {min_rows}")

    # Step 1: Load data
    df = load_data(args)

    # Step 2: Clean
    cleaner = DataCleaner()
    df_clean = cleaner.clean(df)

    # Step 3: Check salary count
    salary_count = df_clean["salary_usd_numeric"].notna().sum()
    logger.info("Rows with salary: %d", salary_count)

    readiness = evaluate_training_readiness(df_clean)
    print("\n 📊 Scraped-data readiness:")
    print(f"    Salary rows:     {readiness['salary_rows']:,}")
    print(f"    Salary coverage: {readiness['salary_coverage_pct']:.1f}%")
    print(f"    Cities:          {readiness['cities_count']}")
    print(f"    Seniority lvls:  {readiness['seniority_levels_count']}")
    print(f"    Top source:      {readiness['top_source']} ({readiness['top_source_pct']:.1f}%)")
    if readiness["ready_for_scraped_only_training"]:
        print("    Status:          ready for scraped-only candidate training")
    else:
        print("    Status:          keep Kaggle or hybrid training")
        for reason in readiness["reasons"]:
            print(f"      - {reason}")

    if salary_count < min_rows:
        logger.warning(
            "Only %d rows have salary data (minimum: %d). "
            "Consider scraping more data or lowering --min-rows.",
            salary_count, min_rows,
        )
        print(f"\n⚠️  Only {salary_count} rows have salary data (minimum: {min_rows})")
        print("    Consider scraping more data or lowering --min-rows.")
        # Continue anyway if we have at least 20 rows
        if salary_count < 20:
            print(f"\n❌ Cannot train with fewer than 20 salary rows. Exiting.")
            sys.exit(1)
        print(f"    Proceeding with {salary_count} rows...\n")

    # Step 4: Feature engineering
    feature_engineer = FeatureEngineer()

    # Use rows that have salary for training (but fit on full data for encoders)
    X = feature_engineer.fit_transform(df_clean)

    # Step 5: Extract y aligned with X index
    y = df_clean.loc[X.index, "salary_usd_numeric"]

    # Only train on rows with actual salary
    salary_mask = y.notna()
    X_train = X.loc[salary_mask]
    y_train = y.loc[salary_mask]

    logger.info("Training features: %d columns, %d rows with salary", X_train.shape[1], len(X_train))

    # Step 6: Train model
    predictor = SalaryPredictor()
    metrics = predictor.train(X_train, y_train)
    _assert_model_promotion_allowed(args, metrics, predictor.best_model_name)

    # Save model artifacts
    os.makedirs(model_dir, exist_ok=True)
    predictor.save(model_dir)
    feature_engineer.save(model_dir)

    metadata_path = os.path.join(model_dir, "metadata.json")
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
    metadata["training_source"] = source
    metadata["scraped_data_readiness"] = readiness
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Step 7: Save cleaned and feature CSVs
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cleaned_path = os.path.join(OUTPUT_DIR, "jobs_cleaned.csv")
    features_path = os.path.join(OUTPUT_DIR, "jobs_features.csv")

    df_clean.to_csv(cleaned_path, index=False)
    X.to_csv(features_path, index=False)

    logger.info("Saved cleaned data: %s", cleaned_path)
    logger.info("Saved features: %s", features_path)

    # Final summary
    best_metrics = metrics.get(predictor.best_model_name, {})
    val_r2   = best_metrics.get("r2", 0)
    val_rmse = best_metrics.get("rmse", 0)
    val_mae  = best_metrics.get("mae", 0)

    print(f"\n{'='*70}")
    print(f" ✅ TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f" Model:    {predictor.best_model_name}")
    print(f" RMSE:     ${val_rmse:,.0f}")
    print(f" MAE:      ${val_mae:,.0f}")
    print(f" R²:       {val_r2:.3f}")
    print(f" Features: {len(feature_engineer.feature_columns)}")
    print(f" Rows:     {len(X_train)}")
    print(f"\n 📁 Artifacts saved to: {model_dir}")
    print(f" 📁 Cleaned CSV:        {cleaned_path}")
    print(f" 📁 Features CSV:       {features_path}")
    print(f"{'='*70}\n")

    # ─────────────────────────────────────────────────────────────────────────
    # AUTORESEARCH: Print metric in standard format + log experiment
    # The agent reads these lines to decide keep/revert.
    # val_metric uses R² (higher is better).
    # ─────────────────────────────────────────────────────────────────────────
    print(f"val_metric: {val_r2:.4f}")   # agent reads this line — do not remove
    print(f"val_rmse:   {val_rmse:.2f}") # agent reads this line — do not remove

    _log_experiment(
        model_name=predictor.best_model_name,
        metrics=best_metrics,
        rows=len(X_train),
        features=len(feature_engineer.feature_columns),
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="JobLens — Train Salary Prediction Model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m pipeline.train --use-db
  python -m pipeline.train --data output/jobs_master.csv --min-rows 100
        """,
    )
    parser.add_argument(
        "--data",
        type=str,
        default=DEFAULT_DATA,
        help=f"Path to scraped input CSV (default: {DEFAULT_DATA})",
    )
    parser.add_argument(
        "--use-db",
        action="store_true",
        help="Load training data from PostgreSQL database instead of CSV",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=DEFAULT_MODEL_DIR,
        help=f"Directory to save model artifacts (default: {DEFAULT_MODEL_DIR})",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=500,
        help="Minimum salary rows required (default: 500)",
    )
    parser.add_argument(
        "--max-r2-drop",
        type=float,
        default=0.02,
        help="Maximum allowed R² drop versus existing promoted model (default: 0.02)",
    )
    parser.add_argument(
        "--force-promote",
        action="store_true",
        help="Save the new model even if it performs worse than the existing model",
    )
    args = parser.parse_args()

    train_pipeline(args)


if __name__ == "__main__":
    main()
