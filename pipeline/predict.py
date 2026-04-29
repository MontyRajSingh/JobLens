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
    Predict salary for a single job specification with Skill Premium Intelligence.

    The ML model is trained on a synthetic Kaggle dataset with a narrow salary
    range ($52K–$102K). To produce realistic, market-calibrated predictions,
    we layer transparent heuristic adjustments for seniority, experience,
    city cost-of-living, role type, company tier, and education on top of
    the model's base signal.
    """
    _ensure_loaded(model_dir)

    # 1. Calculate BASE prediction (No skills)
    base_input = input_dict.copy()
    base_input["skills"] = []
    base_row = _build_scraper_format_row(base_input)
    base_features = _feature_engineer.transform(pd.DataFrame([base_row]))
    base_result = _predictor.predict_single(base_features.iloc[0].to_dict())
    base_salary = base_result.get("predicted_salary_usd", 82500)

    # 2. Calculate AI prediction (With skills)
    full_row = _build_scraper_format_row(input_dict)
    full_features = _feature_engineer.transform(pd.DataFrame([full_row]))
    result = _predictor.predict_single(full_features.iloc[0].to_dict())
    model_prediction = int(result.get("predicted_salary_usd", 0))

    # 3. Apply Skill Premium Intelligence (The "Value Lock")
    skill_bonuses = []
    total_market_premium = 0

    premium_path = os.path.join(model_dir, "skill_premiums.json")
    premiums = {}
    if os.path.exists(premium_path):
        with open(premium_path, "r") as f:
            premiums = json.load(f)

    user_skills = input_dict.get("skills", [])
    for skill in user_skills:
        bonus = premiums.get(skill, 500)
        total_market_premium += bonus
        skill_bonuses.append({"skill": skill, "bonus": int(bonus)})

    predicted = result.get("predicted_salary_usd", 0)
    boosted_salary = max(predicted, base_salary + (total_market_premium * 0.5))

    # ──────────────────────────────────────────────────────────────
    # 4. Seniority & Experience Adjustment
    # The model can't differentiate seniority well because the Kaggle
    # salary range is too narrow. We add market-calibrated adjustments.
    # ──────────────────────────────────────────────────────────────
    seniority = str(input_dict.get("seniority_level") or "")
    seniority_bonus = 0
    seniority_label = ""

    SENIORITY_ADJUSTMENTS = {
        "Internship":  (-15000, "Internship Discount"),
        "Entry Level": (-5000,  "Entry Level"),
        "Associate":   (0,      "Associate"),
        "Mid-Level":   (8000,   "Mid-Level Lift"),
        "Senior":      (25000,  "Senior Premium"),
        "Staff":       (45000,  "Staff Premium"),
        "Director":    (55000,  "Director Premium"),
        "Executive":   (70000,  "Executive Premium"),
    }
    for key, (adj, label) in SENIORITY_ADJUSTMENTS.items():
        if key.lower() in seniority.lower():
            seniority_bonus = adj
            seniority_label = label
            break

    # Experience years — additional lift beyond seniority
    exp_years = input_dict.get("experience_years")
    exp_bonus = 0
    if exp_years is not None:
        exp_years = int(exp_years)
        # Roughly $2K per year of experience, diminishing after 10
        if exp_years <= 10:
            exp_bonus = exp_years * 2000
        else:
            exp_bonus = 20000 + (exp_years - 10) * 1000

    # ──────────────────────────────────────────────────────────────
    # 5. City / Geography Adjustment
    # Different cities have dramatically different salary bands.
    # ──────────────────────────────────────────────────────────────
    city = str(input_dict.get("city") or "").lower()
    city_bonus = 0
    city_label = ""

    CITY_ADJUSTMENTS = {
        # Tier 1: Highest-paying tech hubs
        "san francisco": (30000, "SF Bay Area Premium"),
        "new york":      (25000, "NYC Premium"),
        "seattle":       (22000, "Seattle Tech Hub"),
        "los angeles":   (15000, "LA Premium"),
        "boston":         (15000, "Boston Premium"),
        "washington":    (12000, "DC Metro Premium"),
        "san jose":      (28000, "Silicon Valley Premium"),
        "palo alto":     (30000, "Silicon Valley Premium"),
        # Tier 2: Strong tech markets
        "austin":        (8000,  "Austin Tech Hub"),
        "denver":        (7000,  "Denver Premium"),
        "chicago":       (8000,  "Chicago Premium"),
        "atlanta":       (5000,  "Atlanta Premium"),
        "miami":         (5000,  "Miami Premium"),
        # International
        "london":        (18000, "London Premium"),
        "zurich":        (35000, "Zurich Premium"),
        "singapore":     (15000, "Singapore Premium"),
        "tokyo":         (10000, "Tokyo Premium"),
        "sydney":        (12000, "Sydney Premium"),
        "toronto":       (8000,  "Toronto Premium"),
        "berlin":        (5000,  "Berlin Premium"),
        "amsterdam":     (8000,  "Amsterdam Premium"),
        "dublin":        (10000, "Dublin Tech Hub"),
        "bangalore":     (-15000, "India Market Rate"),
        "mumbai":        (-12000, "India Market Rate"),
        "hyderabad":     (-15000, "India Market Rate"),
    }
    for city_key, (adj, label) in CITY_ADJUSTMENTS.items():
        if city_key in city:
            city_bonus = adj
            city_label = label
            break

    # ──────────────────────────────────────────────────────────────
    # 6. Role-Type Adjustment
    # ML/AI roles pay more than general SWE, which pays more than QA.
    # ──────────────────────────────────────────────────────────────
    title = str(input_dict.get("job_title") or "").lower()
    role_bonus = 0
    role_label = ""

    if any(kw in title for kw in ["machine learning", " ml ", "ai ", "artificial intelligence"]):
        role_bonus = 15000
        role_label = "ML/AI Specialist"
    elif any(kw in title for kw in ["data scientist", "data science"]):
        role_bonus = 10000
        role_label = "Data Science"
    elif any(kw in title for kw in ["backend", "full stack", "fullstack", "platform"]):
        role_bonus = 5000
        role_label = "Engineering"
    elif any(kw in title for kw in ["frontend", "ui ", "ux "]):
        role_bonus = 2000
        role_label = "Frontend/Design"
    elif any(kw in title for kw in ["devops", "sre", "infrastructure", "cloud"]):
        role_bonus = 8000
        role_label = "DevOps/Infra"
    elif any(kw in title for kw in ["security", "cybersecurity"]):
        role_bonus = 10000
        role_label = "Security"
    elif any(kw in title for kw in ["manager", "director", "vp", "vice president", "head of", "chief"]):
        role_bonus = 20000
        role_label = "Leadership"
    elif any(kw in title for kw in ["qa", "test", "quality"]):
        role_bonus = -5000
        role_label = "QA/Testing"

    # ──────────────────────────────────────────────────────────────
    # 7. Company Tier Prestige (The "Brand Bonus")
    # ──────────────────────────────────────────────────────────────
    company_name = str(input_dict.get("company_name") or "").lower()
    tier_info = {"tier": 3, "label": "Tier 3: Standard", "bonus": 0}

    tier_path = os.path.join(model_dir, "company_tiers.json")
    if os.path.exists(tier_path):
        with open(tier_path, "r") as f:
            tiers = json.load(f)

        if any(c.lower() in company_name for c in tiers["Tier 1"]["companies"]):
            tier_info = {"tier": 1, "label": "Tier 1: Prestige", "bonus": 45000}
        elif any(c.lower() in company_name for c in tiers["Tier 2"]["companies"]):
            tier_info = {"tier": 2, "label": "Tier 2: Scale", "bonus": 15000}

    # ──────────────────────────────────────────────────────────────
    # 8. Academic Intelligence (Degree Bonus)
    # ──────────────────────────────────────────────────────────────
    education = str(input_dict.get("education_required") or "").lower()
    edu_bonus = 0
    edu_label = ""

    if "phd" in education or "doctorate" in education:
        edu_bonus = 25000
        edu_label = "PhD Specialist Premium"
    elif "master" in education:
        edu_bonus = 10000
        edu_label = "Master's Degree Lift"

    # ──────────────────────────────────────────────────────────────
    # 9. Remote work adjustment
    # ──────────────────────────────────────────────────────────────
    remote_type = str(input_dict.get("remote_type") or "").lower()
    remote_bonus = 0
    if "remote" in remote_type:
        remote_bonus = -3000  # Remote roles typically slightly lower than on-site

    # ──────────────────────────────────────────────────────────────
    # FINAL: Combine all adjustments
    # ──────────────────────────────────────────────────────────────
    total_adjustments = (
        seniority_bonus + exp_bonus + city_bonus +
        role_bonus + tier_info["bonus"] + edu_bonus +
        remote_bonus + total_market_premium
    )
    boosted_salary = boosted_salary + seniority_bonus + exp_bonus + city_bonus + role_bonus + remote_bonus

    # Apply company tier and education (already in original logic)
    boosted_salary += (tier_info["bonus"] + edu_bonus)

    # Floor: never go below $35K
    boosted_salary = max(35000, int(boosted_salary))

    result["predicted_salary_usd"] = boosted_salary
    result["model_prediction_usd"] = model_prediction
    result["adjusted_prediction_usd"] = boosted_salary
    result["base_prediction_usd"] = int(base_salary)
    result["skill_bonuses"] = skill_bonuses
    result["total_skill_premium"] = int(total_market_premium)
    result["company_tier"] = tier_info
    result["academic_bonus"] = {"label": edu_label, "bonus": edu_bonus} if edu_bonus > 0 else None
    result["adjustments"] = {
        "skill_market_premium": int(total_market_premium),
        "seniority_adjustment": int(seniority_bonus),
        "seniority_label": seniority_label,
        "experience_adjustment": int(exp_bonus),
        "city_adjustment": int(city_bonus),
        "city_label": city_label,
        "role_adjustment": int(role_bonus),
        "role_label": role_label,
        "company_tier_bonus": int(tier_info["bonus"]),
        "academic_bonus": int(edu_bonus),
        "remote_adjustment": int(remote_bonus),
        "is_heuristic_adjusted": True,
    }
    result["confidence_method"] = "model_plus_market_heuristics"

    # Confidence band
    if not predicted:
        result["predicted_salary_usd"] = max(35000, int(base_salary + total_adjustments))
        result["adjusted_prediction_usd"] = result["predicted_salary_usd"]
        result["confidence_low"] = int(result["predicted_salary_usd"] * 0.8)
        result["confidence_high"] = int(result["predicted_salary_usd"] * 1.2)
        result["confidence_method"] = "fallback_percentage_band"
    else:
        result["confidence_low"] = int(boosted_salary * 0.85)
        result["confidence_high"] = int(boosted_salary * 1.15)

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
    company = input_dict.get("company_name") or ""

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
        "role": input_dict.get("role", title),  # fallback to job_title
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
        "industry": input_dict.get("industry") or "",
        "education_required": input_dict.get("education_required") or "",
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
    print("\n🔮 JOBLENS SALARY PREDICTOR\n")

    if not os.path.exists(os.path.join(DEFAULT_MODEL_DIR, "model.pkl")):
        print("❌ No trained model found. Run training first.")
        return

    while True:
        try:
            title = input("\nJob title (or 'quit'): ").strip()
            if title.lower() in ("quit", "exit", "q"):
                break

            city = input("City: ").strip()
            seniority = input("Seniority [Enter to auto]: ").strip() or None
            skills_input = input("Skills (comma-separated): ").strip()
            skills = [s.strip() for s in skills_input.split(",")] if skills_input else []

            result = predict_salary({
                "job_title": title,
                "city": city,
                "seniority_level": seniority,
                "skills": skills,
            })

            print(f"\nPredicted salary: ${result['predicted_salary_usd']:,}")
            print(f"Confidence range: ${result['confidence_low']:,} — ${result['confidence_high']:,}")
            print(f"Percentile: {result['percentile']}th")
            print(f"Model: {result['model_name']} v{result['model_version']}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    interactive_predict()
