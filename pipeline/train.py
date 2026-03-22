"""
train.py — Training entry point for the JobLens salary prediction model.

Orchestrates the full training pipeline:
1. Load CSV → DataCleaner().clean(df)
2. Check minimum salary rows
3. FeatureEngineer().fit_transform() → feature matrix
4. SalaryPredictor().train(X, y)
5. Save all artifacts to pipeline/models/
6. Save cleaned and feature CSVs to output/

CLI:
    python -m pipeline.train
    python -m pipeline.train --data output/jobs_master.csv --min-rows 100
    python -m pipeline.train --use-kaggle
    python -m pipeline.train --use-kaggle --merge-scraped
"""

import os
import sys
import argparse
import logging

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import OUTPUT_DIR
from pipeline.data_cleaner import DataCleaner
from pipeline.preprocessing import FeatureEngineer
from pipeline.model import SalaryPredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_DATA = os.path.join(OUTPUT_DIR, "jobs_master.csv")
DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
DEFAULT_KAGGLE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "job_descriptions.csv"
)


def load_data(args) -> pd.DataFrame:
    """
    Load data based on CLI flags.

    Priority:
      1. --use-kaggle → load Kaggle via KaggleDatasetLoader
      2. --merge-scraped → also load scraped CSV and concatenate
      3. (default) → load scraped CSV from --data path
    """
    frames = []

    if args.use_kaggle:
        from pipeline.dataset_loader import KaggleDatasetLoader
        kaggle_path = DEFAULT_KAGGLE_PATH
        if not os.path.exists(kaggle_path):
            print(f"\n❌ Kaggle dataset not found: {kaggle_path}")
            sys.exit(1)

        loader = KaggleDatasetLoader()
        df_kaggle = loader.load(kaggle_path)
        loader.validate(df_kaggle)
        frames.append(df_kaggle)

        # Also merge scraped data if requested
        if args.merge_scraped:
            scraped_path = args.data
            if os.path.exists(scraped_path):
                logger.info("Merging scraped data from %s", scraped_path)
                df_scraped = pd.read_csv(scraped_path)
                logger.info("Scraped data: %d rows", len(df_scraped))
                print(f"   Scraped data:  {len(df_scraped):,} rows from {scraped_path}")
                frames.append(df_scraped)
            else:
                logger.warning("Scraped data not found at %s — using Kaggle only", scraped_path)
                print(f"   ⚠️  Scraped data not found: {scraped_path} — Kaggle only")

        # Concatenate
        df = pd.concat(frames, ignore_index=True)

        # Deduplicate on dedup_key if present
        if "dedup_key" in df.columns:
            before = len(df)
            df = df.drop_duplicates(subset=["dedup_key"], keep="first")
            dropped = before - len(df)
            if dropped > 0:
                logger.info("Deduplication: removed %d duplicates → %d remaining", dropped, len(df))
                print(f"   Dedup: removed {dropped:,} → {len(df):,} remaining")

        print(f"   Total training rows: {len(df):,}\n")
        return df

    else:
        # Default: load scraped data
        data_path = args.data
        if not os.path.exists(data_path):
            logger.error("Data file not found: %s", data_path)
            print(f"\n❌ Data file not found: {data_path}")
            print("   Run the scraper first: python main.py --sources linkedin --max-jobs 30")
            print("   Or use --use-kaggle to train on Kaggle dataset")
            sys.exit(1)

        df = pd.read_csv(data_path)
        logger.info("Loaded %d rows from %s", len(df), data_path)
        return df


def train_pipeline(args) -> None:
    """
    Execute the full training pipeline.
    """
    model_dir = args.model_dir
    min_rows = args.min_rows

    source = "Kaggle dataset" if args.use_kaggle else args.data
    print(f"\n{'='*70}")
    print(f" 🚀 JOBLENS TRAINING PIPELINE")
    print(f"{'='*70}")
    print(f" Source:    {source}")
    if args.use_kaggle and args.merge_scraped:
        print(f"           + scraped data from {args.data}")
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

    # Save model artifacts
    os.makedirs(model_dir, exist_ok=True)
    predictor.save(model_dir)
    feature_engineer.save(model_dir)

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
    print(f"\n{'='*70}")
    print(f" ✅ TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f" Model:    {predictor.best_model_name}")
    print(f" RMSE:     ${best_metrics.get('rmse', 0):,.0f}")
    print(f" MAE:      ${best_metrics.get('mae', 0):,.0f}")
    print(f" R²:       {best_metrics.get('r2', 0):.3f}")
    print(f" Features: {len(feature_engineer.feature_columns)}")
    print(f" Rows:     {len(X_train)}")
    print(f"\n 📁 Artifacts saved to: {model_dir}")
    print(f" 📁 Cleaned CSV:        {cleaned_path}")
    print(f" 📁 Features CSV:       {features_path}")
    print(f"{'='*70}\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="JobLens — Train Salary Prediction Model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m pipeline.train --use-kaggle
  python -m pipeline.train --data output/jobs_master.csv --min-rows 100
  python -m pipeline.train --use-kaggle --merge-scraped
        """,
    )
    parser.add_argument(
        "--data",
        type=str,
        default=DEFAULT_DATA,
        help=f"Path to scraped input CSV (default: {DEFAULT_DATA})",
    )
    parser.add_argument(
        "--use-kaggle",
        action="store_true",
        help="Use Kaggle dataset from data/job_descriptions.csv",
    )
    parser.add_argument(
        "--merge-scraped",
        action="store_true",
        help="Combine Kaggle + scraped data (requires --use-kaggle)",
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
    args = parser.parse_args()

    if args.merge_scraped and not args.use_kaggle:
        parser.error("--merge-scraped requires --use-kaggle")

    train_pipeline(args)


if __name__ == "__main__":
    main()
