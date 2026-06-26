# Tech Stack & Build System

## Languages

- Python 3.11+ (backend, scrapers, ML pipeline)
- JavaScript/JSX (frontend, React 18)

## Backend

- **Framework**: FastAPI with Uvicorn
- **Database**: PostgreSQL (prod via Supabase), SQLite (dev fallback) via SQLAlchemy 2.0+
- **Auth**: Supabase Auth (frontend-driven), API key auth on /predict in production
- **Rate limiting**: SlowAPI (60/min predict, 200/min general)
- **Validation**: Pydantic 2.0+ response models

## Frontend

- **Build tool**: Vite 5
- **Framework**: React 18 with React Router 6
- **Styling**: Tailwind CSS 3
- **HTTP client**: Axios
- **Auth**: @supabase/supabase-js
- **Charts**: Recharts
- **Animations**: Framer Motion, GSAP, Three.js
- **Icons**: Lucide React

## Scraping

- **Primary library**: Scrapling (with fetchers)
- **Browser automation**: Playwright
- **HTTP**: Requests
- **Headless Chrome** configured via `config.py` CHROME_OPTIONS

## ML Pipeline

- **Model**: XGBoost (regressor)
- **Preprocessing**: scikit-learn (StandardScaler, train/test split)
- **Data**: pandas, numpy
- **Serialization**: joblib (pickle)
- **Explainability**: SHAP (scaffolded, not yet integrated)

## Infrastructure

- **Containerization**: Docker + Docker Compose (Postgres 16, API, Frontend/nginx)
- **CI/CD**: GitHub Actions (daily scraper cron, deploy checks on push to main)
- **Deployment**: Render (API), Vercel (frontend)
- **Environment**: python-dotenv for .env loading

## Common Commands

```bash
# --- Backend API ---
uvicorn api.main:app --reload --port 8000

# --- Frontend ---
cd frontend && npm run dev       # Dev server
cd frontend && npm run build     # Production build

# --- Scraper ---
python main.py --sources indeed levelsfyi payscale ziprecruiter --max-jobs 10
python main.py --sources linkedin --max-jobs 30

# --- ML Pipeline ---
python -m pipeline.train                     # Train on scraped CSV (output/jobs_master.csv)
python -m pipeline.train --use-db            # Train on scraped data from DB

# --- Docker (full stack) ---
docker-compose up --build

# --- Install Python deps ---
pip install -r requirements.txt

# --- Install frontend deps ---
cd frontend && npm install

# --- Install Scrapling browsers ---
scrapling install
```

## Environment Variables

Key env vars (defined in `.env` at root and `frontend/.env`):

- `DATABASE_URL` — PostgreSQL connection string (prod)
- `API_KEYS` — Comma-separated API keys for /predict auth
- `CORS_ORIGINS` — Allowed origins in production
- `ENVIRONMENT` — "development" or "production"
- `MODEL_DIR` — Path to ML model artifacts
- `GLASSDOOR_EMAIL` / `GLASSDOOR_PASSWORD` — Glassdoor credentials
- `VITE_API_URL` — Backend URL for frontend
- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — Supabase config for frontend
