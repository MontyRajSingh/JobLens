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
    confidence_low: int = Field(..., description="Lower bound of confidence interval")
    confidence_high: int = Field(..., description="Upper bound of confidence interval")
    percentile: int = Field(..., description="Salary percentile within training data")
    top_features: List[Dict[str, Any]] = Field(default=[], description="Top contributing features")
    similar_jobs_count: int = Field(default=0, description="Count of similar salary jobs in training data")
    model_name: str = Field(..., description="Name of the model used")
    model_rmse: Optional[float] = Field(default=None, description="Model RMSE on test set")


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
