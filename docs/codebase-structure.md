# JobLens Codebase Structure

This document records the intended module shape for JobLens. The goal is to keep each module deep: callers learn a small interface while scraper, cleaning, model, storage, and deployment details stay local to the implementation.

## Runtime Modules

### Scraper Module

- Seam: `main.py` / `run_pipeline(...)` for orchestration, `BaseScraper.scrape(...)` for individual source adapters.
- Interface: source name, keyword, location, currency, USD rate, and max jobs in; normalized job dictionaries out.
- Implementation: site-specific adapters in `scrapers/` and shared browser/text/salary helpers in `utils/`.
- Active sources (`config.ENABLED_SOURCES`): `levelsfyi`, `payscale`, `linkedin` (open) and `wellfound`, `instahyre`, `naukri` (cookie-authenticated, listed in `config.COOKIE_SOURCES`). Indeed and ZipRecruiter were dropped — both hard-block CI datacenter IPs (403) and would need paid residential proxies.
- Cookie auth: login-walled sources read a browser `Cookie:` header string from a `<SOURCE>_COOKIE` env var (GitHub secret) via `BaseScraper.load_cookies(env_var, domain)`, injected into the Scrapling fetch. A missing/expired cookie makes that source return nothing — it never crashes the run.
- Output: the pipeline writes only `output/jobs_master.csv` (the source of truth); it does **not** write to the database. The API reseeds the DB from the CSV in a background thread on startup, skipping the reseed when the DB already holds that exact CSV.
- Fail-loud, non-fatal: each source is isolated. `main._emit_run_summary` prints a per-source yield table, raises a `::warning::` annotation and step-summary flag for empty sources, and exits non-zero only on a total blackout (every source returns 0).
- Locality rule: selectors, text extraction quirks, rate-limit handling, and source-specific parsing stay inside the source adapter.

### Cleaning And Feature Module

- Seam: `DataCleaner.clean(df)` and `FeatureEngineer.fit_transform/transform(df)`.
- Interface: dataframe in, dataframe out, with the scraper schema normalized at the cleaner seam.
- Implementation: salary parsing, metadata repair, skill inference, feature encoding, and model feature alignment.
- Locality rule: callers should not pre-fill optional scraper columns just to protect cleaner internals.

### Model Module

- Seam: `pipeline.predict.predict_salary(...)` and the FastAPI prediction route.
- Interface: job attributes in, salary estimate and confidence metadata out.
- Implementation: persisted model artifacts in `pipeline/models/`, feature state, post-model adjustments, and explainability data.
- Locality rule: route handlers should not know feature-column details.

### API Module

- Seam: `/api/v1/*` route contracts and `/health`.
- Interface: Pydantic request/response schemas in `api/schemas/`.
- Implementation: DB startup, reseeding, rate limiting, CORS, and route-specific query logic.
- Fast boot: the lifespan hook opens the port immediately and runs model loading + DB seeding in a background thread. Reseeding fingerprints the CSV (MD5, stored in the `app_meta` table) and is skipped when the DB was already seeded from a byte-identical CSV; when it does run, it builds a `jobs_staging` table and swaps it in atomically so live requests never see an empty table.
- Locality rule: deployment-specific boot flags belong in environment variables, not route handlers.

### Local Database Rebuild

The development SQLite database is a derived artifact from `output/jobs_master.csv`. If `data/jobs.db` is missing, stale, or has an old schema, rebuild it with:

```bash
python3 scripts/rebuild_local_db.py
```

This replaces only `data/jobs.db`, runs the cleaner, and loads the current API schema.

`data/jobs.db` is git-ignored and must stay untracked — it is a derived local artifact, never a data source of record.

### Frontend Module

- Seam: `frontend/src/api/client.js` and the React routes in `App.jsx`.
- Interface: page-level user workflows call named API client functions.
- Implementation: route protection, Supabase adapter, visual components, and Nginx same-origin proxying.
- Locality rule: pages should call the API client, not construct backend URLs directly.

### Deployment Module

- Seam: `render.yaml` for the FastAPI service and `vercel.json` for the frontend.
- Interface: push to GitHub; Render rebuilds `joblens-api`, and Vercel builds the React frontend from `frontend/`.
- Implementation: Dockerized FastAPI on Render, static React on Vercel, `/api/*` rewrites to the Render API, health checks, and seed/reseed behavior.
- Locality rule: only the active deployment adapter should sit at the root. Retired provider configs belong in docs/history or git history, not beside the active adapter.

## Repository Layout Rules

- Root should contain active entrypoints, active deployment files, and repo-wide config only.
- Automated tests live in `tests/`; manual network/browser smoke scripts live in `tests/smoke/` and should not use pytest's `test_*.py` filename pattern.
- Generated artifacts stay ignored: caches, `frontend/dist`, `frontend/node_modules`, local env files, debug dumps.
- Provider-specific deployment files should not be kept unless they are actively verified in CI or documented as supported.
