"""
predict.py — Salary prediction route.

POST /api/v1/predict
  Accepts PredictRequest, returns PredictResponse.
  Calls predict_salary() from pipeline/predict.py.
"""

import json
import logging
import requests
from io import BytesIO
import PyPDF2
from fastapi import APIRouter, HTTPException, UploadFile, File

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

@router.post(
    "/resume",
    summary="Predict salary from Resume",
    description="Upload a resume PDF to extract fields via OpenRouter (Nemotron) and run prediction.",
)
async def predict_from_resume(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Extract text from PDF
    try:
        content = await file.read()
        pdf_reader = PyPDF2.PdfReader(BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {str(e)}")

    # Call OpenRouter API
    api_key = "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"
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    prompt = f"""
    You are an AI resume parser. Extract the following details from the resume text provided below.
    Return ONLY a valid JSON object (no markdown formatting, no commentary) with the following schema:
    {{
        "job_title": "Current or target job title (string)",
        "experience_years": "Total years of experience (number)",
        "skills": ["List of top technical skills", ...],
        "education_required": "Highest education degree (e.g. Bachelor's, Master's, PhD, or empty string)",
        "company_name": "Current or most recent company name (string)"
    }}
    
    Resume Text:
    {text}
    """
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "messages": [{"role": "user", "content": prompt}],
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result_text = response.json()["choices"][0]["message"]["content"].strip()
        
        # Clean up markdown code blocks if any
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        extracted_data = json.loads(result_text)
    except Exception as e:
        logger.exception("Failed to parse resume with OpenRouter")
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")
        
    # Set default fields for prediction
    extracted_data["city"] = "New York, NY, USA"
    extracted_data["seniority_level"] = "Mid-Level (2-5 years)" 
    if extracted_data.get("experience_years", 0) > 5:
        extracted_data["seniority_level"] = "Senior (5+ years)"
    extracted_data["employment_type"] = "Full-time"
    extracted_data["remote_type"] = "On-site"
    extracted_data["has_equity"] = False
    extracted_data["has_bonus"] = False

    # Return extracted data so frontend can populate form and then trigger prediction
    return {"extracted_data": extracted_data}

