import type {
  AgentReportEnvelope,
  AnalysisRunResponse,
  AnalysisRunSummary,
  CandleBar,
  CreateAnalysisResponse,
  DataSnapshot,
  FinalVerdict,
  FinalSynthesisSource,
  FinalVerdictReport,
  InvestmentsResponse,
  NewsArticle,
  PaperPosition,
  PriceHistoryResponse,
  PriceRange,
  RiskLevel,
  RunStatus,
  StockSearchResult,
  Timeframe,
  WalletSummary,
} from "./types";

const TIMEFRAMES = new Set<Timeframe>(["short", "medium", "long"]);
const RUN_STATUSES = new Set<RunStatus>([
  "queued",
  "running",
  "completed",
  "partial_success",
  "failed",
]);
const FINAL_VERDICTS = new Set<FinalVerdict>(["buy", "hold", "sell", "no_recommendation"]);
const SYNTHESIS_SOURCES = new Set<FinalSynthesisSource>(["llm", "heuristic"]);
const RISK_LEVELS = new Set<RiskLevel>(["low", "medium", "high", "unknown"]);

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}

function asNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is number => typeof item === "number" && Number.isFinite(item));
}

function asStringNumberMap(value: unknown): Record<string, number> {
  const source = asRecord(value);
  const output: Record<string, number> = {};
  for (const [key, raw] of Object.entries(source)) {
    if (typeof raw === "number" && Number.isFinite(raw)) {
      output[key] = raw;
    }
  }
  return output;
}

function asUnknownMap(value: unknown): Record<string, unknown> {
  return asRecord(value);
}

function asTimeframe(value: unknown): Timeframe {
  return TIMEFRAMES.has(value as Timeframe) ? (value as Timeframe) : "short";
}

function asRunStatus(value: unknown): RunStatus {
  return RUN_STATUSES.has(value as RunStatus) ? (value as RunStatus) : "queued";
}

function asFinalVerdict(value: unknown): FinalVerdict {
  return FINAL_VERDICTS.has(value as FinalVerdict) ? (value as FinalVerdict) : "no_recommendation";
}

function asRiskLevel(value: unknown): RiskLevel {
  return RISK_LEVELS.has(value as RiskLevel) ? (value as RiskLevel) : "unknown";
}

function asSynthesisSource(value: unknown): FinalSynthesisSource {
  return SYNTHESIS_SOURCES.has(value as FinalSynthesisSource)
    ? (value as FinalSynthesisSource)
    : "heuristic";
}

function normalizeSnapshot(value: unknown): DataSnapshot | null {
  if (value === null || value === undefined) {
    return null;
  }
  const source = asRecord(value);
  const features = asRecord(source.features);

  return {
    snapshot_id: asString(source.snapshot_id),
    target_id: asString(source.target_id),
    as_of: asString(source.as_of),
    providers: Array.isArray(source.providers)
      ? source.providers
          .map((item) => {
            const provider = asRecord(item);
            return {
              name: asString(provider.name),
              fetched_at: asString(provider.fetched_at),
            };
          })
          .filter((provider) => provider.name.length > 0)
      : [],
    data_quality_flags: asStringArray(source.data_quality_flags),
    features: {
      price_history: asNumberArray(features.price_history),
      technical_indicators: asStringNumberMap(features.technical_indicators),
      fundamental_metrics: asStringNumberMap(features.fundamental_metrics),
      news_items: asStringArray(features.news_items),
      news_articles: normalizeNewsArticles(features.news_articles),
      sentiment_signals: asStringNumberMap(features.sentiment_signals),
      risk_metrics: asStringNumberMap(features.risk_metrics),
    },
  };
}

function normalizeNewsArticles(value: unknown): NewsArticle[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      const source = asRecord(item);
      return {
        title: asString(source.title),
        url: asNullableString(source.url),
        source: asNullableString(source.source),
        published_at: asNullableString(source.published_at),
      };
    })
    .filter((article) => article.title.length > 0);
}

function normalizeAgentReport(value: unknown): AgentReportEnvelope | null {
  if (value === null || value === undefined) {
    return null;
  }
  const source = asRecord(value);
  return {
    run_id: asString(source.run_id),
    snapshot_id: asString(source.snapshot_id),
    agent_name: asString(source.agent_name),
    status: asString(source.status, "unknown"),
    confidence: asNumber(source.confidence, 0),
    summary: asString(source.summary),
    key_points: asStringArray(source.key_points),
    signals: asUnknownMap(source.signals),
    citations: asStringArray(source.citations),
    errors: asStringArray(source.errors),
    result: asUnknownMap(source.result),
  };
}

function normalizeAgentReports(value: unknown): Record<string, AgentReportEnvelope | null> {
  const source = asRecord(value);
  const output: Record<string, AgentReportEnvelope | null> = {};
  for (const [agentName, report] of Object.entries(source)) {
    output[agentName] = normalizeAgentReport(report);
  }
  return output;
}

function normalizeFinalReport(value: unknown): FinalVerdictReport | null {
  if (value === null || value === undefined) {
    return null;
  }
  const source = asRecord(value);
  return {
    run_id: asString(source.run_id),
    final_verdict: asFinalVerdict(source.final_verdict),
    synthesis_source: asSynthesisSource(source.synthesis_source),
    model_version: asNullableString(source.model_version),
    prompt_version: asNullableString(source.prompt_version),
    llm_fallback_reason: asNullableString(source.llm_fallback_reason),
    bias_score: typeof source.bias_score === "number" ? source.bias_score : null,
    confidence: asNumber(source.confidence, 0),
    risk_level: asRiskLevel(source.risk_level),
    summary: asString(source.summary),
    decision_factors: asStringArray(source.decision_factors),
    conflicting_signals: asStringArray(source.conflicting_signals),
    required_followups: asStringArray(source.required_followups),
  };
}

