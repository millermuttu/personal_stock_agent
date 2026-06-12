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

export interface NewsArticle {
  title: string;
  url: string | null;
  source: string | null;
  published_at: string | null;
}

export interface SnapshotFeatures {
  price_history: number[];
  technical_indicators: Record<string, number>;
  fundamental_metrics: Record<string, number>;
  news_items: string[];
  news_articles: NewsArticle[];
  sentiment_signals: Record<string, number>;
  risk_metrics: Record<string, number>;
}

export type PriceRange = "1D" | "5D" | "1W" | "1M" | "3M" | "6M";

export interface CandleBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface PriceHistoryResponse {
  ticker: string;
  range: PriceRange;
  interval: string;
  bars: CandleBar[];
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
  bias_score: number | null;
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

export type PositionStatus = "open" | "closed";

export interface PaperPosition {
  id: string;
  run_id: string | null;
  ticker: string;
  verdict: FinalVerdict | null;
  status: PositionStatus;
  entry_price: number;
  quantity: number;
  invested_amount: number;
  opened_at: string;
  closed_at: string | null;
  close_price: number | null;
  current_price: number | null;
  current_value: number | null;
  pnl: number;
  pnl_pct: number;
}

export interface WalletSummary {
  starting_cash: number;
  cash: number;
  invested: number;
  holdings_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
}

export interface InvestmentsResponse {
  wallet: WalletSummary;
  positions: PaperPosition[];
}

export interface AnalysisRunSummary {
  run_id: string;
  target_id: string;
  timeframe: Timeframe;
  status: RunStatus;
  created_at: string;
  completed_at: string | null;
  final_verdict: FinalVerdict | null;
  risk_level: RiskLevel | null;
  confidence: number | null;
}

export interface AnalysisRunResponse {
  run_id: string;
  target_id: string;
  timeframe: Timeframe;
  status: RunStatus;
  created_at: string;
  completed_at: string | null;
  snapshot: DataSnapshot | null;
  selected_agents: string[];
  agent_reports: Record<string, AgentReportEnvelope | null>;
  final_report: FinalVerdictReport | null;
  error_summary: string | null;
}
