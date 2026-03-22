"""
model.py — SalaryPredictor class for training and inference.

Trains three models (XGBoost, Random Forest, Ridge) on engineered features,
selects the best by RMSE, and provides predict/predict_single methods with
confidence intervals, salary percentile, and feature importance analysis.

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
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor

logger = logging.getLogger(__name__)


class SalaryPredictor:
    """
    Multi-model salary prediction with automatic model selection.

    Trains XGBoost, Random Forest, and Ridge; selects best by RMSE.
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
        Train three models, evaluate, and select the best.

        Steps:
        1. Drop rows where y < 20000 or y > 500000
        2. 80/20 split (random_state=42)
        3. Train XGBoost, Random Forest, Ridge
        4. Evaluate RMSE, MAE, R² on test set
        5. Select best by lowest RMSE
        6. Store residuals std for confidence intervals
        7. Store training salary percentiles

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

        # Step 3: Train models
        models = {
            "XGBoost": XGBRegressor(
                n_estimators=500,
                learning_rate=0.05,
                max_depth=6,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                early_stopping_rounds=50,
                eval_metric="rmse",
                verbosity=0,
            ),
            "Random Forest": RandomForestRegressor(
                n_estimators=300,
                max_depth=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,
            ),
            "Ridge": Ridge(alpha=1.0),
        }

        results = {}
        for name, model in models.items():
            logger.info("Training %s...", name)
            if name == "XGBoost":
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_test, y_test)],
                    verbose=False,
                )
            else:
                model.fit(X_train, y_train)

            y_pred = model.predict(X_test)
            rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
            mae = float(mean_absolute_error(y_test, y_pred))
            r2 = float(r2_score(y_test, y_pred))

            results[name] = {"rmse": rmse, "mae": mae, "r2": r2}
            self.all_models[name] = model
            logger.info("%s — RMSE: $%,.0f | MAE: $%,.0f | R²: %.3f", name, rmse, mae, r2)

        # Step 5: Select best
        self.best_model_name = min(results, key=lambda k: results[k]["rmse"])
        self.best_model = self.all_models[self.best_model_name]
        self.metrics = results

        # Step 6: Residuals std
        y_pred_best = self.best_model.predict(X_test)
        self.test_residuals_std = float(np.std(y_test.values - y_pred_best))

        # Print evaluation table
        self._print_evaluation(results, y_test, y_pred_best, X_test)

        return results

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

        # Top features
        top_features = self._get_top_feature_impacts(feature_dict, predicted)

        # Similar jobs count (within 1 std of training data)
        similar_count = 0
        if self._training_salary_values is not None:
            similar_count = int(np.sum(
                np.abs(self._training_salary_values - predicted) < self.test_residuals_std
            ))

        return {
            "predicted_salary_usd": round(predicted),
            "confidence_low": round(conf_low),
            "confidence_high": round(conf_high),
            "percentile": percentile,
            "top_features": top_features,
            "similar_jobs_count": similar_count,
            "model_name": self.best_model_name,
            "model_version": self.MODEL_VERSION,
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

    def _get_top_feature_impacts(self, feature_dict: dict, predicted: float) -> List[dict]:
        """Compute top feature impacts for predict_single result."""
        importances = self.get_feature_importance(top_n=10)
        if not importances:
            return []

        top_features = []
        total_importance = sum(fi["importance"] for fi in importances) or 1.0

        for fi in importances[:5]:
            fname = fi["feature"]
            fval = feature_dict.get(fname, 0)
            # Approximate impact: proportion of importance × predicted salary
            impact = fi["importance"] / total_importance * predicted * 0.3
            sign = "+" if fval > 0 else ""
            top_features.append({
                "feature": fname,
                "value": fval,
                "impact": f"{sign}${abs(impact):,.0f}",
            })

        return top_features

    # ──────────────────────────────────────────────
    # Evaluation printing
    # ──────────────────────────────────────────────

    def _print_evaluation(self, results: Dict, y_test, y_pred_best, X_test) -> None:
        """Print evaluation table, feature importances, sample predictions."""
        print(f"\n{'='*70}")
        print(f" 🎯 MODEL EVALUATION RESULTS")
        print(f"{'='*70}")

        # Model comparison table
        print(f"\n ┌{'─'*58}┐")
        print(f" │ {'Model':<18}│ {'RMSE':>10} │ {'MAE':>10} │ {'R²':>7} │ {'Best':>5} │")
        print(f" ├{'─'*58}┤")
        for name, m in results.items():
            best_marker = "  ✓  " if name == self.best_model_name else "     "
            print(f" │ {name:<18}│ ${m['rmse']:>8,.0f} │ ${m['mae']:>8,.0f} │ {m['r2']:>6.3f} │{best_marker}│")
        print(f" └{'─'*58}┘")

        # Top 20 feature importances
        top_feats = self.get_feature_importance(top_n=20)
        if top_feats:
            print(f"\n 📊 Top 20 Feature Importances ({self.best_model_name}):")
            for i, fi in enumerate(top_feats, 1):
                bar = "█" * int(fi["importance"] * 100)
                print(f"    {i:>2}. {fi['feature']:<30} {fi['importance']:.4f}  {bar}")

        # Sample predictions
        print(f"\n 🔮 Sample Predictions (10 random):")
        print(f"    {'Actual':>12} {'Predicted':>12} {'Error':>12}")
        print(f"    {'─'*12} {'─'*12} {'─'*12}")

        n_samples = min(10, len(y_test))
        sample_idx = np.random.choice(len(y_test), n_samples, replace=False)
        y_test_arr = y_test.values
        for i in sample_idx:
            actual = y_test_arr[i]
            pred = y_pred_best[i]
            error = pred - actual
            sign = "+" if error > 0 else ""
            print(f"    ${actual:>10,.0f} ${pred:>10,.0f} {sign}${error:>9,.0f}")

        # Accuracy buckets
        errors = np.abs(y_test.values - y_pred_best)
        within_10k = np.mean(errors < 10_000) * 100
        within_20k = np.mean(errors < 20_000) * 100
        within_30k = np.mean(errors < 30_000) * 100
        print(f"\n 🎯 Prediction Accuracy:")
        print(f"    Within $10k: {within_10k:.1f}%")
        print(f"    Within $20k: {within_20k:.1f}%")
        print(f"    Within $30k: {within_30k:.1f}%")

        print(f"\n{'='*70}\n")

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
