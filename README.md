# Personal Stock Market Analyst

Backend + frontend starter implementation for the architecture in `system_arch.md`.

## Run locally

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

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/stock_agent"
alembic upgrade head
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

## Market data provider mode

Choose market data source with:

```bash
export MARKET_DATA_PROVIDER="hybrid"
```

Supported values:

* `hybrid` (default): try Yahoo Finance first, then fall back to mock data
* `yahoo`: use only Yahoo Finance
* `mock`: use deterministic mock market data (recommended for offline tests)

## Fundamentals provider mode

Choose fundamentals source with:

```bash
export FUNDAMENTALS_PROVIDER="hybrid"
```

Supported values:

* `hybrid` (default): try Yahoo Finance first, then fall back to mock fundamentals
* `yahoo`: use only Yahoo fundamentals
* `mock`: use deterministic mock fundamentals (recommended for offline tests)

## News provider mode

Choose news/sentiment source with:

```bash
export NEWS_PROVIDER="hybrid"
```

Supported values:

* `hybrid` (default): try Yahoo Finance news first, then fall back to mock headlines
* `yahoo`: use only Yahoo news headlines
* `mock`: use deterministic mock headlines and sentiment signals (recommended for offline tests)

## Real-data mode (Yahoo only)

To force real provider usage only (no fallback), set:

```bash
export MARKET_DATA_PROVIDER="yahoo"
export FUNDAMENTALS_PROVIDER="yahoo"
export NEWS_PROVIDER="yahoo"
```

Optional reliability tuning:

```bash
export MARKET_DATA_TIMEOUT_SECONDS="20"
export MARKET_DATA_MAX_ATTEMPTS="3"
export FUNDAMENTALS_TIMEOUT_SECONDS="15"
export FUNDAMENTALS_MAX_ATTEMPTS="2"
export NEWS_TIMEOUT_SECONDS="15"
export NEWS_MAX_ATTEMPTS="2"
```

## Notes

* Current storage is PostgreSQL via SQLAlchemy async sessions.
* Market, fundamentals, and news data are provider-driven (`yahoo`, `mock`, `hybrid`).
* The sentiment agent consumes both normalized headlines and provider-derived `sentiment_signals`.
* Final report includes synthesis metadata: `synthesis_source`, `model_version`, `prompt_version`, and `llm_fallback_reason` when heuristic fallback is used.
* Agent write isolation is enforced in repository updates and orchestrator state handling.
* For quick local bootstrapping without Alembic, set `AUTO_CREATE_SCHEMA=1` before running the API.
