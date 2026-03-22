"""
predict.py — Salary prediction route.

POST /api/v1/predict
  Accepts PredictRequest, returns PredictResponse.
  Calls predict_salary() from pipeline/predict.py.
"""

import logging
from fastapi import APIRouter, HTTPException

from api.schemas.request import PredictRequest
from api.schemas.response import PredictResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.post(
    "",
    response_model=PredictResponse,
    summary="Predict salary for a job",
    description="Takes job details and returns a predicted annual salary in USD "
                "with confidence interval, percentile, and top contributing features.",
)
async def predict_salary_endpoint(request: PredictRequest):
    """Predict salary for a given job specification."""
    try:
        from pipeline.predict import predict_salary

        input_dict = {
            "job_title": request.job_title,
            "city": request.city,
            "seniority_level": request.seniority_level,
            "skills": request.skills,
            "experience_years": request.experience_years,
            "employment_type": request.employment_type,
            "remote_type": request.remote_type,
            "company_name": request.company_name,
            "education_required": request.education_required,
            "has_equity": request.has_equity,
            "has_bonus": request.has_bonus,
        }

        result = predict_salary(input_dict)

        # Add model RMSE from metadata
        model_rmse = None
        try:
            from pipeline.predict import _predictor
            if _predictor and _predictor.metrics:
                best_name = _predictor.best_model_name
                model_rmse = _predictor.metrics.get(best_name, {}).get("rmse")
        except Exception:
            pass

        return PredictResponse(
            predicted_salary_usd=result["predicted_salary_usd"],
            confidence_low=result["confidence_low"],
            confidence_high=result["confidence_high"],
            percentile=result["percentile"],
            top_features=result.get("top_features", []),
            similar_jobs_count=result.get("similar_jobs_count", 0),
            model_name=result["model_name"],
            model_rmse=model_rmse,
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Run training first: python -m pipeline.train",
        )
    except Exception as e:
        logger.exception("Prediction error")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
