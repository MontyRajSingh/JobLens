# Project Structure

```
job_scraper/
├── main.py                    # CLI scraper orchestrator (cities × keywords × sources)
├── config.py                  # Central config: cities, keywords, skills taxonomy, FAANG set, COL indices
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # 3-service stack: db (Postgres), api, frontend
├── Dockerfile                 # API container
├── Dockerfile.scraper         # Scraper container
│
├── scrapers/                  # Job scraping modules
│   ├── base_scraper.py        # Abstract base class with REQUIRED_COLUMNS, validate_batch()
│   ├── indeed_scraper.py      # Indeed multi-page scraper
│   ├── levelsfyi_scraper.py   # Levels.fyi JSON extractor
│   ├── payscale_scraper.py    # PayScale salary scraper
│   ├── ziprecruiter_scraper.py
│   ├── linkedin_scraper.py
│   └── glassdoor_scraper.py
│
├── utils/                     # Shared utilities
│   ├── driver_utils.py        # Browser/WebDriver setup
│   ├── salary_utils.py        # Salary parsing, currency conversion
│   ├── text_utils.py          # Skill extraction, seniority inference, FAANG detection
│   └── validators.py          # DataFrame validation
│
├── pipeline/                  # ML training & prediction
│   ├── data_cleaner.py        # DataCleaner class
│   ├── data_quality.py        # Data quality / readiness checks
│   ├── preprocessing.py       # FeatureEngineer (one-hot, scaling)
│   ├── model.py               # SalaryPredictor (XGBoost)
│   ├── predict.py             # Prediction helpers for API
│   ├── train.py               # Training CLI entry point
│   └── models/                # Trained artifacts (model.pkl, scaler, metadata)
│
├── api/                       # FastAPI backend
│   ├── main.py                # App setup: lifespan, CORS, rate limiting, middleware
│   ├── db/
│   │   ├── database.py        # SQLAlchemy engine, jobs table schema, get_db()
│   │   └── loader.py          # save_jobs_to_db(), load_jobs_to_db()
│   ├── routes/
│   │   ├── predict.py         # POST /api/v1/predict
│   │   ├── jobs.py            # GET /api/v1/jobs, /api/v1/jobs/{id}, /api/v1/jobs/company/{name}
│   │   └── insights.py        # GET /api/v1/insights/*
│   └── schemas/
│       ├── request.py         # Pydantic request models
│       └── response.py        # Pydantic response models
│
├── frontend/                  # React SPA
│   ├── src/
│   │   ├── App.jsx            # Router with ProtectedRoute wrapper
│   │   ├── main.jsx           # Entry point
│   │   ├── api/               # Axios client, API helpers
│   │   ├── auth/              # AuthProvider (Supabase)
│   │   ├── components/        # Navbar, Charts, FilterPanel, JobCard, backgrounds
│   │   ├── pages/             # Home, Jobs, JobDetail, Predict, Insights, Login, etc.
│   │   └── lib/               # Supabase client init
│   └── package.json
│
├── data/                      # Local data files
│   └── jobs.db                # SQLite fallback DB
│
├── output/                    # Scraper output (timestamped CSVs/JSONs, master file)
│
└── .github/workflows/
    ├── daily_scraper.yml      # Cron: scrape daily → commit output/ → push
    └── deploy.yml             # CI: import checks + frontend build on push to main
```

## Architecture Patterns

- **Scrapers** inherit from `BaseScraper` and must implement `scrape()` returning a list of dicts with 27 standardized columns
- **Deduplication** uses MD5-based `dedup_key` (company + title + city hash) with UNIQUE constraint in DB
- **API routes** are mounted under `/api/v1` prefix; use SQLAlchemy raw SQL via `text()` for queries
- **Database access** uses FastAPI `Depends(get_db)` dependency injection pattern
- **Frontend auth** uses Supabase — all routes except `/login` are wrapped in `ProtectedRoute`
- **Config is centralized** in `config.py` — cities, keywords, skill taxonomy, and constants live there
- **Dual-write pattern**: scrapers save to both CSV files (backup) and PostgreSQL (primary)
- **ML model** is loaded once at API startup via lifespan event and held in app state
