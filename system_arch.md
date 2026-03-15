# Personal Stock Market Analyst

## System Architecture Design

This document is the source of truth for the V1 architecture.

`HLD.md` is a summary view of this design and should not redefine interfaces or schemas.

---

## 1. V1 Scope

V1 is a stock-first analysis system.

Users submit a stock ticker and a timeframe, and the system returns a structured analysis run composed of agent reports plus a final verdict.

Supported inputs:

* `ticker`
* `timeframe = short | medium | long`

Explicitly out of scope for V1:

* sector-level analysis
* portfolio analysis
* automated trading
* reinforcement learning
* brokerage integration

These can be added in later versions once the stock workflow is stable and measurable.

---

## 2. Product Goals

* Generate repeatable stock analysis from a shared market-data snapshot
* Combine multiple analytical perspectives without letting each agent invent its own data
* Return machine-readable outputs that are easy to store, compare, and backtest
* Support partial failure safely
* Keep architecture simple enough for a small V1 team to implement and operate

---

## 3. High-Level Architecture

Logical flow:

User -> Next.js Frontend -> FastAPI API -> Analysis Service -> LangGraph Orchestrator -> Agent Workers -> OpenAI + Market Data Providers -> PostgreSQL -> Frontend

Core layers:

1. Presentation Layer
2. API Layer
3. Analysis and Orchestration Layer
4. Data Pipeline Layer
5. Storage Layer

Design principle:

All agents operate on the same normalized input snapshot for a given run. Agents do not fetch their own market data directly in V1.

---

## 4. Canonical Domain Model

### 4.1 Analysis Target

V1 supports only one target type:

```json
{
  "target_type": "stock",
  "target_id": "NVDA"
}
```

Future versions may introduce:

* `target_type = sector`
* `target_type = portfolio`

Those are intentionally excluded from V1 contracts so the current system stays internally consistent.

### 4.2 Timeframes

```json
{
  "short": "days to weeks",
  "medium": "weeks to months",
  "long": "months to years"
}
```

Timeframe selection affects:

* agent selection
* data lookback windows
* cache TTL expectations
* verdict interpretation

---

## 5. Technology Stack

### Frontend

* Next.js
* Tailwind CSS

Responsibilities:

* ticker search
* timeframe selection
* run-status polling
* analysis dashboard
* agent report rendering
* charts and source/citation display

### Backend API

* FastAPI

Responsibilities:

* validate requests
* create analysis runs
* expose run status and results
* return structured errors

### Orchestration

* LangGraph

Responsibilities:

* build analysis graph
* maintain run state
* run agents in parallel
* aggregate results
* enforce verdict guardrails

### Storage

* PostgreSQL

Responsibilities:

* persist runs
* persist agent outputs
* persist normalized input snapshots
* support auditability and backtesting

### LLM Provider

* OpenAI model configured per environment

Responsibilities:

* interpret computed signals
* synthesize agent reports
* produce final structured verdicts

---

## 6. Request Lifecycle

1. User submits `ticker` and `timeframe`
2. API validates payload and creates `analysis_run`
3. Analysis service fetches provider data once for the run
4. Data pipeline normalizes raw data into a shared snapshot
5. Indicator services compute derived signals
6. Orchestrator selects agents for the timeframe
7. Agents run in parallel using the shared snapshot
8. Aggregator checks agent statuses and required-agent completion
9. Final reasoning step produces a verdict or `no_recommendation`
10. All artifacts are stored in PostgreSQL
11. Frontend polls or fetches the finished run

V1 should be implemented as an asynchronous workflow:

* `POST /analysis` creates a run and returns `run_id`
* `GET /analysis/{run_id}` returns status plus results when available

This avoids long synchronous HTTP requests when providers or LLM calls are slow.

State update rule:

Each agent writes only to its own report slot inside the run state. No agent can edit, replace, or delete another agent's report.

---

## 7. Agent Catalog

V1 agents:

* `technical_analysis`
* `fundamental_analysis`
* `sentiment_analysis`
* `risk_analysis`

### 7.1 Timeframe-to-Agent Mapping

#### Short

Required agents:

* `technical_analysis`
* `risk_analysis`

Optional agents:

* `sentiment_analysis`

#### Medium

Required agents:

* `technical_analysis`
* `fundamental_analysis`
* `risk_analysis`

Optional agents:

* `sentiment_analysis`

#### Long

Required agents:

* `fundamental_analysis`
* `risk_analysis`

Optional agents:

* `sentiment_analysis`

### 7.2 Agent Responsibilities

#### Technical Analysis Agent

Inputs:

* normalized price history
* volume history
* computed technical indicators

Outputs:

* trend assessment
* technical trade posture
* key technical signals

#### Fundamental Analysis Agent

Inputs:

