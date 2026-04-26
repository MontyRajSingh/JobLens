"""
jobs.py — Job listing routes.

GET /api/v1/jobs     — Paginated, filterable job search
GET /api/v1/jobs/{id} — Single job by database ID
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db.database import get_db
from api.schemas.response import JobRecord, JobSearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "",
    response_model=JobSearchResponse,
    summary="Search and filter jobs",
    description="Paginated job search with keyword, city, salary range, "
                "remote type, seniority, skills, and source filters.",
)
async def search_jobs(
    keyword: Optional[str] = Query(default=None, description="Search in title/company"),
    city: Optional[str] = Query(default=None),
    min_salary: Optional[int] = Query(default=None, ge=0),
    max_salary: Optional[int] = Query(default=None, le=1_000_000),
    remote_type: Optional[str] = Query(default=None),
    seniority_level: Optional[str] = Query(default=None),
    skills: Optional[str] = Query(default=None, description="Comma-separated skills (ANY match)"),
    source: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Search jobs with filters and pagination."""
    try:
        # Build WHERE clauses
        conditions = []
        params = {}

        if keyword:
            conditions.append(
                "(LOWER(job_title) LIKE :kw OR LOWER(company_name) LIKE :kw)"
            )
            params["kw"] = f"%{keyword.lower()}%"

        if city:
            conditions.append("LOWER(city) LIKE :city")
            params["city"] = f"%{city.lower()}%"

        if min_salary is not None:
            conditions.append("salary_usd_numeric >= :min_sal")
            params["min_sal"] = min_salary

        if max_salary is not None:
            conditions.append("salary_usd_numeric <= :max_sal")
            params["max_sal"] = max_salary

        if remote_type:
            conditions.append("LOWER(remote_type) = :remote")
            params["remote"] = remote_type.lower()

        if seniority_level:
            conditions.append("LOWER(seniority_level) LIKE :seniority")
            params["seniority"] = f"%{seniority_level.lower()}%"

        if source:
            conditions.append("LOWER(source_website) = :source")
            params["source"] = source.lower()

        if skills:
            skill_list = [s.strip().lower() for s in skills.split(",") if s.strip()]
            skill_conditions = []
            for i, skill in enumerate(skill_list):
                key = f"skill_{i}"
                skill_conditions.append(f"LOWER(skills_required) LIKE :{key}")
                params[key] = f"%{skill}%"
            if skill_conditions:
                conditions.append(f"({' OR '.join(skill_conditions)})")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Count total
        count_sql = f"SELECT COUNT(*) FROM jobs WHERE {where_clause}"
        result = db.execute(text(count_sql), params)
        total = result.scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        data_sql = (
            f"SELECT id, job_title, company_name, city, salary, salary_usd_numeric, "
            f"seniority_level, experience_required, remote_type, employment_type, "
            f"skills_required, source_website, job_link, has_equity, has_bonus, "
            f"company_tier_score, industry "
            f"FROM jobs WHERE {where_clause} "
            f"ORDER BY salary_usd_numeric DESC NULLS LAST "
            f"LIMIT :limit OFFSET :offset"
        )
        params["limit"] = page_size
        params["offset"] = offset

        rows = db.execute(text(data_sql), params).fetchall()

        results = []
        for row in rows:
            results.append(JobRecord(
                id=row[0],
                job_title=row[1],
                company_name=row[2],
                city=row[3],
                salary=row[4],
                salary_usd_numeric=row[5],
                seniority_level=row[6],
                experience_required=row[7],
                remote_type=row[8],
                employment_type=row[9],
                skills_required=row[10],
                source_website=row[11],
                job_link=row[12],
                has_equity=bool(row[13]) if row[13] is not None else None,
                has_bonus=bool(row[14]) if row[14] is not None else None,
                company_tier_score=row[15],
                industry=row[16],
            ))

        return JobSearchResponse(
            total=total,
            page=page,
            page_size=page_size,
            results=results,
        )

    except Exception as e:
        logger.exception("Job search error")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get(
    "/{job_id}",
    response_model=JobRecord,
    summary="Get single job by ID",
)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a single job record by database ID."""
    try:
        sql = (
            "SELECT id, job_title, company_name, city, salary, salary_usd_numeric, "
            "seniority_level, experience_required, remote_type, employment_type, "
            "skills_required, source_website, job_link, has_equity, has_bonus, "
            "company_tier_score, industry "
            "FROM jobs WHERE id = :job_id"
        )
        row = db.execute(text(sql), {"job_id": job_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobRecord(
            id=row[0],
            job_title=row[1],
            company_name=row[2],
            city=row[3],
            salary=row[4],
            salary_usd_numeric=row[5],
            seniority_level=row[6],
            experience_required=row[7],
            remote_type=row[8],
            employment_type=row[9],
            skills_required=row[10],
            source_website=row[11],
            job_link=row[12],
            has_equity=bool(row[13]) if row[13] is not None else None,
            has_bonus=bool(row[14]) if row[14] is not None else None,
            company_tier_score=row[15],
            industry=row[16],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Get job error")
        raise HTTPException(status_code=500, detail=f"Failed to get job: {str(e)}")
