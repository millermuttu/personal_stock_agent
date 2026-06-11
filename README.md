# Personal Stock Market Analyst

Backend + frontend starter implementation for the architecture in `system_arch.md`.

**Market scope:** Indian equities only (NSE/BSE via Yahoo Finance). A bare symbol
such as `RELIANCE` is routed to NSE (`RELIANCE.NS`); append `.BO` for BSE
(`RELIANCE.BO`). Symbols that already carry an `.NS`/`.BO` suffix are preserved.

## Quick start (recommended)

```bash
pip install -r requirements-dev.txt          # one-time: backend deps
cp .env.example .env                          # then add your OPENAI_API_KEY (optional)
./run.sh                                      # postgres + migrations + backend + frontend
```

Then open `http://localhost:3000`. `run.sh` also accepts `backend` or `frontend`
to launch just one side. Press Ctrl+C to stop; the Postgres container is left
running (stop it with `docker compose down`).

Without `OPENAI_API_KEY` the app still runs and uses deterministic heuristic
synthesis for the final verdict.

## Run locally (manual)

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Start PostgreSQL via Docker:

```bash
docker compose up -d postgres
```

4. Export a PostgreSQL connection string:

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/stock_agent"
```

5. Run migrations:

```bash
alembic upgrade head
```

6. Start the API:

```bash
uvicorn backend.main:app --reload
```

## Run frontend (Next.js)

From a separate terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Frontend defaults:

* App URL: `http://localhost:3000`
* Browser API base: `NEXT_PUBLIC_API_BASE_URL=/api`
* Next.js proxy target: `BACKEND_ORIGIN=http://127.0.0.1:8000`
* Run details route: `http://localhost:3000/runs/<run_id>`

Optional overrides:

```bash
export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
export BACKEND_ORIGIN="http://127.0.0.1:8000"
export CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
```

## Run tests

The test suite runs fully offline (in-memory repository + stub providers); it
needs neither PostgreSQL nor network access:

```bash
pytest -q
```

API endpoints:

* `GET /health`
* `GET /stocks/search?q=nvda`
* `POST /analysis`
* `GET /analysis/{run_id}`

## OpenAI integration

Set these environment variables to enable model-based final verdict synthesis:

```bash
export OPENAI_API_KEY="your_key_here"
export OPENAI_MODEL="gpt-4.1-mini"
export OPENAI_TEMPERATURE="0.1"
```

If `OPENAI_API_KEY` is not set, the orchestrator falls back to deterministic local synthesis.

## Data providers

All market, fundamentals, and news/sentiment data comes from **real Yahoo
Finance** lookups for **Indian (NSE/BSE) listings** — there is no mock or
synthetic data path. If Yahoo cannot return usable data for a ticker, the run
fails rather than fabricating values. Ticker search suggestions come from Yahoo's
live symbol search, filtered to Indian exchanges (`.NS` / `.BO`).

Optional reliability tuning:

```bash
export MARKET_DATA_TIMEOUT_SECONDS="20"
export MARKET_DATA_MAX_ATTEMPTS="3"
export FUNDAMENTALS_TIMEOUT_SECONDS="15"
export FUNDAMENTALS_MAX_ATTEMPTS="2"
export NEWS_TIMEOUT_SECONDS="15"
export NEWS_MAX_ATTEMPTS="2"
export NEWS_MAX_HEADLINES="8"
```

## Notes

* Current storage is PostgreSQL via SQLAlchemy async sessions.
* Market, fundamentals, and news data are sourced live from Yahoo Finance only.
* `beta` is read from Yahoo fundamentals; if unavailable the snapshot defaults it to `1.0` and adds a `risk_beta_unavailable` quality flag.
* The sentiment agent consumes both normalized headlines and provider-derived `sentiment_signals`.
* Final report includes synthesis metadata: `synthesis_source`, `model_version`, `prompt_version`, and `llm_fallback_reason` when heuristic fallback is used.
* Agent write isolation is enforced in repository updates and orchestrator state handling.
* For quick local bootstrapping without Alembic, set `AUTO_CREATE_SCHEMA=1` before running the API.