* normalized financial statements
* valuation metrics
* profitability metrics

Outputs:

* business quality assessment
* valuation assessment
* long-horizon investment posture

#### Sentiment Analysis Agent

Inputs:

* curated news articles
* headline timestamps
* source metadata

Outputs:

* current market sentiment
* key themes
* headline-driven risks or tailwinds

#### Risk Analysis Agent

Inputs:

* volatility metrics
* beta
* drawdown history
* concentration or data-quality warnings

Outputs:

* risk level
* downside scenarios
* guardrail signals for the final verdict

---

## 8. Centralized Data Pipeline

V1 uses a shared data pipeline rather than agent-owned fetching.

Pipeline:

Fetch -> Validate -> Normalize -> Compute Features -> Build Snapshot -> Cache -> Send to Agents

Rules:

* market and fundamentals data are fetched once per run
* all agents receive the same `snapshot_id`
* raw provider payloads are stored for reproducibility when practical
* each snapshot includes `as_of`, `fetched_at`, `provider_name`, and `data_quality_flags`

Advantages:

* fewer duplicate provider calls
* fewer inconsistent timestamps across agents
* easier caching
* easier debugging and backtesting

---

## 9. Canonical Contracts

### 9.1 Analysis Request

```json
{
  "ticker": "NVDA",
  "timeframe": "short"
}
```

### 9.2 Analysis Run

```json
{
  "run_id": "run_123",
  "target_type": "stock",
  "target_id": "NVDA",
  "timeframe": "short",
  "status": "queued | running | completed | partial_success | failed",
  "created_at": "2026-03-15T10:00:00Z",
  "completed_at": null
}
```

### 9.3 Shared Snapshot

```json
{
  "snapshot_id": "snap_123",
  "target_id": "NVDA",
  "as_of": "2026-03-15T09:30:00Z",
  "providers": [
    {
      "name": "market_data_provider",
      "fetched_at": "2026-03-15T09:31:00Z"
    }
  ],
  "data_quality_flags": [],
  "features": {
    "price_history": [],
    "technical_indicators": {},
    "fundamental_metrics": {},
    "news_items": [],
    "risk_metrics": {}
  }
}
```

### 9.4 Agent Report Envelope

Every agent must return the same outer schema.

```json
{
  "schema_version": "1.0",
  "run_id": "run_123",
  "snapshot_id": "snap_123",
  "agent_name": "technical_analysis",
  "target_type": "stock",
  "target_id": "NVDA",
  "timeframe": "short",
  "as_of": "2026-03-15T09:30:00Z",
  "status": "success | partial_success | failed | insufficient_data",
  "confidence": 0.76,
  "summary": "Momentum is improving, but resistance remains near recent highs.",
  "key_points": [
    "RSI recovered from oversold levels",
    "Price is above the 20-day moving average"
  ],
  "signals": {},
  "citations": [],
  "errors": [],
  "result": {}
}
```

Agent-specific details belong inside `result`.

Example `result` payloads:

* technical: `trend`, `trade_signal`, `entry_zone`, `risk_factors`
* fundamental: `company_quality`, `valuation`, `investment_signal`
* sentiment: `sentiment`, `key_themes`
* risk: `risk_level`, `key_risks`

### 9.5 Final Verdict Contract

```json
{
  "schema_version": "1.0",
  "run_id": "run_123",
  "target_type": "stock",
  "target_id": "NVDA",
  "timeframe": "short",
  "as_of": "2026-03-15T09:30:00Z",
  "status": "completed | partial_success | failed",
  "final_verdict": "buy | hold | sell | no_recommendation",
  "confidence": 0.72,
  "risk_level": "low | medium | high | unknown",
  "decision_factors": [
    "Technical momentum is positive",
    "Risk remains elevated because volatility is above normal"
  ],
  "conflicting_signals": [],
  "required_followups": [],
  "summary": "Short-term setup is constructive, but risk limits position sizing."
}
```

`no_recommendation` is mandatory when the system lacks enough evidence to issue a safe call.

---

## 10. Orchestration Policy

The final LLM step is a synthesis layer, not a replacement for system rules.

### 10.1 Agent Write Isolation

Orchestrator state should keep reports in a keyed map:

```json
{
  "agent_reports": {
    "technical_analysis": null,
    "fundamental_analysis": null,
    "sentiment_analysis": null,
    "risk_analysis": null
  }
}
```

Merge contract:

* each node may write only to `agent_reports[its_own_agent_name]`
* merge strategy is key-based patch, not full-map replacement
* writes to other keys are rejected and logged as orchestration errors
* aggregator reads all keys but never rewrites per-agent payloads

Retry behavior:

* same agent may retry and replace only its own slot for the same run
* previous attempt metadata should be kept in run logs for auditability

