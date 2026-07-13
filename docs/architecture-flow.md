# JobLens System Architecture

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                USER INTERFACE                                │
│                                                                              │
│  React + Vite app on Vercel                                                  │
│                                                                              │
│  Pages: Home · Jobs · Job Detail · Predict · Offer Analyzer · Insights       │
│         Company Profile · History · Login                                    │
│                                                                              │
│  Components: Navbar · JobCard · FilterPanel · Charts · Visual backgrounds    │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │
                                    │ /api/* requests
                                    │ Vercel rewrite
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND API LAYER                              │
│                                                                             │
│  FastAPI on Render                                                          │
│                                                                             │
│  api/main.py                                                                │
│    • Loads environment                                                      │
│    • Loads ML model artifacts                                               │
│    • Initializes database schema                                            │
│    • Reseeds jobs from output/jobs_master.csv                               │
│    • Mounts /api/v1 routers                                                 │
│    • Exposes /health                                                        │
│                                                                             │
│  ┌────────────────────┐ ┌────────────────────┐ ┌─────────────────────────┐  │
│  │ Jobs Router        | │ Predict Router     │ │ Insights Router         │  │
│  │ api/routes/jobs.py │ │ api/routes/predict.py│ │ api/routes/insights.py│  │
│  │                    │ │                    │ │                         │  │
│  │ search jobs        │ │ salary prediction   │ │ market summaries       │  │
│  │ job details        │ │ resume prediction   │ │ salary by city         │  │
│  │ company profiles   │ │ offer analysis      │ │ top skills             │  │
│  └──────────┬─────────┘ └──────────┬─────────┘ └───────────┬─────────────┘  │
└─────────────┼──────────────────────┼───────────────────────┼────────────────┘
              │                      │                       │
              │ SQLAlchemy           │ model call             │ aggregate SQL
              ▼                      ▼                       ▼
┌────────────────────────────┐  ┌──────────────────────────────────────────────┐
│       DATABASE LAYER       │  │                 ML PIPELINE                  │
│                            │  │                                              │
│  Production: Render        │  │  pipeline/predict.py                         │
│  Postgres via DATABASE_URL │  │    • loads persisted model                   │
│                            │  │    • transforms request into model features  │
│  Local: SQLite             │  │    • applies salary adjustments              │
│  data/jobs.db              │  │    • returns confidence and explainability   │
│                            │  │                                              │
│  Schema: api/db/database.py│  │  pipeline/models/                            │
│  Loader: api/db/loader.py  │  │    • model.pkl                               │
│                            │  │    • feature_state.json                      │
│  Main table: jobs          │  │    • feature_columns.json                    │
└─────────────┬──────────────┘  │    • skill_premiums.json                     │
              │                 │    • company_tiers.json                      │
              │                 │    • metadata.json                           │
              │                 └──────────────────────────────────────────────┘
              │
              │ seeded from committed CSV
              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            DATA INGESTION LAYER                              │
│                                                                              │
│  GitHub Actions daily scraper                                                │
│  .github/workflows/daily_scraper.yml                                         │
│                                                                              │
│  main.py                                                                     │
│    ├─ scrapers/indeed_scraper.py                                             │
│    ├─ scrapers/linkedin_scraper.py                                           │
│    ├─ scrapers/levelsfyi_scraper.py                                          │
│    ├─ scrapers/payscale_scraper.py                                           │
│    ├─ scrapers/ziprecruiter_scraper.py                                       │
│    ├─ scrapers/wellfound_scraper.py                                          │
│    ├─ scrapers/instahyre_scraper.py                                          │
│    └─ scrapers/naukri_scraper.py                                             │
│                                                                              │
│  Raw scrape → normalized job dicts → output/jobs_master.csv                  │
│  output/jobs_master.csv is committed and used as production seed data        │
└──────────────────────────────────────────────────────────────────────────────┘

Separate user-specific path:

┌──────────────────────────────────────────────────────────────────────────────┐
│                         AUTH AND USER HISTORY LAYER                          │
│                                                                              │
│  React frontend                                                              │
│    ├─ frontend/src/lib/supabase.js                                           │
│    ├─ frontend/src/auth/AuthProvider.jsx                                     │
│    └─ frontend/src/api/userData.js                                           │
│                                                                              │
│  Supabase                                                                    │
│    • Auth sessions                                                           │
│    • saved_predictions                                                       │
│    • saved_offers                                                            │
│    • saved_resumes                                                           │
│    • favorite_jobs                                                           │
│    • private resume-pdfs storage bucket                                      │
│                                                                              │
│  SQL setup: supabase/user_history.sql                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Repository Structure

```text
JobLens/
├── api/
│   ├── main.py                         FastAPI app, startup, CORS, auth, routers
│   ├── db/
│   │   ├── database.py                 SQLAlchemy engine, sessions, jobs schema
│   │   └── loader.py                   CSV reseed, inserts, training-data load
│   ├── routes/
│   │   ├── jobs.py                     Job search, job detail, company profile
│   │   ├── predict.py                  Salary, resume, and offer prediction
│   │   └── insights.py                 Market analytics endpoints
│   └── schemas/
│       ├── request.py                  Pydantic request contracts
│       └── response.py                 Pydantic response contracts
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx                    React mount
│   │   ├── App.jsx                     Routes and ProtectedRoute
│   │   ├── api/
│   │   │   ├── client.js               Backend HTTP client
│   │   │   └── userData.js             Supabase saved-history calls
│   │   ├── auth/AuthProvider.jsx       Supabase auth state provider
│   │   ├── lib/supabase.js             Supabase browser client
│   │   ├── pages/                      Product pages
│   │   └── components/                 Shared UI components
│   ├── package.json                    Frontend scripts and deps
│   └── vite.config.js                  Local dev server and /api proxy
│
├── pipeline/
│   ├── data_cleaner.py                 Cleans scraped data and salary fields
│   ├── preprocessing.py                Feature engineering
│   ├── model.py                        Model train/load wrapper
│   ├── predict.py                      Runtime inference API
│   ├── train.py                        Training entry point
│   ├── data_quality.py                 Training-readiness checks
│   └── models/                         Committed inference artifacts
│
├── scrapers/
│   ├── base_scraper.py                 Common scraper interface
│   └── *_scraper.py                    Source-specific adapters
│
├── utils/
│   ├── salary_utils.py                 Salary parsing and normalization helpers
│   ├── text_utils.py                   Text cleanup and extraction helpers
│   ├── validators.py                   Data validation helpers
│   └── driver_utils.py                 Selenium Chrome setup
│
├── output/jobs_master.csv              Committed scraped market dataset
├── data/jobs.db                        Local derived SQLite DB
├── scripts/rebuild_local_db.py         Rebuilds local SQLite from CSV
├── supabase/user_history.sql           Supabase tables, RLS, storage policies
├── tests/                              Regression tests
├── render.yaml                         Render API + Postgres deployment
├── vercel.json                         Vercel frontend + API rewrite
├── Dockerfile                          Backend API image
├── Dockerfile.scraper                  Scraper image support
└── .github/workflows/daily_scraper.yml Daily data refresh workflow
```

## Runtime Flow

```text
┌─────────────┐
│ User Browser│
└──────┬──────┘
       │
       │ loads static app
       ▼
┌────────────────────┐
│ Vercel Frontend     │
│ frontend/dist       │
└──────┬─────────────┘
       │
       │ /api/v1/*
       ▼
┌────────────────────┐
│ Render FastAPI API  │
│ api/main.py         │
└──────┬─────────────┘
       │
       ├──────────────▶ pipeline/predict.py
       │                 pipeline/models/*
       │
       └──────────────▶ Render Postgres
                         jobs table
```

Frontend code never talks directly to the market-data database. It calls the
backend through `frontend/src/api/client.js`. User-history data is the exception:
the frontend writes that directly to Supabase through `frontend/src/api/userData.js`.

## Frontend Layer

```text
┌────────────────────────────────────────────────────────────────┐
│                         React App                              │
│                                                                │
│  main.jsx                                                      │
│    └─ AuthProvider                                             │
│       └─ BrowserRouter                                         │
│          └─ App.jsx                                            │
│             ├─ Navbar                                          │
│             ├─ ProtectedRoute                                  │
│             └─ Routes                                          │
│                ├─ /login       Login.jsx                       │
│                ├─ /            Home.jsx                        │
│                ├─ /jobs        Jobs.jsx                        │
│                ├─ /jobs/:id    JobDetail.jsx                   │
│                ├─ /predict     Predict.jsx                     │
│                ├─ /offer       OfferAnalyzer.jsx               │
│                ├─ /insights    Insights.jsx                    │
│                ├─ /companies/:companyName CompanyProfile.jsx   │
│                └─ /history     History.jsx                     │
└────────────────────────────────────────────────────────────────┘
```

### Frontend API Calls

```text
frontend/src/api/client.js
  ├─ predictSalary(payload)        POST /api/v1/predict
  ├─ predictFromResume(file)       POST /api/v1/predict/resume
  ├─ analyzeOffer(payload)         POST /api/v1/predict/offer
  ├─ searchJobs(params)            GET  /api/v1/jobs
  ├─ getJob(id)                    GET  /api/v1/jobs/{id}
  ├─ getCompanyProfile(name)       GET  /api/v1/jobs/company/{name}
  ├─ getSalaryByCity(keyword)      GET  /api/v1/insights/salary-by-city
  ├─ getTopSkills(city, seniority) GET  /api/v1/insights/top-skills
  ├─ getSalaryBySeniority()        GET  /api/v1/insights/salary-by-seniority
  ├─ getRemoteVsOnsite()           GET  /api/v1/insights/remote-vs-onsite
  └─ getMarketSummary()            GET  /api/v1/insights/market-summary
```

`VITE_API_URL` controls the base URL. If it is empty, requests use same-origin
`/api`, which is what Vercel rewrites to Render.

## Auth And User History Layer

```text
┌────────────────────────────────────────────────────────────────┐
│                         Supabase Auth                          │
│                                                                │
│  frontend/src/lib/supabase.js                                  │
│    └─ createClient(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)  │
│                                                                │
│  frontend/src/auth/AuthProvider.jsx                            │
│    ├─ getSession()                                             │
│    ├─ onAuthStateChange()                                      │
│    ├─ signInWithGoogle()                                       │
│    ├─ signInWithEmail()                                        │
│    ├─ signUpWithEmail()                                        │
│    └─ signOut()                                                │
└────────────────────────────────────────────────────────────────┘
```

Auth is optional. If Supabase env vars are not configured, `ProtectedRoute`
allows the app to run without login.

User-specific data goes to Supabase:

```text
frontend/src/api/userData.js
  ├─ savePrediction()
  ├─ saveOffer()
  ├─ uploadResumePdf()
  ├─ saveResume()
  ├─ getFavoriteJob()
  ├─ addFavoriteJob()
  ├─ removeFavoriteJob()
  ├─ listSavedPredictions()
  ├─ listSavedOffers()
  ├─ listSavedResumes()
  └─ listFavoriteJobs()
```

Supabase schema:

```text
supabase/user_history.sql
  ├─ storage bucket: resume-pdfs
  ├─ table: saved_predictions
  ├─ table: saved_offers
  ├─ table: saved_resumes
  ├─ table: favorite_jobs
  └─ row-level security policies scoped to auth.uid()
```

## Backend API Layer

```text
┌────────────────────────────────────────────────────────────────┐
│                         FastAPI App                            │
│                                                                │
│  api/main.py                                                   │
│    ├─ load .env                                                │
│    ├─ load model artifacts                                     │
│    ├─ init DB schema                                           │
│    ├─ reseed jobs from CSV                                     │
│    ├─ configure CORS                                           │
│    ├─ configure rate limits                                    │
│    ├─ optional API-key protection for /predict                 │
│    ├─ include jobs router                                      │
│    ├─ include predict router                                   │
│    ├─ include insights router                                  │
│    └─ expose /health                                           │
└────────────────────────────────────────────────────────────────┘
```

### Routes

```text
api/routes/jobs.py
  GET /api/v1/jobs
    Query params:
      keyword, city, min_salary, max_salary, remote_type,
      seniority_level, skills, source, page, page_size
    Returns:
      JobSearchResponse

  GET /api/v1/jobs/{id}
    Returns:
      JobRecord

  GET /api/v1/jobs/company/{company_name}
    Returns:
      CompanyProfileResponse
```

```text
api/routes/predict.py
  POST /api/v1/predict
    Input:
      PredictRequest
    Returns:
      PredictResponse

  POST /api/v1/predict/resume
    Input:
      PDF file
    Work:
      extract text -> infer profile fields -> predict salary -> gap analysis

  POST /api/v1/predict/offer
    Input:
      OfferAnalyzeRequest
    Returns:
      OfferAnalyzeResponse
```

```text
api/routes/insights.py
  GET /api/v1/insights/salary-by-city
  GET /api/v1/insights/top-skills
  GET /api/v1/insights/salary-by-seniority
  GET /api/v1/insights/remote-vs-onsite
  GET /api/v1/insights/market-summary
```

## Database Layer

```text
┌────────────────────────────────────────────────────────────────┐
│                         SQLAlchemy                             │
│                                                                │
│  api/db/database.py                                            │
│    ├─ reads DATABASE_URL                                       │
│    ├─ if present: PostgreSQL engine                            │
│    ├─ if missing: SQLite engine at data/jobs.db                │
│    ├─ SessionLocal                                             │
│    ├─ get_db() FastAPI dependency                              │
│    ├─ get_engine()                                             │
│    └─ jobs_table schema                                        │
└────────────────────────────────────────────────────────────────┘
```

### Jobs Table

```text
jobs
  id
  job_title
  company_name
  company_name_raw
  city
  location
  salary
  salary_currency
  salary_usd_numeric
  seniority_level
  experience_required
  employment_type
  remote_type
  industry
  education_required
  has_equity
  has_bonus
  has_remote_benefits
  skills_required
  job_description
  job_link
  job_id
  source_website
  dedup_key
  is_faang
  cost_of_living_index
  date_posted_raw
  applicant_count
  currency
  scraped_at
```

### DB Loader

```text
api/db/loader.py
  ├─ save_jobs_to_db(jobs)
  │    insert rows with dedupe on dedup_key
  │
  ├─ load_jobs_to_db(csv_path)
  │    CSV -> dict rows -> save_jobs_to_db
  │
  ├─ reseed_jobs_from_csv(csv_path)
  │    CSV -> DataCleaner -> replace jobs table
  │
  └─ load_training_data()
       jobs table -> Pandas DataFrame
```

Local rebuild:

```bash
python3 scripts/rebuild_local_db.py
```

## ML Pipeline Layer

```text
┌────────────────────────────────────────────────────────────────┐
│                         ML Runtime                             │
│                                                                │
│  POST /api/v1/predict                                          │
│        │                                                       │
│        ▼                                                       │
│  api/routes/predict.py                                         │
│        │                                                       │
│        ▼                                                       │
│  pipeline/predict.py                                           │
│        ├─ load FeatureEngineer                                 │
│        ├─ load SalaryPredictor                                 │
│        ├─ transform request into feature vector                │
│        ├─ predict salary                                       │
│        ├─ apply transparent adjustments                        │
│        ├─ calculate confidence interval                        │
│        └─ return prediction payload                            │
└────────────────────────────────────────────────────────────────┘
```

Training and preprocessing modules:

```text
pipeline/data_cleaner.py
  Cleans scraped jobs, repairs fields, parses salary_usd_numeric.

pipeline/preprocessing.py
  Builds model features and aligns runtime columns.

pipeline/model.py
  Trains, saves, loads, and runs the salary model.

pipeline/train.py
  Training command entry point.

pipeline/data_quality.py
  Dataset readiness checks.
```

Committed model artifacts:

```text
pipeline/models/model.pkl
pipeline/models/feature_scaler.pkl
pipeline/models/feature_state.json
pipeline/models/feature_columns.json
pipeline/models/company_tiers.json
pipeline/models/skill_premiums.json
pipeline/models/metadata.json
```

## Scraper And Data Refresh Layer

```text
┌────────────────────────────────────────────────────────────────┐
│                     GitHub Daily Scraper                        │
│                                                                │
│  .github/workflows/daily_scraper.yml                           │
│    ├─ checkout repo                                            │
│    ├─ install Python deps                                      │
│    ├─ install Scrapling browsers                               │
│    ├─ compute day-of-week shard                                │
│    ├─ run main.py                                              │
│    └─ commit output/ changes                                   │
└────────────────────────────────────────────────────────────────┘
```

Scraper runtime:

```text
main.py
  ├─ loads configured cities and keywords from config.py
  ├─ selects sources
  ├─ calls scraper adapters
  ├─ normalizes records
  ├─ writes output/jobs_master.csv
  └─ can insert into DB when DATABASE_URL is provided
```

Scraper adapters:

```text
scrapers/base_scraper.py
scrapers/indeed_scraper.py
scrapers/linkedin_scraper.py
scrapers/levelsfyi_scraper.py
scrapers/payscale_scraper.py
scrapers/ziprecruiter_scraper.py
scrapers/wellfound_scraper.py
scrapers/instahyre_scraper.py
scrapers/naukri_scraper.py
```

Shared scraper helpers:

```text
utils/driver_utils.py
utils/salary_utils.py
utils/text_utils.py
utils/validators.py
```

Production refresh:

```text
daily scraper commit
  -> GitHub main changes
  -> Render auto-deploys API
  -> API startup reads output/jobs_master.csv
  -> reseed_jobs_from_csv()
  -> jobs table refreshed
```

## Deployment Layer

```text
┌──────────────────────────────┐      ┌──────────────────────────────┐
│            Vercel            │      │            Render            │
│                              │      │                              │
│  vercel.json                 │      │  render.yaml                 │
│    ├─ build frontend         │      │    ├─ joblens-api            │
│    ├─ serve static assets    │      │    │   runtime: Docker       │
│    ├─ SPA fallback           │      │    │   health: /health       │
│    └─ /api rewrite ──────────┼─────▶│    │   DATA_DIR=/app/output  │
│                              │      │    │   MODEL_DIR=/app/...    │
│                              │      │    └─ joblens-db             │
│                              │      │        Render Postgres       │
└──────────────────────────────┘      └──────────────────────────────┘
```

Render API env:

```text
DATABASE_URL      from joblens-db
ENVIRONMENT       production
MODEL_DIR         /app/pipeline/models
DATA_DIR          /app/output
CORS_ORIGINS      *
SKIP_RESEED       false
```

Frontend env:

```text
VITE_API_URL                optional; blank means same-origin /api
VITE_SUPABASE_URL           optional Supabase project URL
VITE_SUPABASE_ANON_KEY      optional Supabase anon key
```

## End-To-End Flows

### Job Search

```text
Jobs.jsx
  -> searchJobs(params)
  -> GET /api/v1/jobs
  -> api/routes/jobs.py
  -> SQLAlchemy session
  -> jobs table
  -> JobSearchResponse
  -> JobCard list
```

### Job Detail

```text
JobDetail.jsx
  -> getJob(id)
  -> GET /api/v1/jobs/{id}
  -> jobs table
  -> JobRecord
```

### Company Profile

```text
CompanyProfile.jsx
  -> getCompanyProfile(companyName)
  -> GET /api/v1/jobs/company/{company_name}
  -> aggregate SQL over jobs table
  -> CompanyProfileResponse
```

### Salary Prediction

```text
Predict.jsx
  -> predictSalary(payload)
  -> POST /api/v1/predict
  -> PredictRequest
  -> api/routes/predict.py
  -> pipeline.predict.predict_salary()
  -> pipeline/models/*
  -> similar jobs query
  -> PredictResponse
```

### Resume Prediction

```text
Predict.jsx
  -> upload PDF
  -> POST /api/v1/predict/resume
  -> PyPDF2 extracts text
  -> route infers title, skills, seniority, experience
  -> salary prediction
  -> resume gap analysis
  -> optional Supabase save
```

### Offer Analysis

```text
OfferAnalyzer.jsx
  -> analyzeOffer(payload)
  -> POST /api/v1/predict/offer
  -> predicted salary or market reference salary
  -> total compensation comparison
  -> verdict and recommendation
```

### Market Insights

```text
Insights.jsx
  -> client.js insight calls
  -> /api/v1/insights/*
  -> aggregate SQL over jobs table
  -> Charts.jsx
```

### Login And Saved History

```text
Login.jsx
  -> AuthProvider
  -> Supabase Auth
  -> session in React context

Prediction / offer / favorite / resume save
  -> userData.js
  -> Supabase table or storage bucket
  -> History.jsx reads saved records
```

### Daily Data Refresh

```text
GitHub scheduler
  -> daily_scraper.yml
  -> main.py
  -> scrapers/*
  -> output/jobs_master.csv
  -> git commit
  -> Render deploy
  -> FastAPI startup
  -> reseed_jobs_from_csv()
  -> jobs table ready
```

## Key Contracts

### Backend Request Models

```text
api/schemas/request.py
  PredictRequest
  OfferAnalyzeRequest
  JobSearchRequest
```

### Backend Response Models

```text
api/schemas/response.py
  PredictResponse
  OfferAnalyzeResponse
  JobRecord
  CompanyProfileResponse
  JobSearchResponse
  SalaryByCityItem
  TopSkillItem
  SalaryBySeniorityItem
  RemoteVsOnsiteResponse
  MarketSummaryResponse
  HealthResponse
```

## Operational Commands

Local API:

```bash
uvicorn api.main:app --reload --port 8000
```

Local frontend:

```bash
npm --prefix frontend run dev
```

Rebuild local DB:

```bash
python3 scripts/rebuild_local_db.py
```

Run tests:

```bash
python3 -m pytest tests
```

Production health:

```text
https://joblens-api.onrender.com/health
```

## Ownership Rules

- Frontend pages call `frontend/src/api/client.js`; they should not hardcode backend URLs.
- User-specific history goes through Supabase and `frontend/src/api/userData.js`.
- Public market data goes through FastAPI and the `jobs` table.
- Runtime salary inference goes through `pipeline.predict`.
- Scraper-specific parsing stays inside each scraper adapter.
- `output/jobs_master.csv` is the production seed dataset.
- `data/jobs.db` is a local derived artifact.
- Active production deployment is Vercel frontend plus Render API/Postgres.
