"""
predict.py — Salary prediction route.

POST /api/v1/predict
  Accepts PredictRequest, returns PredictResponse.
  Calls predict_salary() from pipeline/predict.py.
"""

import os
import json
import logging
import requests
import re
from io import BytesIO
import PyPDF2
from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlalchemy import text as sql_text

from api.db.database import SessionLocal
from api.schemas.request import OfferAnalyzeRequest, PredictRequest
from api.schemas.response import OfferAnalyzeResponse, PredictResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["Prediction"])


def _coerce_experience_years(value) -> float:
    """Return parsed years of experience, defaulting to 0 when absent."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))

    text = str(value).strip().lower()
    if not text or text in {"none", "null", "n/a", "na", "not mentioned", "unknown"}:
        return 0.0

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        return (float(range_match.group(1)) + float(range_match.group(2))) / 2

    number_match = re.search(r"(\d+(?:\.\d+)?)", text)
    if number_match:
        return max(0.0, float(number_match.group(1)))

    return 0.0


def _seniority_from_experience(years: float) -> str:
    """Map experience years to the seniority labels expected by the model."""
    if years <= 0:
        return "Entry Level (0-2 years)"
    if years < 3:
        return "Associate (1-3 years)"
    if years < 5:
        return "Mid-Level (2-5 years)"
    if years < 8:
        return "Senior (5+ years)"
    return "Staff (8+ years)"


def _infer_job_title_from_resume(text: str, skills: list | None = None) -> str:
    """Infer a usable target job title when the LLM leaves job_title blank."""
    text_lower = (text or "").lower()
    title_patterns = [
        ("Machine Learning Engineer", r"\b(machine learning engineer|ml engineer|ai engineer)\b"),
        ("Data Scientist", r"\b(data scientist|data science)\b"),
        ("Data Analyst", r"\b(data analyst|business analyst|analytics analyst)\b"),
        ("Data Engineer", r"\b(data engineer|etl engineer|analytics engineer)\b"),
        ("Full Stack Developer", r"\b(full stack|full-stack)\b"),
        ("Frontend Engineer", r"\b(frontend|front-end|react developer|ui developer)\b"),
        ("Backend Engineer", r"\b(backend|back-end|api developer)\b"),
        ("DevOps Engineer", r"\b(devops|site reliability|sre|cloud engineer)\b"),
        ("Software Engineer", r"\b(software engineer|software developer|developer|programmer)\b"),
        ("Product Manager", r"\b(product manager|product owner)\b"),
        ("UI/UX Designer", r"\b(ui/ux|ux designer|ui designer|product designer)\b"),
    ]
    for title, pattern in title_patterns:
        if re.search(pattern, text_lower):
            return title

    skill_set = {str(skill).lower() for skill in (skills or [])}
    for skill_keyword in [
        "machine learning", "pytorch", "tensorflow", "scikit-learn", "nlp",
        "python", "sql", "tableau", "power bi", "excel",
        "react", "javascript", "typescript", "node.js",
        "aws", "docker", "kubernetes", "terraform",
    ]:
        if skill_keyword in text_lower:
            skill_set.add(skill_keyword)
    if {"machine learning", "pytorch", "tensorflow", "scikit-learn", "nlp"} & skill_set:
        return "Machine Learning Engineer"
    if {"python", "sql", "tableau", "power bi", "excel"} & skill_set:
        return "Data Analyst"
    if {"react", "javascript", "typescript", "node.js"} & skill_set:
        return "Full Stack Developer"
    if {"aws", "docker", "kubernetes", "terraform"} & skill_set:
        return "DevOps Engineer"

    return "Software Engineer"


def _compact_job(row) -> dict:
    """Convert a DB row to the compact job shape used in prediction evidence."""
    return {
        "id": row[0],
        "job_title": row[1],
        "company_name": row[2],
        "city": row[3],
        "salary_usd_numeric": row[4],
        "seniority_level": row[5],
        "remote_type": row[6],
        "source_website": row[7],
    }


def _find_similar_jobs(job_title: str, city: str, seniority: str | None = None, limit: int = 5) -> list[dict]:
    """Find salary-bearing jobs similar enough to explain a prediction."""
    title_terms = [t for t in re.split(r"\W+", (job_title or "").lower()) if len(t) >= 4]
    keyword = title_terms[0] if title_terms else (job_title or "").lower()
    city_key = (city or "").split(",")[0].strip().lower()

    conditions = ["salary_usd_numeric IS NOT NULL"]
    params = {"limit": limit}
    if keyword:
        conditions.append("LOWER(job_title) LIKE :keyword")
        params["keyword"] = f"%{keyword}%"
    if city_key:
        conditions.append("LOWER(city) LIKE :city")
        params["city"] = f"%{city_key}%"
    if seniority:
        conditions.append("LOWER(seniority_level) LIKE :seniority")
        params["seniority"] = f"%{seniority.split('(')[0].strip().lower()}%"

    query = f"""
        SELECT id, job_title, company_name, city, salary_usd_numeric,
               seniority_level, remote_type, source_website
        FROM jobs
        WHERE {' AND '.join(conditions)}
        ORDER BY salary_usd_numeric DESC
        LIMIT :limit
    """
    with SessionLocal() as db:
        rows = db.execute(sql_text(query), params).fetchall()

        if not rows and keyword:
            rows = db.execute(sql_text("""
                SELECT id, job_title, company_name, city, salary_usd_numeric,
                       seniority_level, remote_type, source_website
                FROM jobs
                WHERE salary_usd_numeric IS NOT NULL AND LOWER(job_title) LIKE :keyword
                ORDER BY salary_usd_numeric DESC
                LIMIT :limit
            """), {"keyword": f"%{keyword}%", "limit": limit}).fetchall()

    return [_compact_job(row) for row in rows]


def _market_reference_salary(job_title: str, city: str, seniority: str | None = None) -> tuple[int | None, int]:
    """Return median salary and evidence count for comparable jobs."""
    similar_jobs = _find_similar_jobs(job_title, city, seniority, limit=50)
    salaries = sorted(
        float(job["salary_usd_numeric"])
        for job in similar_jobs
        if job.get("salary_usd_numeric") is not None
    )
    if not salaries:
        return None, 0
    return int(salaries[len(salaries) // 2]), len(salaries)


def _resume_gap_analysis(extracted_data: dict) -> dict:
    """Suggest missing high-value skills from saved premium data."""
    model_dir = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "pipeline", "models"))
    premium_path = os.path.join(model_dir, "skill_premiums.json")
    try:
        with open(premium_path, "r") as f:
            premiums = json.load(f)
    except Exception:
        premiums = {}

    detected = {str(skill).lower() for skill in extracted_data.get("skills", []) if skill}
    missing = []
    for skill, premium in sorted(premiums.items(), key=lambda item: item[1], reverse=True):
        if str(skill).lower() not in detected:
            missing.append({"skill": skill, "estimated_lift_usd": int(premium)})
        if len(missing) == 5:
            break

    return {
        "detected_skills": extracted_data.get("skills", []),
        "missing_high_value_skills": missing,
        "estimated_top3_lift_usd": sum(item["estimated_lift_usd"] for item in missing[:3]),
    }


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
        similar_jobs = _find_similar_jobs(
            request.job_title,
            request.city,
            request.seniority_level,
        )

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
            model_prediction_usd=result.get("model_prediction_usd"),
            adjusted_prediction_usd=result.get("adjusted_prediction_usd"),
            base_prediction_usd=result.get("base_prediction_usd"),
            confidence_low=result["confidence_low"],
            confidence_high=result["confidence_high"],
            confidence_method=result.get("confidence_method"),
            percentile=result["percentile"],
            top_features=result.get("top_features", []),
            adjustments=result.get("adjustments", {}),
            skill_bonuses=result.get("skill_bonuses", []),
            total_skill_premium=result.get("total_skill_premium", 0),
            company_tier=result.get("company_tier"),
            academic_bonus=result.get("academic_bonus"),
            similar_jobs_count=len(similar_jobs),
            similar_jobs=similar_jobs,
            model_name=result["model_name"],
            model_version=result.get("model_version"),
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
    "/offer",
    response_model=OfferAnalyzeResponse,
    summary="Analyze a compensation offer against market data",
)
async def analyze_offer(request: OfferAnalyzeRequest):
    """Compare an offer's total annual compensation to market evidence."""
    try:
        from pipeline.predict import predict_salary

        total_comp = request.base_salary_usd + request.annual_bonus_usd + request.annual_equity_usd
        market_salary, evidence_count = _market_reference_salary(
            request.job_title,
            request.city,
            request.seniority_level,
        )

        prediction = predict_salary({
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
        })
        predicted_salary = int(prediction["predicted_salary_usd"])
        reference = market_salary or predicted_salary

        difference = total_comp - reference
        difference_pct = round((difference / reference * 100), 1) if reference else 0.0
        if difference_pct >= 10:
            verdict = "strong"
            recommendation = "The offer is meaningfully above the current market reference."
        elif difference_pct >= -5:
            verdict = "fair"
            recommendation = "The offer is close to market. Negotiate on role scope, bonus, or equity if needed."
        else:
            verdict = "low"
            recommendation = "The offer is below market. Ask for a higher base or clearer bonus/equity upside."

        return OfferAnalyzeResponse(
            total_comp_usd=total_comp,
            market_reference_usd=reference,
            difference_usd=int(difference),
            difference_pct=difference_pct,
            verdict=verdict,
            recommendation=recommendation,
            evidence_count=evidence_count,
            predicted_salary_usd=predicted_salary,
        )
    except Exception as e:
        logger.exception("Offer analysis error")
        raise HTTPException(status_code=500, detail=f"Offer analysis failed: {str(e)}")

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
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set")
        raise HTTPException(status_code=500, detail="Resume parsing service misconfigured")
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    prompt = f"""
    You are an AI resume parser. Extract the following details from the resume text provided below.
    If total years of experience is explicitly mentioned, return it as a number.
    If total years of experience is not mentioned, return 0.
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
        response = requests.post(url, headers=headers, json=payload, timeout=120)
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
        
    # Normalize defaults for prediction. City is intentionally left to the
    # frontend so the user-selected city is preserved.
    experience_years = _coerce_experience_years(extracted_data.get("experience_years"))
    extracted_data["experience_years"] = experience_years
    extracted_data["seniority_level"] = _seniority_from_experience(experience_years)
    if not str(extracted_data.get("job_title") or "").strip():
        extracted_data["job_title"] = _infer_job_title_from_resume(
            text,
            extracted_data.get("skills") if isinstance(extracted_data.get("skills"), list) else [],
        )
    extracted_data["employment_type"] = "Full-time"
    extracted_data["remote_type"] = "On-site"
    extracted_data["has_equity"] = False
    extracted_data["has_bonus"] = False

    return {
        "extracted_data": extracted_data,
        "gap_analysis": _resume_gap_analysis(extracted_data),
    }
