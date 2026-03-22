"""
request.py — Pydantic request models for the JobLens API.

Defines validated input schemas for salary prediction and job search endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Request body for POST /api/v1/predict."""

    job_title: str = Field(..., description="Job title", min_length=2, examples=["Senior Data Scientist"])
    city: str = Field(..., description="City name", examples=["New York, NY, USA"])
    seniority_level: str = Field(..., description="Seniority level", examples=["Senior (5+ years)"])
    skills: List[str] = Field(default=[], description="List of skills", examples=[["Python", "SQL", "AWS"]])
    experience_years: Optional[float] = Field(default=None, ge=0, le=50, description="Years of experience")
    employment_type: str = Field(default="Full-time", description="Employment type")
    remote_type: str = Field(default="On-site", description="Remote work type")
    company_name: Optional[str] = Field(default=None, description="Company name")
    education_required: Optional[str] = Field(default=None, description="Education requirement")
    has_equity: bool = Field(default=False, description="Has equity compensation")
    has_bonus: bool = Field(default=False, description="Has bonus compensation")


class JobSearchRequest(BaseModel):
    """Query parameters for GET /api/v1/jobs (used as dependency)."""

    keyword: Optional[str] = Field(default=None, description="Keyword search in title/company")
    city: Optional[str] = Field(default=None, description="Filter by city")
    min_salary: Optional[int] = Field(default=None, ge=0, description="Minimum salary USD")
    max_salary: Optional[int] = Field(default=None, le=1_000_000, description="Maximum salary USD")
    remote_type: Optional[str] = Field(default=None, description="Filter: Remote, Hybrid, On-site")
    seniority_level: Optional[str] = Field(default=None, description="Filter by seniority level")
    skills: Optional[List[str]] = Field(default=None, description="Filter by skills (ANY match)")
    source: Optional[str] = Field(default=None, description="Filter by source website")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Results per page")
