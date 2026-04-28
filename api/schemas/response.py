"""
response.py — Pydantic response models for the JobLens API.

Defines validated output schemas for predictions, job records, search results,
and insight endpoints.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PredictResponse(BaseModel):
    """Response body for POST /api/v1/predict."""

    predicted_salary_usd: int = Field(..., description="Predicted annual salary in USD")
    model_prediction_usd: Optional[int] = Field(
        default=None,
        description="Raw model prediction before heuristic business adjustments",
    )
    adjusted_prediction_usd: Optional[int] = Field(
        default=None,
        description="Final prediction after transparent heuristic adjustments",
    )
    base_prediction_usd: Optional[int] = Field(
        default=None,
        description="Model prediction with skills removed, used for skill premium comparison",
    )
    confidence_low: int = Field(..., description="Lower bound of confidence interval")
    confidence_high: int = Field(..., description="Upper bound of confidence interval")
    confidence_method: Optional[str] = Field(default=None, description="How the confidence interval was calculated")
    percentile: int = Field(..., description="Salary percentile within training data")
    top_features: List[Dict[str, Any]] = Field(default=[], description="Top contributing features")
    adjustments: Dict[str, Any] = Field(default={}, description="Transparent non-model salary adjustments")
    skill_bonuses: List[Dict[str, Any]] = Field(default=[], description="Individual skill premiums (+$X)")
    total_skill_premium: int = Field(default=0, description="Total salary lift from skills")
    company_tier: Optional[Dict[str, Any]] = Field(default=None, description="Company prestige tier information")
    academic_bonus: Optional[Dict[str, Any]] = Field(default=None, description="Academic degree bonus information")
    similar_jobs_count: int = Field(default=0, description="Count of similar salary jobs in training data")
    similar_jobs: List[Dict[str, Any]] = Field(default=[], description="Similar market jobs behind the prediction")
    model_name: str = Field(..., description="Name of the model used")
    model_version: Optional[str] = Field(default=None, description="Model artifact version")
    model_rmse: Optional[float] = Field(default=None, description="Model RMSE on test set")


class OfferAnalyzeResponse(BaseModel):
    """Response body for POST /api/v1/predict/offer."""

    total_comp_usd: int
    market_reference_usd: int
    difference_usd: int
    difference_pct: float
    verdict: str
    recommendation: str
    evidence_count: int
    predicted_salary_usd: Optional[int] = None


class JobRecord(BaseModel):
    """Single job record for API responses."""

    id: Optional[int] = Field(default=None, description="Database row ID")
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    city: Optional[str] = None
    salary: Optional[str] = None
    salary_usd_numeric: Optional[float] = None
    seniority_level: Optional[str] = None
    experience_required: Optional[str] = None
    remote_type: Optional[str] = None
    employment_type: Optional[str] = None
    skills_required: Optional[str] = None
    source_website: Optional[str] = None
    job_link: Optional[str] = None
    has_equity: Optional[bool] = None
    has_bonus: Optional[bool] = None
    is_faang: Optional[int] = None
    industry: Optional[str] = None


class CompanyProfileResponse(BaseModel):
    """Company compensation profile."""

    company_name: str
    job_count: int
    salary_count: int
    avg_salary: Optional[float] = None
    median_salary: Optional[float] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    equity_frequency_pct: float = 0.0
    bonus_frequency_pct: float = 0.0
    remote_frequency_pct: float = 0.0
    top_roles: List[Dict[str, Any]] = []
    top_cities: List[Dict[str, Any]] = []
    recent_jobs: List[JobRecord] = []


class JobSearchResponse(BaseModel):
    """Response body for GET /api/v1/jobs."""

    total: int = Field(..., description="Total matching results")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Results per page")
    results: List[JobRecord] = Field(default=[], description="Job records")


class SalaryByCityItem(BaseModel):
    """Single city salary insight."""
    city: str
    avg_salary: float
    median_salary: float
    job_count: int
    salary_range: Dict[str, float]


class TopSkillItem(BaseModel):
    """Single skill insight."""
    skill: str
    count: int
    avg_salary_with_skill: Optional[float] = None
    avg_salary_without_skill: Optional[float] = None
    salary_premium_pct: Optional[float] = None


class SalaryBySeniorityItem(BaseModel):
    """Single seniority-level salary insight."""
    seniority_level: str
    avg_salary: float
    median_salary: float
    count: int
    seniority_score: int


class RemoteVsOnsiteResponse(BaseModel):
    """Remote vs on-site salary comparison."""
    remote_avg: Optional[float] = None
    hybrid_avg: Optional[float] = None
    onsite_avg: Optional[float] = None
    remote_premium_pct: Optional[float] = None
    hybrid_premium_pct: Optional[float] = None
    remote_count: int = 0
    hybrid_count: int = 0
    onsite_count: int = 0


class MarketSummaryResponse(BaseModel):
    """Overall market summary."""
    total_jobs: int
    cities_count: int
    sources_count: int
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_avg: Optional[float] = None
    salary_median: Optional[float] = None
    top_companies: List[Dict[str, Any]] = []
    top_skills: List[Dict[str, Any]] = []
    jobs_with_salary_pct: float = 0.0
    last_scraped: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    jobs_count: int
    model_rmse: Optional[float] = None
    model_version: Optional[str] = None
    last_trained: Optional[str] = None
