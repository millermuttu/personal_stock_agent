#!/usr/bin/env bash
#
# run.sh — launch the Personal Stock Market Analyst (Indian market) locally.
#
# Brings up PostgreSQL (Docker), applies migrations, then starts the FastAPI
# backend and the Next.js frontend. Press Ctrl+C to stop backend + frontend.
#
# Usage:
#   ./run.sh                # full stack: postgres + backend + frontend
#   ./run.sh backend        # postgres + backend only
#   ./run.sh frontend       # frontend only (assumes backend already running)
#
# Secrets/config: put OPENAI_API_KEY (and any overrides) in a `.env` file at the
# repo root, or export them before running. Without OPENAI_API_KEY the app still
# works and falls back to deterministic heuristic synthesis.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# --- pretty logging -----------------------------------------------------------
c_info()  { printf '\033[1;34m[run]\033[0m %s\n' "$*"; }
c_ok()    { printf '\033[1;32m[run]\033[0m %s\n' "$*"; }
c_warn()  { printf '\033[1;33m[run]\033[0m %s\n' "$*"; }
c_err()   { printf '\033[1;31m[run]\033[0m %s\n' "$*" >&2; }

# --- load optional .env -------------------------------------------------------
if [[ -f "$ROOT_DIR/.env" ]]; then
  c_info "Loading environment from .env"
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

# --- configuration (override via env or .env) ---------------------------------
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5433/stock_agent}"
export OPENAI_MODEL="${OPENAI_MODEL:-gpt-4.1-mini}"
export OPENAI_TEMPERATURE="${OPENAI_TEMPERATURE:-0.1}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
export BACKEND_ORIGIN="${BACKEND_ORIGIN:-http://${BACKEND_HOST}:${BACKEND_PORT}}"

MODE="${1:-all}"
PIDS=()

cleanup() {
  c_warn "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  c_info "Postgres container is left running. Stop it with: docker compose down"
}
trap cleanup INT TERM

# --- helpers ------------------------------------------------------------------
start_postgres() {
  if ! command -v docker >/dev/null 2>&1; then
    c_err "docker not found. Install Docker or point DATABASE_URL at your own Postgres."
    exit 1
  fi
  c_info "Starting PostgreSQL (docker compose up -d postgres)..."
  docker compose up -d postgres >/dev/null

  c_info "Waiting for PostgreSQL to accept connections..."
  for _ in $(seq 1 30); do
    if docker exec stock-agent-postgres pg_isready -U postgres -d stock_agent >/dev/null 2>&1; then
      c_ok "PostgreSQL is ready."
      return 0
    fi
    sleep 1
  done
  c_err "PostgreSQL did not become ready in time."
  exit 1
}

run_migrations() {
  c_info "Applying database migrations (alembic upgrade head)..."
  alembic upgrade head
  c_ok "Migrations applied."
}

start_backend() {
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    c_warn "OPENAI_API_KEY not set — final verdicts will use deterministic heuristic synthesis."
  else
    c_ok "OPENAI_API_KEY detected — final verdicts will use OpenAI (${OPENAI_MODEL})."
  fi
  c_info "Starting FastAPI backend on http://${BACKEND_HOST}:${BACKEND_PORT} ..."
  uvicorn backend.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload &
  PIDS+=("$!")
}

start_frontend() {
  if ! command -v npm >/dev/null 2>&1; then
    c_err "npm not found. Install Node.js to run the frontend."
    exit 1
  fi
  if [[ ! -f frontend/.env.local ]]; then
    c_info "Creating frontend/.env.local from .env.example"
    cp frontend/.env.example frontend/.env.local
  fi
  if [[ ! -d frontend/node_modules ]]; then
    c_info "Installing frontend dependencies (npm install)..."
    (cd frontend && npm install)
  fi
  c_info "Starting Next.js frontend on http://localhost:3000 ..."
  (cd frontend && npm run dev) &
  PIDS+=("$!")
}

# --- orchestrate --------------------------------------------------------------
case "$MODE" in
  all)
    start_postgres
    run_migrations
    start_backend
    start_frontend
    ;;
  backend)
    start_postgres
    run_migrations
    start_backend
    ;;
  frontend)
    start_frontend
    ;;
  *)
    c_err "Unknown mode '$MODE'. Use: all | backend | frontend"
    exit 1
    ;;
esac

echo
c_ok "Up. Open the app at: http://localhost:3000"
c_info "Backend API:    ${BACKEND_ORIGIN}"
c_info "API docs:       ${BACKEND_ORIGIN}/docs"
c_info "Press Ctrl+C to stop."
echo

wait
