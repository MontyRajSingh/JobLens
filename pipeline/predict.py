"""
predict.py — Inference entry point for salary prediction.

Provides predict_salary() function that loads trained model artifacts
and predicts salary for a given job specification. Also provides an
interactive CLI mode for manual predictions.

Module-level singletons ensure model is loaded only once.

Usage (programmatic):
    from pipeline.predict import predict_salary
    result = predict_salary({
        "job_title": "Senior Data Scientist",
        "city": "New York, NY, USA",
        "seniority_level": "Senior (5+ years)",
        "skills": ["Python", "Machine Learning", "SQL"],
    })

Usage (CLI):
    python -m pipeline.predict
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import COL_INDEX, FAANG
from utils.text_utils import is_faang, infer_seniority
from pipeline.preprocessing import FeatureEngineer
from pipeline.model import SalaryPredictor

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Module-level singletons (loaded once)
# ──────────────────────────────────────────────
_feature_engineer: Optional[FeatureEngineer] = None
_predictor: Optional[SalaryPredictor] = None

DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")


def _ensure_loaded(model_dir: str = DEFAULT_MODEL_DIR) -> None:
    """Load feature engineer and predictor if not already loaded."""
    global _feature_engineer, _predictor

    if _feature_engineer is None:
        _feature_engineer = FeatureEngineer()
        _feature_engineer.load(model_dir)
        logger.info("Feature engineer loaded from %s", model_dir)

    if _predictor is None:
        _predictor = SalaryPredictor()
        _predictor.load(model_dir)
        logger.info("Predictor loaded from %s", model_dir)


def predict_salary(input_dict: Dict, model_dir: str = DEFAULT_MODEL_DIR) -> Dict:
    """
    Predict salary for a single job specification.

    Input dict keys:
        job_title (str): Required. Job title.
        city (str): Required. City name from SCRAPE_CITIES.
        seniority_level (str): Optional. Seniority label.
        skills (list[str]): Optional. List of skill names.
        experience_years (float): Optional. Years of experience.
        employment_type (str): Optional. e.g. "Full-time".
        remote_type (str): Optional. "Remote", "Hybrid", "On-site".
        company_name (str): Optional. Company name.
        education_required (str): Optional. e.g. "Bachelor's".
        has_equity (bool): Optional. Has equity compensation.
        has_bonus (bool): Optional. Has bonus compensation.

    Args:
        input_dict: Job specification dict.
        model_dir: Path to model artifacts directory.

    Returns:
        Rich prediction result dict from SalaryPredictor.predict_single().
    """
    _ensure_loaded(model_dir)

    # Convert input_dict to single-row DataFrame in scraper output format
    row = _build_scraper_format_row(input_dict)
    row_df = pd.DataFrame([row])

    # Transform to feature space
    features = _feature_engineer.transform(row_df)

    # Predict
    feature_row = features.iloc[0].to_dict()
    result = _predictor.predict_single(feature_row)

    # Fallback: if prediction is 0 or None, use training median from metadata
    if not result.get("predicted_salary_usd"):
        meta_path = os.path.join(model_dir, "metadata.json")
        fallback = 82500  # hard default
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
            fallback = meta.get("salary_mean", fallback)
        logger.warning("Prediction was 0/None — using fallback salary $%.0f", fallback)
        result["predicted_salary_usd"] = int(fallback)
        result["confidence_low"] = int(fallback * 0.7)
        result["confidence_high"] = int(fallback * 1.3)

    return result


def _build_scraper_format_row(input_dict: Dict) -> Dict:
    """
    Convert a user-friendly input dict to a scraper-output-format row.

    Maps:
    - skills list → comma-joined string for skills_required
    - experience_years → "X+ years" string for experience_required
    - company_name → is_faang check
    - city → col_index lookup
    """
    title = input_dict.get("job_title", "")
    city = input_dict.get("city", "")
    company = input_dict.get("company_name", "")

    # Skills list → comma-separated string
    skills = input_dict.get("skills", [])
    skills_str = ", ".join(skills) if skills else None

    # Experience years → experience string
    exp_years = input_dict.get("experience_years")
    if exp_years is not None:
        exp_str = f"{int(exp_years)}+ years"
    else:
        exp_str = None

    # Seniority
    seniority = input_dict.get("seniority_level")
    if not seniority:
        seniority = infer_seniority(title)

    row = {
        "job_title": title,
        "company_name": company,
        "city": city,
        "location": city,
        "salary": None,
        "salary_currency": "USD",
        "salary_usd_numeric": np.nan,
        "seniority_level": seniority,
        "experience_required": exp_str,
        "employment_type": input_dict.get("employment_type", "Full-time"),
        "remote_type": input_dict.get("remote_type", "On-site"),
        "industry": input_dict.get("industry"),
        "education_required": input_dict.get("education_required"),
        "has_equity": 1 if input_dict.get("has_equity") else 0,
        "has_bonus": 1 if input_dict.get("has_bonus") else 0,
        "has_remote_benefits": 1 if input_dict.get("remote_type") in ("Remote", "Hybrid") else 0,
        "skills_required": skills_str,
        "job_description": input_dict.get("job_description", ""),
        "job_link": "",
        "job_id": "",
        "source_website": input_dict.get("source_website", "LinkedIn"),
        "dedup_key": "",
        "is_faang": is_faang(company),
        "cost_of_living_index": COL_INDEX.get(city, 80),
        "date_posted_raw": None,
        "applicant_count": None,
        "currency": "USD",
    }

    # Add company_rating if provided
    if "company_rating" in input_dict:
        row["company_rating"] = input_dict["company_rating"]

    return row


# ──────────────────────────────────────────────
# Interactive CLI mode
# ──────────────────────────────────────────────

def interactive_predict():
    """Interactive CLI for salary prediction."""
    print(f"\n{'='*60}")
    print(f" 🔮 JOBLENS SALARY PREDICTOR — Interactive Mode")
    print(f"{'='*60}\n")

    # Check if model exists
    if not os.path.exists(os.path.join(DEFAULT_MODEL_DIR, "model.pkl")):
        print("❌ No trained model found. Run training first:")
        print("   python -m pipeline.train --data output/jobs_master.csv")
        return

    while True:
        try:
            # Get inputs
            title = input("\n 📋 Job title (or 'quit'): ").strip()
            if title.lower() in ("quit", "exit", "q"):
                print("\nGoodbye! 👋\n")
                break

            city = input(" 🌍 City (e.g. 'New York, NY, USA'): ").strip()
            seniority = input(" 📈 Seniority (e.g. 'Senior (5+ years)') [Enter to auto]: ").strip() or None
            skills_input = input(" 🛠  Skills (comma-separated): ").strip()
            skills = [s.strip() for s in skills_input.split(",") if s.strip()] if skills_input else []

            # Predict
            result = predict_salary({
                "job_title": title,
                "city": city,
                "seniority_level": seniority,
                "skills": skills,
            })

            # Display result
            print(f"\n {'='*50}")
            print(f" 💰 PREDICTION RESULT")
            print(f" {'='*50}")
            print(f"  Predicted salary:  ${result['predicted_salary_usd']:,}")
            print(f"  Confidence range:  ${result['confidence_low']:,} — ${result['confidence_high']:,}")
            print(f"  Salary percentile: {result['percentile']}th")
            print(f"  Similar jobs:      {result['similar_jobs_count']}")
            print(f"  Model:             {result['model_name']} v{result['model_version']}")

            if result.get("top_features"):
                print(f"\n  📊 Top contributing features:")
                for feat in result["top_features"]:
                    print(f"     {feat['feature']:<25} = {feat['value']}  ({feat['impact']})")

            print(f" {'='*50}")

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.exception("Prediction error")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    interactive_predict()