Guardrails:

* required agents must finish with `success` or `partial_success`
* if a required agent returns `failed` or `insufficient_data`, the run cannot return `buy` or `sell`
* stale or low-quality snapshots must downgrade the run to `partial_success` or `no_recommendation`
* the final reasoner may summarize evidence, but it may not invent data that is not in the snapshot or agent reports

Recommended decision policy:

1. Validate run completeness
2. Reject stale or invalid snapshots
3. Evaluate risk agent output before upside claims
4. Detect agent disagreement explicitly
5. Produce a verdict or `no_recommendation`

Failure handling:

* provider fetch failure -> mark snapshot incomplete and retry where reasonable
* optional-agent failure -> continue run as `partial_success`
* required-agent failure -> final verdict becomes `no_recommendation`
* orchestrator or storage failure -> mark run `failed`

---

## 11. API Design

### POST /analysis

Creates a new run.

Request:

```json
{
  "ticker": "NVDA",
  "timeframe": "short"
}
```

Response:

```json
{
  "run_id": "run_123",
  "status": "queued"
}
```

### GET /analysis/{run_id}

Returns:

* run metadata
* final verdict when ready
* agent reports
* errors and status details

### GET /stocks/search

Returns ticker search results for the frontend.

### GET /health

Operational health endpoint for API and worker checks.

---

## 12. Storage Design

### 12.1 Reference Tables

#### stocks

* `ticker` primary key
* `name`
* `exchange`
* `sector`
* `industry`
* `is_active`
* `updated_at`

### 12.2 Run Tables

#### analysis_runs

* `run_id` primary key
* `target_type`
* `target_id`
* `timeframe`
* `status`
* `final_verdict`
* `confidence`
* `risk_level`
* `created_at`
* `completed_at`
* `model_version`
* `prompt_version`
* `request_payload_json`
* `error_summary`

#### agent_reports

* `report_id` primary key
* `run_id` foreign key
* `agent_name`
* `status`
* `as_of`
* `confidence`
* `report_json`
* `error_json`
* `created_at`

Constraints:

* unique key on (`run_id`, `agent_name`) for current report slot isolation
* only the row matching the calling `agent_name` may be updated by that agent worker
* optional: keep historical retries in a separate `agent_report_attempts` table

#### data_snapshots

* `snapshot_id` primary key
* `run_id` foreign key
* `target_id`
* `as_of`
* `provider_manifest_json`
* `quality_flags_json`
* `features_json`
* `raw_inputs_json`
* `created_at`

Why store snapshot data:

* replayability
* debugging
* evaluation
* backtesting

---

## 13. Caching Strategy

Cache by normalized provider data, not by final LLM output alone.

Suggested TTLs:

* intraday price data: minutes
* fundamentals: 1 day
* news: 30 to 60 minutes
* computed indicators: tied to price-snapshot freshness

Cache keys should include:

* provider
* ticker
* timeframe or lookback window
* trading day or `as_of`

---

## 14. Module Structure

```text
project_root/
  backend/
    api/
      routers/
      dependencies/
    orchestrator/
      graph.py
      policies.py
      state.py
    agents/
      technical_analysis.py
      fundamental_analysis.py
      sentiment_analysis.py
      risk_analysis.py
    services/
      analysis_service.py
      market_data_service.py
      fundamentals_service.py
      news_service.py
      snapshot_builder.py
      cache_service.py
    indicators/
      technical_indicators.py
      risk_metrics.py
    llm/
      client.py
      prompts.py
      schemas.py
    db/
      models.py
      repositories.py
  frontend/
    app/
    components/
    lib/
    charts/
    analysis/
```

---

## 15. Observability, Evaluation, and Safety

Architecture must support more than just successful responses.

Track:

* provider latency and failure rates
* LLM latency and token usage
* run duration by timeframe
* agent failure counts
* verdict distribution
* prompt version and model version

Evaluation requirements:

* save enough data to replay historical runs
* compare verdicts against future outcomes offline
* score agents separately from final verdict quality

Safety requirements:

* every response should disclose that it is informational analysis, not guaranteed advice
* system should prefer `no_recommendation` over forced certainty
* source timestamps must be visible in stored artifacts and UI

---

## 16. Future Versions

Potential V2 additions:

* sector analysis as a separate target type
* portfolio analysis
* analyst-performance scoring
* backtesting dashboard
* notification workflows

Future work should extend the canonical contracts instead of creating parallel schemas.

---

## 17. Implementation Priorities

Recommended build order:

1. stock-only request path
2. centralized snapshot builder
3. technical, fundamental, sentiment, and risk agents
4. canonical storage schema
5. orchestrator guardrails
6. frontend run dashboard
7. evaluation and observability hooks

---

# End of System Architecture Design
