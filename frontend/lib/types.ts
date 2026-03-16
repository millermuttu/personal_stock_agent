export type Timeframe = "short" | "medium" | "long";

export type RunStatus = "queued" | "running" | "completed" | "partial_success" | "failed";

export type FinalVerdict = "buy" | "hold" | "sell" | "no_recommendation";
export type FinalSynthesisSource = "llm" | "heuristic";

export type RiskLevel = "low" | "medium" | "high" | "unknown";

export interface StockSearchResult {
  ticker: string;
  name: string;
  sector: string;
}

export interface ProviderManifest {
  name: string;
  fetched_at: string;
}

export interface SnapshotFeatures {
  price_history: number[];
  technical_indicators: Record<string, number>;
  fundamental_metrics: Record<string, number>;
  news_items: string[];
  sentiment_signals: Record<string, number>;
  risk_metrics: Record<string, number>;
}

export interface DataSnapshot {
  snapshot_id: string;
  target_id: string;
  as_of: string;
  providers: ProviderManifest[];
  data_quality_flags: string[];
  features: SnapshotFeatures;
}

export interface AgentReportEnvelope {
  run_id: string;
  snapshot_id: string;
  agent_name: string;
  status: string;
  confidence: number;
  summary: string;
  key_points: string[];
  signals: Record<string, unknown>;
  citations: string[];
  errors: string[];
  result: Record<string, unknown>;
}

export interface FinalVerdictReport {
  run_id: string;
  final_verdict: FinalVerdict;
  synthesis_source: FinalSynthesisSource;
  model_version: string | null;
  prompt_version: string | null;
  llm_fallback_reason: string | null;
  confidence: number;
  risk_level: RiskLevel;
  summary: string;
  decision_factors: string[];
  conflicting_signals: string[];
  required_followups: string[];
}

export interface CreateAnalysisResponse {
  run_id: string;
  status: RunStatus;
}

export interface AnalysisRunResponse {
  run_id: string;
  target_id: string;
  timeframe: Timeframe;
  status: RunStatus;
  created_at: string;
  completed_at: string | null;
  snapshot: DataSnapshot | null;
  agent_reports: Record<string, AgentReportEnvelope | null>;
  final_report: FinalVerdictReport | null;
  error_summary: string | null;
}
