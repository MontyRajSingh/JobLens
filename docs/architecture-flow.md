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
│  FastAPI on Render (api/main.py)                                            │
│    • Opens the port immediately; startup work runs in a background thread   │
│    • Loads env + ML model artifacts                                          │
│    • Initializes DB schema                                                   │
│    • Reseeds jobs from output/jobs_master.csv (skipped if CSV unchanged)    │
│    • Mounts /api/v1 routers · Exposes /health                              │
│                                                                             │
│  ┌────────────────────┐ ┌────────────────────┐ ┌─────────────────────────┐  │
│  │ Jobs Router        │ │ Predict Router     │ │ Insights Router         │  │
│  │ search · detail ·  │ │ salary · resume ·  │ │ market summaries ·      │  │
│  │ company profiles   │ │ offer analysis     │ │ salary/city · skills    │  │
│  └──────────┬─────────┘ └──────────┬─────────┘ └───────────┬─────────────┘  │
└─────────────┼──────────────────────┼───────────────────────┼────────────────┘
              │ SQLAlchemy           │ model call             │ aggregate SQL
              ▼                      ▼                       ▼
┌────────────────────────────┐  ┌──────────────────────────────────────────────┐
│       DATABASE LAYER       │  │                 ML PIPELINE                  │
│  Prod: Render Postgres     │  │  pipeline/predict.py → pipeline/models/*     │
│  Local: SQLite data/jobs.db│  │  (model.pkl, feature_*.json, *_tiers.json)   │
│  Schema: api/db/database.py│  │  loads model → features → salary + confidence│
│  Loader: api/db/loader.py  │  └──────────────────────────────────────────────┘
│  Main table: jobs          │
└─────────────┬──────────────┘
              │ seeded from committed CSV
              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            DATA INGESTION LAYER                              │
│                                                                              │
│  GitHub Actions daily scraper (.github/workflows/daily_scraper.yml)         │
│                                                                              │
│  main.py → active scrapers:                                                 │
│    levelsfyi · payscale · linkedin  (open)                                  │
│    wellfound · instahyre · naukri   (cookie-authenticated)                  │
│                                                                              │
│  Raw scrape → normalized dicts → output/jobs_master.csv (committed, seed)   │
└──────────────────────────────────────────────────────────────────────────────┘

Separate user path: React → Supabase (auth, saved predictions/offers/resumes,
favorite_jobs, resume-pdfs bucket). Schema in supabase/user_history.sql.
```

Frontend never talks to the market-data DB directly — it calls the backend via
`frontend/src/api/client.js`. User-history data is the exception: written
straight to Supabase via `frontend/src/api/userData.js`.

## Repository Layout

```text
api/        FastAPI app (main.py), db/ (database, loader), routes/, schemas/
frontend/   React + Vite: api/client.js, auth/, lib/supabase.js, pages/, components/
pipeline/   data_cleaner, preprocessing, model, predict, train + models/ artifacts
scrapers/   base_scraper.py + one *_scraper.py per source
utils/      salary_utils, text_utils, validators, driver_utils
output/jobs_master.csv   committed scraped dataset (production seed)
config.py                sources, cities, keywords, cookie-source set
render.yaml · vercel.json · Dockerfile · .github/workflows/daily_scraper.yml
```

## Data Refresh Flow

```text
GitHub scheduler (daily)
  → main.py runs each source × city-shard × keyword
  → each scraper returns normalized job dicts (non-fatal per source)
  → append to output/jobs_master.csv   ← single source of truth
  → per-source summary + ::warning:: annotations + step-summary table
  → git commit, then rebase-and-retry push (can't drop a night's data)
  → Render redeploys → FastAPI reseeds the jobs table from the CSV in a
    background thread (new CSV → new fingerprint → full reseed)
```

Key properties:

- **CSV is the source of truth.** The scraper does **not** write to the DB; the
  API reseeds from `jobs_master.csv` on boot (`reseed_jobs_from_csv`).
- **Fast boot.** The API opens its port immediately and runs model loading +
  seeding in a background thread. The reseed stores an MD5 fingerprint of the
  seeded CSV in the `app_meta` table and is skipped entirely when the DB
  already holds that exact CSV — so restarts without a new scrape serve
  existing data instantly. When a reseed does run, it loads into a
  `jobs_staging` table and swaps it in atomically, so concurrent requests
  never see an empty jobs table.
- **Fail-loud, non-fatal.** One dead scraper never crashes the run. Empty
  sources raise a GitHub warning annotation and a step-summary flag; only a
  **total blackout** (every source returns 0) fails the run.
- **Safe push.** The commit only appends rows, so the push rebases on the latest
  `main` and retries — a diverged remote can't silently lose data.

## Scraper Sources

| Source | Access | Notes |
|--------|--------|-------|
| Levels.fyi, PayScale, LinkedIn | open | no auth needed |
| Wellfound, Instahyre, Naukri | cookie | need `<SOURCE>_COOKIE` GitHub secret |
| ~~Indeed, ZipRecruiter~~ | dropped | hard-block CI datacenter IPs (403); need paid residential proxies |

Cookie sources read a browser `Cookie:` header string from
`WELLFOUND_COOKIE` / `INSTAHYRE_COOKIE` / `NAUKRI_COOKIE` via
`BaseScraper.load_cookies(...)`. Missing/expired cookies → the source returns
nothing and is flagged in the run summary (never a crash). Cookies expire
periodically and must be refreshed manually.

## End-to-End Flows (frontend → API → data)

```text
Job search      Jobs.jsx → searchJobs → GET /jobs → jobs table → JobCard list
Job detail      JobDetail.jsx → getJob → GET /jobs/{id} → JobRecord
Company profile CompanyProfile.jsx → GET /jobs/company/{name} → aggregate SQL
Salary predict  Predict.jsx → POST /predict → pipeline.predict → models/*
Resume predict  Predict.jsx → POST /predict/resume → PDF text → infer → predict
Offer analysis  OfferAnalyzer.jsx → POST /predict/offer → verdict
Market insights Insights.jsx → GET /insights/* → aggregate SQL → Charts.jsx
Saved history   Login → Supabase Auth → userData.js → Supabase → History.jsx
```

## Deployment

```text
Vercel (vercel.json)          Render (render.yaml)
  build + serve frontend        joblens-api  (Docker, health /health)
  SPA fallback                  joblens-db   (Postgres, DATABASE_URL)
  /api/* rewrite ────────────▶  DATA_DIR=/app/output · MODEL_DIR=/app/pipeline/models
```

- Render API env: `DATABASE_URL`, `ENVIRONMENT`, `MODEL_DIR`, `DATA_DIR`,
  `CORS_ORIGINS`, `SKIP_RESEED`.
- Frontend env: `VITE_API_URL` (blank = same-origin `/api`),
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (all optional).
- Daily scraper secrets: `WELLFOUND_COOKIE`, `INSTAHYRE_COOKIE`, `NAUKRI_COOKIE`.

## Operational Commands

```bash
uvicorn api.main:app --reload --port 8000     # local API
npm --prefix frontend run dev                 # local frontend
python3 scripts/rebuild_local_db.py           # rebuild local SQLite from CSV
python3 -m pytest tests                        # tests
# health: https://joblens-api.onrender.com/health
```

## Ownership Rules

- Frontend pages call `frontend/src/api/client.js`; never hardcode backend URLs.
- User history goes through Supabase / `userData.js`; public market data through
  FastAPI and the `jobs` table.
- Runtime salary inference goes through `pipeline.predict`.
- Source-specific parsing stays inside each scraper adapter.
- `output/jobs_master.csv` is the production seed; `data/jobs.db` is a local
  derived artifact.
- Active deployment is Vercel frontend + Render API/Postgres.
```
