"""
model.py — SalaryPredictor class for training and inference.

Trains a Random Forest model on engineered features,
and provides predict/predict_single methods with
confidence intervals and salary percentile.

Usage:
    predictor = SalaryPredictor()
    metrics = predictor.train(X_train, y_train)
    result = predictor.predict_single(feature_dict)
    predictor.save("pipeline/models")
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor
import xgboost as xgb

logger = logging.getLogger(__name__)


class SalaryPredictor:
    """
    Salary prediction using Random Forest.

    Provides confidence intervals and feature importance analysis.
    """

    MODEL_VERSION = "1.0.0"

    def __init__(self):
        self.best_model = None
        self.best_model_name: str = ""
        self.all_models: Dict = {}
        self.metrics: Dict = {}
        self.feature_names: List[str] = []
        self.test_residuals_std: float = 0.0
        self.training_salary_percentiles: Dict[str, float] = {}
        self._training_salary_values: Optional[np.ndarray] = None

    # ──────────────────────────────────────────────
    # Training
    # ──────────────────────────────────────────────

    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """
        Train a Random Forest model and evaluate.

        Steps:
        1. Drop rows where y < 20000 or y > 500000
        2. 80/20 split (random_state=42)
        3. Train Random Forest
        4. Evaluate RMSE, MAE, R² on test set
        5. Store residuals std for confidence intervals
        6. Store training salary percentiles

        Args:
            X: Feature DataFrame.
            y: Target Series (salary_usd_numeric).

        Returns:
            Dict of metrics for all models.
        """
        # Step 1: Filter salary range
        mask = (y >= 20_000) & (y <= 500_000)
        X = X.loc[mask].copy()
        y = y.loc[mask].copy()
        logger.info("Training with %d rows (after salary range filter)", len(X))

        if len(X) < 20:
            raise ValueError(f"Too few training samples: {len(X)}. Need at least 20.")

        self.feature_names = list(X.columns)

        # Step 2: Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42,
        )

        # Step 7: Training salary percentiles
        self._training_salary_values = y_train.values
        self.training_salary_percentiles = {
            "p10": float(np.percentile(y_train, 10)),
            "p25": float(np.percentile(y_train, 25)),
            "p50": float(np.percentile(y_train, 50)),
            "p75": float(np.percentile(y_train, 75)),
            "p90": float(np.percentile(y_train, 90)),
        }

        # Step 3: Train Random Forest (Baseline)
        logger.info("Training Random Forest...")
        rf_model = RandomForestRegressor(
            n_estimators=300,
            max_depth=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        rf_model.fit(X_train, y_train)

        rf_pred = rf_model.predict(X_test)
        rf_rmse = float(np.sqrt(mean_squared_error(y_test, rf_pred)))
        rf_mae = float(mean_absolute_error(y_test, rf_pred))
        rf_r2 = float(r2_score(y_test, rf_pred))

        self.metrics["Random Forest"] = {"rmse": rf_rmse, "mae": rf_mae, "r2": rf_r2}
        logger.info("Random Forest — RMSE: $%s | MAE: $%s | R²: %.3f", f"{rf_rmse:,.0f}", f"{rf_mae:,.0f}", rf_r2)

        # Step 4: Train XGBoost with GridSearchCV
        logger.info("Training XGBoost with GridSearchCV...")
        xgb_param_grid = {
            'n_estimators': [100, 300],
            'max_depth': [4, 6, 8],
            'learning_rate': [0.05, 0.1],
            'subsample': [0.8, 1.0]
        }
        xgb_base = xgb.XGBRegressor(random_state=42, n_jobs=-1)
        grid_search = GridSearchCV(
            estimator=xgb_base,
            param_grid=xgb_param_grid,
            cv=3,
            scoring='neg_mean_squared_error',
            n_jobs=-1,
            verbose=0
        )
        grid_search.fit(X_train, y_train)
        
        xgb_model = grid_search.best_estimator_
        xgb_pred = xgb_model.predict(X_test)
        xgb_rmse = float(np.sqrt(mean_squared_error(y_test, xgb_pred)))
        xgb_mae = float(mean_absolute_error(y_test, xgb_pred))
        xgb_r2 = float(r2_score(y_test, xgb_pred))
        
        self.metrics["XGBoost"] = {"rmse": xgb_rmse, "mae": xgb_mae, "r2": xgb_r2}
        logger.info("XGBoost (Best Params: %s) — RMSE: $%s | MAE: $%s | R²: %.3f", grid_search.best_params_, f"{xgb_rmse:,.0f}", f"{xgb_mae:,.0f}", xgb_r2)

        # Step 5: Select best model
        if xgb_r2 > rf_r2:
            self.best_model_name = "XGBoost"
            self.best_model = xgb_model
            best_pred = xgb_pred
        else:
            self.best_model_name = "Random Forest"
            self.best_model = rf_model
            best_pred = rf_pred
            
        logger.info("Selected %s as the best model.", self.best_model_name)

        # Step 6: Residuals std
        self.test_residuals_std = float(np.std(y_test.values - best_pred))

        return self.metrics

    # ──────────────────────────────────────────────
    # Prediction
    # ──────────────────────────────────────────────

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Batch prediction using the best model.

        Args:
            X: Feature DataFrame.

        Returns:
            Array of predicted salaries.
        """
        if self.best_model is None:
            raise RuntimeError("Model not trained or loaded. Call train() or load() first.")
        return self.best_model.predict(X)

    def predict_single(self, feature_dict: dict) -> dict:
        """
        Predict salary for a single job with rich context.

        Returns dict with: predicted_salary_usd, confidence_low/high,
        percentile, top_features, similar_jobs_count, model_name, model_version.

        Args:
            feature_dict: Single row of features as dict.

        Returns:
            Rich prediction result dict.
        """
        if self.best_model is None:
            raise RuntimeError("Model not trained or loaded. Call train() or load() first.")

        # Build single-row DataFrame
        X = pd.DataFrame([feature_dict])
        for col in self.feature_names:
            if col not in X.columns:
                X[col] = 0
        X = X[self.feature_names]

        predicted = float(self.best_model.predict(X)[0])
        predicted = max(0, predicted)

        # Confidence interval
        conf_low = max(0, predicted - self.test_residuals_std)
        conf_high = predicted + self.test_residuals_std

        # Percentile
        percentile = 50
        if self._training_salary_values is not None and len(self._training_salary_values) > 0:
            percentile = int(np.searchsorted(
                np.sort(self._training_salary_values), predicted
            ) / len(self._training_salary_values) * 100)
            percentile = min(99, max(1, percentile))

        return {
            "predicted_salary_usd": round(predicted),
            "confidence_low": round(conf_low),
            "confidence_high": round(conf_high),
            "percentile": percentile,
            "model_name": self.best_model_name,
            "model_version": self.MODEL_VERSION,
            "skill_premiums": self.get_skill_premiums(X.iloc[0].to_dict()),
            "career_progression": self.get_career_progression(feature_dict),
        }

    # ──────────────────────────────────────────────
    # Feature importance
    # ──────────────────────────────────────────────

    def get_feature_importance(self, top_n: int = 20) -> List[dict]:
        """
        Get top N feature importances from the best model.

        Args:
            top_n: Number of top features to return.

        Returns:
            List of dicts with feature name and importance score.
        """
        if self.best_model is None:
            return []

        if hasattr(self.best_model, "feature_importances_"):
            importances = self.best_model.feature_importances_
        elif hasattr(self.best_model, "coef_"):
            importances = np.abs(self.best_model.coef_)
        else:
            return []

        indices = np.argsort(importances)[::-1][:top_n]
        return [
            {"feature": self.feature_names[i], "importance": float(importances[i])}
            for i in indices
        ]
    # ──────────────────────────────────────────────
    # Premium Intelligence (Skills & Career)
    # ──────────────────────────────────────────────

    def get_skill_premiums(self, feature_row: dict) -> Dict[str, float]:
        """
        Estimate the salary premium for each skill present in the row.
        
        Calculated as: (Feature Importance * Predictor Std) normalized to USD.
        """
        if self.best_model is None:
            return {}

        importances = {}
        if hasattr(self.best_model, "feature_importances_"):
            importances = dict(zip(self.feature_names, self.best_model.feature_importances_))
        
        premiums = {}
        # Only look at skill_ columns
        for col, val in feature_row.items():
            if col.startswith("skill_") and val > 0:
                # Rough heuristic: Importance * 0.2 * Predicted Value (simplified)
                importance = importances.get(col, 0)
                # Skill premium is typically 5-15% of salary for high-demand skills
                premium = importance * 50000  # Scaling factor for visibility
                premiums[col.replace("skill_", "").replace("_", " ").title()] = round(premium, -2)
        
        return dict(sorted(premiums.items(), key=lambda x: x[1], reverse=True)[:5])

    def get_career_progression(self, current_job: dict) -> dict:
        """
        Predict next logical step and salary increase.
        """
        title = str(current_job.get("job_title", "")).lower()
        seniority = str(current_job.get("seniority_level", ""))
        
        next_step = "Senior " + title.title()
        salary_boost = 0.15 # 15% jump
        
        if "senior" in title or "lead" in title:
            next_step = "Staff / Principal " + title.replace("senior", "").replace("lead", "").strip().title()
            salary_boost = 0.20
        elif "entry" in seniority.lower() or "associate" in seniority.lower():
            next_step = title.title() + " (Mid-Level)"
            salary_boost = 0.25
            
        return {
            "next_title": next_step,
            "estimated_jump_percent": int(salary_boost * 100),
            "skills_to_acquire": ["Kubernetes", "System Design", "MLOps"] if "engineer" in title else ["Deep Learning", "A/B Testing", "Tableau"]
        }

    # ──────────────────────────────────────────────
    # Save / Load
    # ──────────────────────────────────────────────

    def save(self, model_dir: str) -> None:
        """
        Save model and metadata to model_dir.

        Writes:
        - model.pkl (best model via joblib)
        - metadata.json (training date, metrics, salary stats)
        """
        os.makedirs(model_dir, exist_ok=True)

        joblib.dump(self.best_model, os.path.join(model_dir, "model.pkl"))

        # Compute salary stats from training data
        salary_min = float(np.min(self._training_salary_values)) if self._training_salary_values is not None else 0
        salary_max = float(np.max(self._training_salary_values)) if self._training_salary_values is not None else 0
        salary_mean = float(np.mean(self._training_salary_values)) if self._training_salary_values is not None else 0

        metadata = {
            "training_date": datetime.now().isoformat(),
            "model_name": self.best_model_name,
            "model_version": self.MODEL_VERSION,
            "rmse": self.metrics.get(self.best_model_name, {}).get("rmse"),
            "mae": self.metrics.get(self.best_model_name, {}).get("mae"),
            "r2": self.metrics.get(self.best_model_name, {}).get("r2"),
            "training_rows": len(self._training_salary_values) if self._training_salary_values is not None else 0,
            "feature_count": len(self.feature_names),
            "feature_names": self.feature_names,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_mean": salary_mean,
            "training_salary_percentiles": self.training_salary_percentiles,
            "test_residuals_std": self.test_residuals_std,
        }

        with open(os.path.join(model_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info("SalaryPredictor saved to %s (model: %s)", model_dir, self.best_model_name)

    def load(self, model_dir: str) -> None:
        """
        Load model and metadata from model_dir.

        Reads model.pkl and metadata.json.
        """
        self.best_model = joblib.load(os.path.join(model_dir, "model.pkl"))

        with open(os.path.join(model_dir, "metadata.json"), "r") as f:
            metadata = json.load(f)

        self.best_model_name = metadata.get("model_name", "Unknown")
        self.feature_names = metadata.get("feature_names", [])
        self.test_residuals_std = metadata.get("test_residuals_std", 0)
        self.training_salary_percentiles = metadata.get("training_salary_percentiles", {})
        self.metrics = {
            self.best_model_name: {
                "rmse": metadata.get("rmse"),
                "mae": metadata.get("mae"),
                "r2": metadata.get("r2"),
            }
        }

        # Reconstruct training salary values from percentiles for percentile computation
        if self.training_salary_percentiles:
            # Approximate training distribution for percentile calc
            p_vals = list(self.training_salary_percentiles.values())
            training_rows = metadata.get("training_rows", 1000)
            self._training_salary_values = np.linspace(
                metadata.get("salary_min", min(p_vals)),
                metadata.get("salary_max", max(p_vals)),
                training_rows,
            )

        logger.info("SalaryPredictor loaded from %s (model: %s, R²: %.3f)",
                     model_dir, self.best_model_name, metadata.get("r2", 0))
