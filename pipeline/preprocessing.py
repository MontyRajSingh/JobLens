"""
preprocessing.py — FeatureEngineer class for ML feature creation.

Transforms cleaned job data into model-ready features across 5 groups:
  A) Numeric (scaled): experience_midpoint, seniority_score, word counts, etc.
  B) Binary flags: is_remote, is_faang, has_equity, role type flags, etc.
  C) Skill one-hot: one column per skill from SKILL_LIST
  D) City one-hot: one column per unique city
  E) Source one-hot: source_linkedin, source_indeed, source_glassdoor

Provides fit_transform() for training and transform() for inference.
Never refits encoders at inference time.
"""

import os
import json
import logging
from typing import Optional, List, Dict

import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import StandardScaler

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import SKILL_LIST, COL_INDEX
from utils.text_utils import extract_experience

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# City tier mappings
# ──────────────────────────────────────────────
TIER_4_CITIES = {
    "new york", "san francisco", "london", "singapore",
    "sydney", "zurich", "tokyo", "hong kong", "seattle",
    "los angeles", "boston", "washington",
}
TIER_3_CITIES = {
    "chicago", "toronto", "berlin", "amsterdam", "dublin",
    "melbourne", "austin", "denver", "atlanta", "miami",
    "manchester", "edinburgh", "munich", "stockholm", "copenhagen",
}
HIGH_SALARY_COUNTRIES = {
    "United States", "United Kingdom", "Canada", "Australia",
    "Germany", "Singapore",
}


# ──────────────────────────────────────────────
# Seniority score mapping
# ──────────────────────────────────────────────
SENIORITY_SCORE_MAP = {
    "Internship (0 years)": 0,
    "Entry Level (0-2 years)": 1,
    "Associate (1-3 years)": 2,
    "Mid-Level (2-5 years)": 3,
    "Senior (4-7 years)": 4,
    "Senior (5+ years)": 4,
    "Staff (8+ years)": 5,
    "Director (8+ years)": 6,
    "Executive (10+ years)": 6,
}


