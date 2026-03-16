import type {
  AgentReportEnvelope,
  AnalysisRunResponse,
  CreateAnalysisResponse,
  DataSnapshot,
  FinalVerdict,
  FinalSynthesisSource,
  FinalVerdictReport,
  RiskLevel,
  RunStatus,
  StockSearchResult,
  Timeframe,
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
      sentiment_signals: asStringNumberMap(features.sentiment_signals),
      risk_metrics: asStringNumberMap(features.risk_metrics),
    },
  };
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
    agent_reports: normalizeAgentReports(source.agent_reports),
    final_report: normalizeFinalReport(source.final_report),
    error_summary: asNullableString(source.error_summary),
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