export function normalizeCreateAnalysisResponse(value: unknown): CreateAnalysisResponse {
  const source = asRecord(value);
  const runId = asString(source.run_id);
  if (!runId) {
    throw new Error("Backend returned invalid create-analysis response (missing run_id).");
  }
  return {
    run_id: runId,
    status: asRunStatus(source.status),
  };
}

export function normalizeAnalysisRun(value: unknown): AnalysisRunResponse {
  const source = asRecord(value);
  return {
    run_id: asString(source.run_id),
    target_id: asString(source.target_id),
    timeframe: asTimeframe(source.timeframe),
    status: asRunStatus(source.status),
    created_at: asString(source.created_at),
    completed_at: asNullableString(source.completed_at),
    snapshot: normalizeSnapshot(source.snapshot),
    selected_agents: asStringArray(source.selected_agents),
    agent_reports: normalizeAgentReports(source.agent_reports),
    final_report: normalizeFinalReport(source.final_report),
    error_summary: asNullableString(source.error_summary),
  };
}

const PRICE_RANGES = new Set<PriceRange>(["1D", "5D", "1W", "1M", "3M", "6M"]);

function asPriceRange(value: unknown): PriceRange {
  return PRICE_RANGES.has(value as PriceRange) ? (value as PriceRange) : "1M";
}

function normalizeCandle(value: unknown): CandleBar | null {
  const source = asRecord(value);
  const time = asNumber(source.time, NaN);
  const open = asNumber(source.open, NaN);
  const high = asNumber(source.high, NaN);
  const low = asNumber(source.low, NaN);
  const close = asNumber(source.close, NaN);
  if ([time, open, high, low, close].some((n) => !Number.isFinite(n))) {
    return null;
  }
  const volumeRaw = source.volume;
  return {
    time,
    open,
    high,
    low,
    close,
    volume: typeof volumeRaw === "number" && Number.isFinite(volumeRaw) ? volumeRaw : null,
  };
}

export function normalizePriceHistory(value: unknown): PriceHistoryResponse {
  const source = asRecord(value);
  const bars = Array.isArray(source.bars)
    ? source.bars.map(normalizeCandle).filter((bar): bar is CandleBar => bar !== null)
    : [];
  return {
    ticker: asString(source.ticker),
    range: asPriceRange(source.range),
    interval: asString(source.interval),
    bars,
  };
}

export function normalizeRunSummaries(value: unknown): AnalysisRunSummary[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      const source = asRecord(item);
      return {
        run_id: asString(source.run_id),
        target_id: asString(source.target_id),
        timeframe: asTimeframe(source.timeframe),
        status: asRunStatus(source.status),
        created_at: asString(source.created_at),
        completed_at: asNullableString(source.completed_at),
        final_verdict: FINAL_VERDICTS.has(source.final_verdict as FinalVerdict)
          ? (source.final_verdict as FinalVerdict)
          : null,
        risk_level: RISK_LEVELS.has(source.risk_level as RiskLevel)
          ? (source.risk_level as RiskLevel)
          : null,
        confidence:
          typeof source.confidence === "number" && Number.isFinite(source.confidence)
            ? source.confidence
            : null,
      };
    })
    .filter((summary) => summary.run_id.length > 0);
}

function normalizePaperPosition(value: unknown): PaperPosition | null {
  const source = asRecord(value);
  const id = asString(source.id);
  if (!id) {
    return null;
  }
  return {
    id,
    run_id: asNullableString(source.run_id),
    ticker: asString(source.ticker),
    verdict: FINAL_VERDICTS.has(source.verdict as FinalVerdict)
      ? (source.verdict as FinalVerdict)
      : null,
    status: source.status === "closed" ? "closed" : "open",
    entry_price: asNumber(source.entry_price),
    quantity: asNumber(source.quantity),
    invested_amount: asNumber(source.invested_amount),
    opened_at: asString(source.opened_at),
    closed_at: asNullableString(source.closed_at),
    close_price: typeof source.close_price === "number" ? source.close_price : null,
    current_price: typeof source.current_price === "number" ? source.current_price : null,
    current_value: typeof source.current_value === "number" ? source.current_value : null,
    pnl: asNumber(source.pnl),
    pnl_pct: asNumber(source.pnl_pct),
  };
}

export function normalizePaperPositionResponse(value: unknown): PaperPosition {
  const position = normalizePaperPosition(value);
  if (!position) {
    throw new Error("Backend returned an invalid investment payload.");
  }
  return position;
}

function normalizeWallet(value: unknown): WalletSummary {
  const source = asRecord(value);
  return {
    starting_cash: asNumber(source.starting_cash),
    cash: asNumber(source.cash),
    invested: asNumber(source.invested),
    holdings_value: asNumber(source.holdings_value),
    unrealized_pnl: asNumber(source.unrealized_pnl),
    realized_pnl: asNumber(source.realized_pnl),
    total_value: asNumber(source.total_value),
    total_pnl: asNumber(source.total_pnl),
    total_pnl_pct: asNumber(source.total_pnl_pct),
  };
}

export function normalizeInvestments(value: unknown): InvestmentsResponse {
  const source = asRecord(value);
  const positions = Array.isArray(source.positions)
    ? source.positions
        .map(normalizePaperPosition)
        .filter((position): position is PaperPosition => position !== null)
    : [];
  return {
    wallet: normalizeWallet(source.wallet),
    positions,
  };
}

export function normalizeStockSearchResults(value: unknown): StockSearchResult[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      const source = asRecord(item);
      return {
        ticker: asString(source.ticker),
        name: asString(source.name),
        sector: asString(source.sector),
      };
    })
    .filter((item) => item.ticker.length > 0);
}