class FeatureEngineer:
    """
    Feature engineering pipeline with fit/transform separation.

    fit_transform(): learns encoders from training data, transforms it.
    transform(): applies saved encoders for inference (no refitting).
    save()/load(): persist/restore all encoder state.
    """

    def __init__(self):
        self.scaler: Optional[StandardScaler] = None
        self.numeric_columns: List[str] = []
        self.feature_columns: List[str] = []
        self.city_list: List[str] = []
        self._top_cities: List[str] = []
        self.skill_columns: List[str] = []
        self.salary_percentiles: Dict[str, float] = {}
        self.city_target_map: Dict[str, float] = {}
        self.title_target_map: Dict[str, float] = {}
        self.company_rating_mean: float = 3.5  # default fill
        self._fitted = False

    # ──────────────────────────────────────────────
    # fit_transform (training)
    # ──────────────────────────────────────────────

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Learn encoders from training data and transform it.

        Creates all 5 feature groups, fits StandardScaler on numeric features,
        and records salary percentiles. Does NOT include salary_usd_numeric
        as a feature (it is the target).

        Args:
            df: Cleaned DataFrame with salary_usd_numeric column.

        Returns:
            Feature DataFrame ready for model training.
        """
        logger.info("FeatureEngineer: fit_transform on %d rows", len(df))
        df = df.copy()

        # Save salary percentiles from training data
        salary_col = df["salary_usd_numeric"].dropna()
        if len(salary_col) > 0:
            self.salary_percentiles = {
                "p10": float(np.percentile(salary_col, 10)),
                "p25": float(np.percentile(salary_col, 25)),
                "p50": float(np.percentile(salary_col, 50)),
                "p75": float(np.percentile(salary_col, 75)),
                "p90": float(np.percentile(salary_col, 90)),
            }

        # Company rating mean from training data
        if "company_rating" in df.columns:
            valid_ratings = df["company_rating"].dropna()
            if len(valid_ratings) > 0:
                self.company_rating_mean = float(valid_ratings.mean())

        # Build all feature groups
        features = pd.DataFrame(index=df.index)

        # GROUP A — Numeric (includes city_tier)
        numeric_df = self._build_numeric_features(df)
        features = pd.concat([features, numeric_df], axis=1)

        # GROUP B — Binary flags
        binary_df = self._build_binary_features(df)
        features = pd.concat([features, binary_df], axis=1)

        # GROUP C — Skill one-hot
        skill_df = self._build_skill_features(df)
        features = pd.concat([features, skill_df], axis=1)
        self.skill_columns = list(skill_df.columns)

        # GROUP D — Target Encoding for City
        city_means = df.groupby("city")["salary_usd_numeric"].mean().to_dict()
        self.city_target_map = city_means
        features["city_target_encoded"] = df["city"].map(self.city_target_map).fillna(df["salary_usd_numeric"].mean())
        
        # GROUP D2 — Target Encoding for Title
        title_means = df.groupby("job_title")["salary_usd_numeric"].mean().to_dict()
        self.title_target_map = title_means
        features["title_target_encoded"] = df["job_title"].map(self.title_target_map).fillna(df["salary_usd_numeric"].mean())

        # GROUP D3 — City one-hot (TOP 100 only)
        city_counts = df["city"].value_counts()
        self._top_cities = city_counts.head(100).index.tolist()
        self.city_list = self._top_cities  # for backward compat
        city_df = self._build_city_features(df, self._top_cities)
        features = pd.concat([features, city_df], axis=1)

        # GROUP E — Source one-hot
        source_df = self._build_source_features(df)
        features = pd.concat([features, source_df], axis=1)

        # Fill any remaining NaN with 0
        features = features.fillna(0)

        # Fit scaler on numeric columns
        self.numeric_columns = list(numeric_df.columns)
        self.scaler = StandardScaler()
        features[self.numeric_columns] = self.scaler.fit_transform(
            features[self.numeric_columns]
        )

        self.feature_columns = list(features.columns)
        self._fitted = True

        logger.info("FeatureEngineer: %d feature columns created", len(self.feature_columns))
        return features

    # ──────────────────────────────────────────────
    # transform (inference)
    # ──────────────────────────────────────────────

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform new data using saved encoders (no refitting).

        Args:
            df: DataFrame in scraper output format.

        Returns:
            Feature DataFrame aligned to training feature columns.
        """
        if not self._fitted:
            raise RuntimeError("FeatureEngineer has not been fitted. Call fit_transform() or load() first.")

        df = df.copy()
        features = pd.DataFrame(index=df.index)

        # GROUP A — Numeric
        numeric_df = self._build_numeric_features(df)
        features = pd.concat([features, numeric_df], axis=1)

        # GROUP B — Binary flags
        binary_df = self._build_binary_features(df)
        features = pd.concat([features, binary_df], axis=1)

        # GROUP C — Skill one-hot (use saved skill columns)
        skill_df = self._build_skill_features(df)
        features = pd.concat([features, skill_df], axis=1)

        # GROUP D — Target Encoding for City
        features["city_target_encoded"] = df["city"].map(self.city_target_map).fillna(np.mean(list(self.city_target_map.values())) if self.city_target_map else 0)

        # GROUP D2 — Target Encoding for Title
        features["title_target_encoded"] = df["job_title"].map(self.title_target_map).fillna(np.mean(list(self.title_target_map.values())) if self.title_target_map else 0)

        # GROUP D3 — City one-hot (use saved top cities)
        city_df = self._build_city_features(df, self._top_cities if self._top_cities else self.city_list)
        features = pd.concat([features, city_df], axis=1)

        # GROUP E — Source one-hot
        source_df = self._build_source_features(df)
        features = pd.concat([features, source_df], axis=1)

        # Fill NaN
        features = features.fillna(0)

        # Ensure all training columns exist (missing → 0)
        for col in self.feature_columns:
            if col not in features.columns:
                features[col] = 0

        # Keep only training columns in order
        features = features[self.feature_columns]

        # Scale numeric columns with saved scaler
        features[self.numeric_columns] = self.scaler.transform(
            features[self.numeric_columns]
        )

        return features

    # ──────────────────────────────────────────────
    # GROUP A — Numeric features
    # ──────────────────────────────────────────────

    def _build_numeric_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build numeric features: experience, seniority score, word counts, etc."""
        nf = pd.DataFrame(index=df.index)

        # experience_midpoint
        nf["experience_midpoint"] = df.apply(
            lambda row: self._parse_experience_midpoint(
                row.get("experience_required"),
                row.get("job_description"),
            ),
            axis=1,
        )

        # seniority_score
        nf["seniority_score"] = df["seniority_level"].map(SENIORITY_SCORE_MAP).fillna(3).astype(int)

        # description_word_count
        nf["description_word_count"] = df["job_description"].apply(
            lambda x: len(str(x).split()) if pd.notna(x) else 0
        ).astype(int)

        # skill_count
        nf["skill_count"] = df["skills_required"].apply(
            lambda x: len(str(x).split(",")) if pd.notna(x) and x else 0
        ).astype(int)

        # title_word_count
        nf["title_word_count"] = df["job_title"].apply(
            lambda x: len(str(x).split()) if pd.notna(x) else 0
        ).astype(int)

        # col_index (cost of living index)
        nf["col_index"] = df["city"].map(COL_INDEX).fillna(80).astype(int)

        # city_tier (1-4 based on city importance)
        nf["city_tier"] = df.apply(
            lambda r: self._compute_city_tier(
                r.get("city", ""),
                r.get("country", ""),
            ),
            axis=1,
        ).astype(int)

        # INTERACTION: experience * seniority
        nf["exp_seniority_interaction"] = nf["experience_midpoint"] * nf["seniority_score"]
        # Fill NaN if experience was missing
        nf["exp_seniority_interaction"] = nf["exp_seniority_interaction"].fillna(0)

        # company_rating
        if "company_rating" in df.columns:
            nf["company_rating"] = df["company_rating"].fillna(self.company_rating_mean)
        else:
            nf["company_rating"] = self.company_rating_mean

        return nf

    @staticmethod
    def _compute_city_tier(city, country) -> int:
        """Map city to tier 1-4 based on importance."""
        city_lower = str(city).lower() if pd.notna(city) else ""
        country_str = str(country) if pd.notna(country) else ""

        # Check tier 4 (highest)
        for t4 in TIER_4_CITIES:
            if t4 in city_lower:
                return 4

        # Check tier 3
        for t3 in TIER_3_CITIES:
            if t3 in city_lower:
                return 3

        # High-salary country → tier 2
        if country_str in HIGH_SALARY_COUNTRIES:
            return 2

        # Rest → tier 1
        return 1

    @staticmethod
    def _parse_experience_midpoint(exp_str, description=None) -> float:
        """Convert experience string to numeric midpoint."""
        if pd.isna(exp_str) or not exp_str:
            # Try to extract from description
            if description and pd.notna(description):
                exp_str = extract_experience(str(description))
            if not exp_str:
                return np.nan

        exp = str(exp_str).lower().strip()

        # Keyword mappings
        if "fresher" in exp or "internship" in exp:
            return 0.0
        if "entry" in exp:
            return 0.5

        # Range: "3-5 years" → 4.0
        import re
        match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)", exp)
        if match:
            return (int(match.group(1)) + int(match.group(2))) / 2

        # Single: "5+ years" → 6.0  or "5 years" → 5.0
        match = re.search(r"(\d+)\s*\+", exp)
        if match:
            return int(match.group(1)) + 1.0

        match = re.search(r"(\d+)\s*years?", exp)
        if match:
            return float(match.group(1))

        return np.nan

    # ──────────────────────────────────────────────
    # GROUP B — Binary flags
    # ──────────────────────────────────────────────

    def _build_binary_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build binary 0/1 flag features."""
        bf = pd.DataFrame(index=df.index)

        # Remote/Hybrid
        remote_col = df["remote_type"].fillna("") if "remote_type" in df.columns else pd.Series("", index=df.index)
        bf["is_remote"] = remote_col.str.lower().str.contains("remote").astype(int)
        bf["is_hybrid"] = remote_col.str.lower().str.contains("hybrid").astype(int)

        # FAANG
        bf["is_faang"] = df["is_faang"].replace({"False": 0, "True": 1, False: 0, True: 1}).fillna(0).astype(int) if "is_faang" in df.columns else 0

        # Equity / Bonus
        bf["has_equity"] = df["has_equity"].replace({"False": 0, "True": 1, False: 0, True: 1}).fillna(0).astype(int) if "has_equity" in df.columns else 0
        bf["has_bonus"] = df["has_bonus"].replace({"False": 0, "True": 1, False: 0, True: 1}).fillna(0).astype(int) if "has_bonus" in df.columns else 0

        # Employment type flags
        emp_col = df["employment_type"].fillna("").str.lower() if "employment_type" in df.columns else pd.Series("", index=df.index)
        bf["is_contract"] = emp_col.str.contains("contract").astype(int)
        bf["is_internship"] = emp_col.str.contains("internship|intern").astype(int)
        bf["is_full_time"] = emp_col.str.contains("full").astype(int)

        # Education flags
        edu_col = df["education_required"].fillna("").str.lower() if "education_required" in df.columns else pd.Series("", index=df.index)
        bf["requires_phd"] = edu_col.str.contains("ph\\.?d|doctorate").astype(int)
        bf["requires_masters"] = edu_col.str.contains("master|m\\.?s\\.?|mba|m\\.?tech").astype(int)
        bf["requires_bachelors"] = edu_col.str.contains("bachelor|b\\.?s\\.?|b\\.?tech").astype(int)

        # Title-based role flags
        title_lower = df["job_title"].fillna("").str.lower()
        bf["is_senior_title"] = title_lower.str.contains("senior|sr\\.|sr |lead").astype(int)
        bf["is_ml_role"] = title_lower.str.contains("machine learning|\\bml\\b|\\bai\\b").astype(int)
        bf["is_ds_role"] = title_lower.str.contains("data scien").astype(int)
        bf["is_sde_role"] = title_lower.str.contains("software engineer|\\bsde\\b|developer").astype(int)
        
        # High-level Seniority Flags
        bf["is_staff_principal"] = title_lower.str.contains("staff|principal|fellow|distinguished").astype(int)
        bf["is_manager_vp"] = title_lower.str.contains("manager|director|vp|vice president|head of|chief").astype(int)

        # DOMAIN SPECIALIZATION (Clustered Skills)
        skills_lower = df["skills_required"].fillna("").str.lower()
        
        # Cloud/DevOps
        cloud_keywords = ["aws", "gcp", "azure", "docker", "kubernetes", "terraform", "devops", "ci/cd", "cloud"]
        bf["is_cloud_expert"] = skills_lower.apply(lambda x: 1 if any(k in x for k in cloud_keywords) else 0)
        
        # Data/AI/ML
        ai_keywords = ["machine learning", "deep learning", "nlp", "llm", "genai", "pytorch", "tensorflow", "data science", "ai"]
        bf["is_ai_expert"] = skills_lower.apply(lambda x: 1 if any(k in x for k in ai_keywords) else 0)
        
        # Data Engineering/Backend
        backend_keywords = ["sql", "postgresql", "mongodb", "redis", "kafka", "spark", "hadoop", "data engineering", "backend"]
        bf["is_backend_expert"] = skills_lower.apply(lambda x: 1 if any(k in x for k in backend_keywords) else 0)
        
        # Frontend/Web
        web_keywords = ["react", "angular", "vue", "javascript", "typescript", "frontend", "web", "node.js"]
        bf["is_web_expert"] = skills_lower.apply(lambda x: 1 if any(k in x for k in web_keywords) else 0)

        return bf

    # ──────────────────────────────────────────────
    # GROUP C — Skill one-hot
    # ──────────────────────────────────────────────

    def _build_skill_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create one-hot columns for each skill in SKILL_LIST."""
        sf = pd.DataFrame(0, index=df.index, columns=[
            f"skill_{s.lower().replace(' ', '_').replace('/', '_')}" for s in SKILL_LIST
        ])

        skills_col = df["skills_required"].fillna("") if "skills_required" in df.columns else pd.Series("", index=df.index)

        for idx in df.index:
            skills_text = str(skills_col.at[idx]).lower()
            if not skills_text:
                continue
            for skill in SKILL_LIST:
                col_name = f"skill_{skill.lower().replace(' ', '_').replace('/', '_')}"
                if skill.lower() in skills_text:
                    sf.at[idx, col_name] = 1

        return sf

    # ──────────────────────────────────────────────
    # GROUP D — City one-hot
    # ──────────────────────────────────────────────

    def _build_city_features(self, df: pd.DataFrame, city_list: List[str]) -> pd.DataFrame:
        """Create one-hot columns for each city in city_list."""
        cf = pd.DataFrame(0, index=df.index, columns=[
            f"city_{c.lower().replace(' ', '_').replace(',', '').replace('.', '')}" for c in city_list
        ])

        city_col = df["city"].fillna("") if "city" in df.columns else pd.Series("", index=df.index)

        for idx in df.index:
            city = str(city_col.at[idx])
            col_name = f"city_{city.lower().replace(' ', '_').replace(',', '').replace('.', '')}"
            if col_name in cf.columns:
                cf.at[idx, col_name] = 1

        return cf

    # ──────────────────────────────────────────────
    # GROUP E — Source one-hot
    # ──────────────────────────────────────────────

    def _build_source_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create source one-hot: source_linkedin, source_indeed, source_glassdoor."""
        source_col = df["source_website"].fillna("").str.lower() if "source_website" in df.columns else pd.Series("", index=df.index)
        ef = pd.DataFrame(index=df.index)
        ef["source_linkedin"] = source_col.str.contains("linkedin").astype(int)
        ef["source_indeed"] = source_col.str.contains("indeed").astype(int)
        ef["source_glassdoor"] = source_col.str.contains("glassdoor").astype(int)
        return ef

    # ──────────────────────────────────────────────
    # save / load
    # ──────────────────────────────────────────────

    def save(self, model_dir: str) -> None:
        """
        Save all encoder state to model_dir.

        Writes:
        - feature_scaler.pkl (StandardScaler)
        - feature_state.json (city_list, salary_percentiles, company_rating_mean)
        - feature_columns.json (ordered feature column names)
        """
        os.makedirs(model_dir, exist_ok=True)

        joblib.dump(self.scaler, os.path.join(model_dir, "feature_scaler.pkl"))

        state = {
            "city_list": self.city_list,
            "top_cities": self._top_cities,
            "numeric_columns": self.numeric_columns,
            "skill_columns": self.skill_columns,
            "city_target_map": self.city_target_map,
            "title_target_map": self.title_target_map,
            "salary_percentiles": self.salary_percentiles,
            "company_rating_mean": self.company_rating_mean,
        }
        with open(os.path.join(model_dir, "feature_state.json"), "w") as f:
            json.dump(state, f, indent=2)

        with open(os.path.join(model_dir, "feature_columns.json"), "w") as f:
            json.dump(self.feature_columns, f, indent=2)

        logger.info("FeatureEngineer saved to %s", model_dir)

    def load(self, model_dir: str) -> None:
        """
        Restore all encoder state from model_dir.

        Reads feature_scaler.pkl, feature_state.json, feature_columns.json.
        """
        self.scaler = joblib.load(os.path.join(model_dir, "feature_scaler.pkl"))

        with open(os.path.join(model_dir, "feature_state.json"), "r") as f:
            state = json.load(f)

        self.city_list = state["city_list"]
        self._top_cities = state.get("top_cities", state["city_list"])
        self.numeric_columns = state["numeric_columns"]
        self.skill_columns = state.get("skill_columns", [])
        self.city_target_map = state.get("city_target_map", {})
        self.title_target_map = state.get("title_target_map", {})
        self.salary_percentiles = state["salary_percentiles"]
        self.company_rating_mean = state.get("company_rating_mean", 3.5)

        with open(os.path.join(model_dir, "feature_columns.json"), "r") as f:
            self.feature_columns = json.load(f)

        self._fitted = True
        logger.info("FeatureEngineer loaded from %s (%d features)", model_dir, len(self.feature_columns))
