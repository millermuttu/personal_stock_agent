# Personal Stock Market Analyst

Initial backend implementation for the architecture in `system_arch.md`.

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

## Notes

* Current storage is PostgreSQL via SQLAlchemy async sessions.
* Snapshot data and agent reasoning are deterministic mock implementations.
* Agent write isolation is enforced in repository updates and orchestrator state handling.
* For quick local bootstrapping without Alembic, set `AUTO_CREATE_SCHEMA=1` before running the API.
