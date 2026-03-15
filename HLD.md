# Personal Stock Market Analyst

## High-Level Design

This document is a concise summary of the V1 system.

Detailed contracts, schemas, and policies live in `system_arch.md`.

---

## 1. V1 Scope

V1 supports stock analysis only.

User input:

* `ticker`
* `timeframe = short | medium | long`

Out of scope:

* sector analysis
* portfolio analysis
* trading automation

---

## 2. Product Goal

Generate a structured stock-analysis run by combining multiple analytical agents over a single normalized market-data snapshot.

The system should be:

* repeatable
* auditable
* safe under partial failure
* easy to extend later

---

## 3. High-Level Flow

User -> Frontend -> FastAPI -> Analysis Service -> LangGraph Orchestrator -> Agents -> Final Verdict -> PostgreSQL -> Frontend

Execution summary:

1. user submits ticker and timeframe
2. API creates an analysis run
3. backend fetches market, fundamentals, news, and risk inputs once
4. snapshot builder normalizes data and computes features
5. orchestrator runs the selected agents in parallel
6. final reasoning step produces a verdict or `no_recommendation`
7. results are stored and returned through the API

---

## 4. Core Components

### Frontend

* Next.js
* Tailwind CSS
* search, run status, dashboard, charts, agent report views

### API Layer

* FastAPI
* request validation
* run creation
* result retrieval

### Orchestration Layer

* LangGraph
* agent selection
* parallel execution
* aggregation
* verdict guardrails

### Data Layer

* centralized fetching
* normalization
* feature computation
* caching

### Storage Layer

* PostgreSQL
* run records
* agent reports
* shared data snapshots

---

## 5. V1 Agent Set

Agents:

* `technical_analysis`
* `fundamental_analysis`
* `sentiment_analysis`
* `risk_analysis`

Timeframe mapping:

* short: technical, risk, optional sentiment
* medium: technical, fundamental, risk, optional sentiment
* long: fundamental, risk, optional sentiment

All agents consume the same snapshot for a given run.

---

## 6. Key Architecture Decisions

### Stock-first domain model

Sector analysis is deferred to V2 so V1 contracts remain consistent.

### Canonical schemas

Every agent returns the same report envelope, and the final verdict uses one shared response contract.

### Shared snapshot model

Agents do not fetch their own data in V1. A centralized pipeline builds one normalized snapshot and passes it to all agents.

### Agent write isolation

Each agent can write only to its own report entry for a run. Agents cannot overwrite or mutate other agent reports.

### Safe fallback behavior

If required inputs or required agents fail, the system returns `no_recommendation` instead of forcing `buy` or `sell`.

---

## 7. API Summary

Primary endpoints:

* `POST /analysis`
* `GET /analysis/{run_id}`
* `GET /stocks/search`
* `GET /health`

The API should use asynchronous run creation rather than holding open a long synchronous request.

---

## 8. Persistence Summary

Main tables:

* `stocks`
* `analysis_runs`
* `agent_reports`
* `data_snapshots`

Stored metadata should include:

* `as_of`
* provider information
* prompt version
* model version
* run status
* errors

---

## 9. Non-Functional Requirements

The architecture should support:

* observability
* reproducibility
* backtesting readiness
* source timestamp visibility
* graceful degradation under provider or LLM failure

---

## 10. Source of Truth

For implementation details, use `system_arch.md`.

This file should stay short and stable.

---

# End of High-Level Design
