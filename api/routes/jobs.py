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
from api.schemas.response import CompanyProfileResponse, JobRecord, JobSearchResponse

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

        # Sorting (Default: Newest First)
        order_by = "scraped_at DESC NULLS LAST"
        
        # If searching for salary specifically, or if user requests it (future), 
        # we could change this, but for now: Newest First.
        
        # Fetch page
        offset = (page - 1) * page_size
        data_sql = (
            f"SELECT id, job_title, company_name, city, salary, salary_usd_numeric, "
            f"seniority_level, experience_required, remote_type, employment_type, "
            f"skills_required, source_website, job_link, has_equity, has_bonus, "
            f"is_faang, industry FROM jobs "
            f"WHERE {where_clause} "
            f"ORDER BY {order_by} "
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
                is_faang=row[15],
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
    "/company/{company_name}",
    response_model=CompanyProfileResponse,
    summary="Get company compensation profile",
)
async def get_company_profile(company_name: str, db: Session = Depends(get_db)):
    """Get aggregate compensation stats for a company."""
    try:
        params = {"company": f"%{company_name.lower()}%"}
        stats_sql = """
            SELECT company_name,
                   COUNT(*) as job_count,
                   COUNT(salary_usd_numeric) as salary_count,
                   AVG(salary_usd_numeric) as avg_salary,
                   MIN(salary_usd_numeric) as min_salary,
                   MAX(salary_usd_numeric) as max_salary,
                   AVG(CASE WHEN has_equity > 0 THEN 1.0 ELSE 0.0 END) as equity_freq,
                   AVG(CASE WHEN has_bonus > 0 THEN 1.0 ELSE 0.0 END) as bonus_freq,
                   AVG(CASE WHEN LOWER(remote_type) LIKE '%remote%' THEN 1.0 ELSE 0.0 END) as remote_freq
            FROM jobs
            WHERE LOWER(company_name) LIKE :company
            GROUP BY company_name
            ORDER BY job_count DESC
            LIMIT 1
        """
        row = db.execute(text(stats_sql), params).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Company '{company_name}' not found")

        canonical = row[0]
        exact_params = {"company": canonical}

        salaries = [
            r[0] for r in db.execute(text("""
                SELECT salary_usd_numeric FROM jobs
                WHERE company_name = :company AND salary_usd_numeric IS NOT NULL
                ORDER BY salary_usd_numeric
            """), exact_params).fetchall()
        ]
        median = float(salaries[len(salaries) // 2]) if salaries else None

        top_roles = [
            {"role": r[0], "count": int(r[1]), "avg_salary": round(float(r[2]), 2) if r[2] else None}
            for r in db.execute(text("""
                SELECT job_title, COUNT(*) as cnt, AVG(salary_usd_numeric) as avg_sal
                FROM jobs WHERE company_name = :company
                GROUP BY job_title ORDER BY cnt DESC LIMIT 5
            """), exact_params).fetchall()
        ]

        top_cities = [
            {"city": r[0], "count": int(r[1]), "avg_salary": round(float(r[2]), 2) if r[2] else None}
            for r in db.execute(text("""
                SELECT city, COUNT(*) as cnt, AVG(salary_usd_numeric) as avg_sal
                FROM jobs WHERE company_name = :company
                GROUP BY city ORDER BY cnt DESC LIMIT 5
            """), exact_params).fetchall()
        ]

        recent_rows = db.execute(text("""
            SELECT id, job_title, company_name, city, salary, salary_usd_numeric,
                   seniority_level, experience_required, remote_type, employment_type,
                   skills_required, source_website, job_link, has_equity, has_bonus,
                   is_faang, industry
            FROM jobs WHERE company_name = :company
            ORDER BY scraped_at DESC NULLS LAST LIMIT 6
        """), exact_params).fetchall()

        recent_jobs = [
            JobRecord(
                id=r[0], job_title=r[1], company_name=r[2], city=r[3], salary=r[4],
                salary_usd_numeric=r[5], seniority_level=r[6], experience_required=r[7],
                remote_type=r[8], employment_type=r[9], skills_required=r[10],
                source_website=r[11], job_link=r[12],
                has_equity=bool(r[13]) if r[13] is not None else None,
                has_bonus=bool(r[14]) if r[14] is not None else None,
                is_faang=r[15], industry=r[16],
            )
            for r in recent_rows
        ]

        return CompanyProfileResponse(
            company_name=canonical,
            job_count=int(row[1]),
            salary_count=int(row[2]),
            avg_salary=round(float(row[3]), 2) if row[3] else None,
            median_salary=round(median, 2) if median else None,
            salary_min=round(float(row[4]), 2) if row[4] else None,
            salary_max=round(float(row[5]), 2) if row[5] else None,
            equity_frequency_pct=round(float(row[6] or 0) * 100, 1),
            bonus_frequency_pct=round(float(row[7] or 0) * 100, 1),
            remote_frequency_pct=round(float(row[8] or 0) * 100, 1),
            top_roles=top_roles,
            top_cities=top_cities,
            recent_jobs=recent_jobs,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Company profile error")
        raise HTTPException(status_code=500, detail=f"Failed to get company profile: {str(e)}")


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
            "is_faang, industry "
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
            is_faang=row[15],
            industry=row[16],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Get job error")
        raise HTTPException(status_code=500, detail=f"Failed to get job: {str(e)}")
