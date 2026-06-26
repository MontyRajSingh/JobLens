# JobLens — Product Summary

JobLens is a global job market intelligence platform that scrapes job listings from multiple sources, normalizes salary data across currencies, and uses an ML model to predict salaries based on job attributes.

## Core Purpose

Answer the question: "What should this role pay in this city at this company?"

## Key Features

- Multi-source job scraping (Indeed, Levels.fyi, PayScale, ZipRecruiter, LinkedIn, Glassdoor)
- Salary normalization across 9 currencies to USD
- XGBoost-based salary prediction from job attributes
- Paginated job search with filtering (keyword, city, salary range, remote type, seniority, skills)
- Company compensation profiles with aggregate stats
- Market insights and analytics
- Daily automated scraping via GitHub Actions

## Target Users

- Job seekers researching salary benchmarks
- Hiring managers benchmarking offers

## Deployment

- Backend (FastAPI): Render
- Frontend (React SPA): Vercel
- Auth & Database: Supabase (PostgreSQL)
- Scraper automation: GitHub Actions cron (daily at 00:00 UTC)

## Coverage

- 13 cities across US, UK, Canada, Australia, Germany, Singapore, UAE, India
- 18 job keywords (data scientist, ML engineer, software engineer, etc.)
- 6 scraper sources
