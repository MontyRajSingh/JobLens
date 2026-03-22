"""
insights.py — Market insight routes.

GET /api/v1/insights/salary-by-city
GET /api/v1/insights/top-skills
GET /api/v1/insights/salary-by-seniority
GET /api/v1/insights/remote-vs-onsite
GET /api/v1/insights/market-summary
"""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db.database import get_db
from api.schemas.response import (
    SalaryByCityItem,
    TopSkillItem,
    SalaryBySeniorityItem,
    RemoteVsOnsiteResponse,
    MarketSummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["Insights"])

# Seniority score mapping for ordering
SENIORITY_SCORES = {
    "internship (0 years)": 0,
    "entry level (0-2 years)": 1,
    "associate (1-3 years)": 2,
    "mid-level (2-5 years)": 3,
    "senior (4-7 years)": 4,
    "senior (5+ years)": 4,
    "staff (8+ years)": 5,
    "director (8+ years)": 6,
    "executive (10+ years)": 6,
}


@router.get(
    "/salary-by-city",
    response_model=List[SalaryByCityItem],
    summary="Average salary by city",
)
async def salary_by_city(
    keyword: Optional[str] = Query(default=None, description="Filter by keyword in title"),
    db: Session = Depends(get_db),
):
    """Get average and median salary broken down by city."""
    try:
        where = "salary_usd_numeric IS NOT NULL"
        params = {}

        if keyword:
            where += " AND LOWER(job_title) LIKE :kw"
            params["kw"] = f"%{keyword.lower()}%"

        sql = f"""
            SELECT city,
                   AVG(salary_usd_numeric) as avg_sal,
                   MIN(salary_usd_numeric) as min_sal,
                   MAX(salary_usd_numeric) as max_sal,
                   COUNT(*) as cnt
            FROM jobs
            WHERE {where}
            GROUP BY city
            ORDER BY avg_sal DESC
        """
        rows = db.execute(text(sql), params).fetchall()

        results = []
        # For median, we need per-city salary lists
        for row in rows:
            city_name = row[0]
            avg_sal = float(row[1]) if row[1] else 0
            min_sal = float(row[2]) if row[2] else 0
            max_sal = float(row[3]) if row[3] else 0
            count = int(row[4])

            # Get median
            median_sql = f"""
                SELECT salary_usd_numeric FROM jobs
                WHERE city = :city AND salary_usd_numeric IS NOT NULL
                {"AND LOWER(job_title) LIKE :kw" if keyword else ""}
                ORDER BY salary_usd_numeric
            """
            median_params = {"city": city_name}
            if keyword:
                median_params["kw"] = f"%{keyword.lower()}%"

            salaries = [r[0] for r in db.execute(text(median_sql), median_params).fetchall()]
            median_sal = salaries[len(salaries) // 2] if salaries else avg_sal

            results.append(SalaryByCityItem(
                city=city_name,
                avg_salary=round(avg_sal, 2),
                median_salary=round(float(median_sal), 2),
                job_count=count,
                salary_range={"min": round(min_sal, 2), "max": round(max_sal, 2)},
            ))

        return results

    except Exception as e:
        logger.exception("Salary by city error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/top-skills",
    response_model=List[TopSkillItem],
    summary="Top skills with salary premium",
)
async def top_skills(
    city: Optional[str] = Query(default=None),
    seniority: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get top skills ranked by salary premium percentage."""
    try:
        # Build filter
        where_parts = ["skills_required IS NOT NULL"]
        params = {}
        if city:
            where_parts.append("LOWER(city) LIKE :city")
            params["city"] = f"%{city.lower()}%"
        if seniority:
            where_parts.append("LOWER(seniority_level) LIKE :seniority")
            params["seniority"] = f"%{seniority.lower()}%"

        where = " AND ".join(where_parts)

        # Get all jobs with skills
        sql = f"SELECT skills_required, salary_usd_numeric FROM jobs WHERE {where}"
        rows = db.execute(text(sql), params).fetchall()

        # Count skills and compute salary averages
        skill_stats: Dict[str, Dict[str, Any]] = {}
        all_salaries = []

        for row in rows:
            skills_text = row[0] or ""
            salary = row[1]

            if salary is not None:
                all_salaries.append(float(salary))

            for skill in skills_text.split(","):
                skill = skill.strip()
                if not skill:
                    continue
                if skill not in skill_stats:
                    skill_stats[skill] = {"count": 0, "salaries": []}
                skill_stats[skill]["count"] += 1
                if salary is not None:
                    skill_stats[skill]["salaries"].append(float(salary))

        overall_avg = sum(all_salaries) / len(all_salaries) if all_salaries else 0

        results = []
        for skill, stats in skill_stats.items():
            avg_with = sum(stats["salaries"]) / len(stats["salaries"]) if stats["salaries"] else None
            avg_without = overall_avg  # Simplified: overall average as proxy

            premium_pct = None
            if avg_with and avg_without and avg_without > 0:
                premium_pct = round((avg_with - avg_without) / avg_without * 100, 2)

            results.append(TopSkillItem(
                skill=skill,
                count=stats["count"],
                avg_salary_with_skill=round(avg_with, 2) if avg_with else None,
                avg_salary_without_skill=round(avg_without, 2) if avg_without else None,
                salary_premium_pct=premium_pct,
            ))

        # Sort by premium descending
        results.sort(key=lambda x: x.salary_premium_pct or 0, reverse=True)
        return results[:30]

    except Exception as e:
        logger.exception("Top skills error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/salary-by-seniority",
    response_model=List[SalaryBySeniorityItem],
    summary="Salary distribution by seniority level",
)
async def salary_by_seniority(db: Session = Depends(get_db)):
    """Get salary stats broken down by seniority level."""
    try:
        sql = """
            SELECT seniority_level,
                   AVG(salary_usd_numeric) as avg_sal,
                   COUNT(*) as cnt
            FROM jobs
            WHERE salary_usd_numeric IS NOT NULL AND seniority_level IS NOT NULL
            GROUP BY seniority_level
        """
        rows = db.execute(text(sql)).fetchall()

        results = []
        for row in rows:
            level = row[0]
            avg_sal = float(row[1]) if row[1] else 0
            count = int(row[2])

            # Get median
            median_sql = """
                SELECT salary_usd_numeric FROM jobs
                WHERE seniority_level = :level AND salary_usd_numeric IS NOT NULL
                ORDER BY salary_usd_numeric
            """
            salaries = [r[0] for r in db.execute(text(median_sql), {"level": level}).fetchall()]
            median_sal = salaries[len(salaries) // 2] if salaries else avg_sal

            score = SENIORITY_SCORES.get(level.lower() if level else "", 3)

            results.append(SalaryBySeniorityItem(
                seniority_level=level,
                avg_salary=round(avg_sal, 2),
                median_salary=round(float(median_sal), 2),
                count=count,
                seniority_score=score,
            ))

        results.sort(key=lambda x: x.seniority_score)
        return results

    except Exception as e:
        logger.exception("Salary by seniority error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/remote-vs-onsite",
    response_model=RemoteVsOnsiteResponse,
    summary="Remote vs on-site salary comparison",
)
async def remote_vs_onsite(db: Session = Depends(get_db)):
    """Compare average salaries for remote, hybrid, and on-site jobs."""
    try:
        sql = """
            SELECT remote_type,
                   AVG(salary_usd_numeric) as avg_sal,
                   COUNT(*) as cnt
            FROM jobs
            WHERE salary_usd_numeric IS NOT NULL AND remote_type IS NOT NULL
            GROUP BY remote_type
        """
        rows = db.execute(text(sql)).fetchall()

        data = {}
        for row in rows:
            rt = (row[0] or "").lower()
            data[rt] = {"avg": float(row[1]) if row[1] else 0, "count": int(row[2])}

        onsite_avg = data.get("on-site", {}).get("avg", 0)
        remote_avg = data.get("remote", {}).get("avg")
        hybrid_avg = data.get("hybrid", {}).get("avg")

        remote_premium = None
        hybrid_premium = None
        if onsite_avg > 0:
            if remote_avg:
                remote_premium = round((remote_avg - onsite_avg) / onsite_avg * 100, 2)
            if hybrid_avg:
                hybrid_premium = round((hybrid_avg - onsite_avg) / onsite_avg * 100, 2)

        return RemoteVsOnsiteResponse(
            remote_avg=round(remote_avg, 2) if remote_avg else None,
            hybrid_avg=round(hybrid_avg, 2) if hybrid_avg else None,
            onsite_avg=round(onsite_avg, 2) if onsite_avg else None,
            remote_premium_pct=remote_premium,
            hybrid_premium_pct=hybrid_premium,
            remote_count=data.get("remote", {}).get("count", 0),
            hybrid_count=data.get("hybrid", {}).get("count", 0),
            onsite_count=data.get("on-site", {}).get("count", 0),
        )

    except Exception as e:
        logger.exception("Remote vs onsite error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/market-summary",
    response_model=MarketSummaryResponse,
    summary="Overall market summary",
)
async def market_summary(db: Session = Depends(get_db)):
    """Get high-level market statistics."""
    try:
        # Basic stats
        stats_sql = """
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT city) as cities,
                   COUNT(DISTINCT source_website) as sources,
                   MIN(salary_usd_numeric) as sal_min,
                   MAX(salary_usd_numeric) as sal_max,
                   AVG(salary_usd_numeric) as sal_avg
            FROM jobs
        """
        row = db.execute(text(stats_sql)).fetchone()
        total = int(row[0]) if row[0] else 0
        cities = int(row[1]) if row[1] else 0
        sources = int(row[2]) if row[2] else 0
        sal_min = float(row[3]) if row[3] else None
        sal_max = float(row[4]) if row[4] else None
        sal_avg = float(row[5]) if row[5] else None

        # Median salary
        sal_median = None
        median_sql = """
            SELECT salary_usd_numeric FROM jobs
            WHERE salary_usd_numeric IS NOT NULL
            ORDER BY salary_usd_numeric
        """
        salaries = [r[0] for r in db.execute(text(median_sql)).fetchall()]
        if salaries:
            sal_median = float(salaries[len(salaries) // 2])

        # Salary fill rate
        sal_count_sql = "SELECT COUNT(*) FROM jobs WHERE salary_usd_numeric IS NOT NULL"
        sal_count = db.execute(text(sal_count_sql)).scalar() or 0
        sal_pct = round(sal_count / total * 100, 1) if total > 0 else 0

        # Top 10 companies
        company_sql = """
            SELECT company_name, COUNT(*) as cnt
            FROM jobs WHERE company_name IS NOT NULL
            GROUP BY company_name ORDER BY cnt DESC LIMIT 10
        """
        top_companies = [
            {"company": r[0], "count": int(r[1])}
            for r in db.execute(text(company_sql)).fetchall()
        ]

        # Top 10 skills
        skills_sql = "SELECT skills_required FROM jobs WHERE skills_required IS NOT NULL"
        skill_counts: Dict[str, int] = {}
        for r in db.execute(text(skills_sql)).fetchall():
            for s in (r[0] or "").split(","):
                s = s.strip()
                if s:
                    skill_counts[s] = skill_counts.get(s, 0) + 1
        top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_skills_list = [{"skill": s, "count": c} for s, c in top_skills]

        # Last scraped
        last_sql = "SELECT MAX(date_posted_raw) FROM jobs"
        last_scraped = db.execute(text(last_sql)).scalar()

        return MarketSummaryResponse(
            total_jobs=total,
            cities_count=cities,
            sources_count=sources,
            salary_min=round(sal_min, 2) if sal_min else None,
            salary_max=round(sal_max, 2) if sal_max else None,
            salary_avg=round(sal_avg, 2) if sal_avg else None,
            salary_median=round(sal_median, 2) if sal_median else None,
            top_companies=top_companies,
            top_skills=top_skills_list,
            jobs_with_salary_pct=sal_pct,
            last_scraped=str(last_scraped) if last_scraped else None,
        )

    except Exception as e:
        logger.exception("Market summary error")
        raise HTTPException(status_code=500, detail=str(e))
