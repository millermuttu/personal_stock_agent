from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Indian exchange suffixes used by Yahoo Finance (NSE = .NS, BSE = .BO).
INDIAN_EXCHANGE_SUFFIXES = (".NS", ".BO")
DEFAULT_INDIAN_SUFFIX = ".NS"


def normalize_indian_ticker(value: str) -> str:
    """Normalize a user-entered symbol to a Yahoo Indian-exchange ticker.

    Bare symbols are routed to NSE (``.NS``); symbols that already carry an
    NSE/BSE suffix are preserved as-is.
    """
    normalized = value.strip().upper()
    if normalized.endswith(INDIAN_EXCHANGE_SUFFIXES):
        return normalized
    return f"{normalized}{DEFAULT_INDIAN_SUFFIX}"


class Timeframe(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class TargetType(str, Enum):
    STOCK = "stock"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class AgentStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    INSUFFICIENT_DATA = "insufficient_data"


class FinalVerdict(str, Enum):
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    NO_RECOMMENDATION = "no_recommendation"


class FinalSynthesisSource(str, Enum):
    LLM = "llm"
    HEURISTIC = "heuristic"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class RecommendationConstraint(str, Enum):
    NONE = "none"
    CAUTION = "caution"
    BLOCK = "block"


class AnalysisRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    timeframe: Timeframe

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return normalize_indian_ticker(value)


class ProviderManifest(BaseModel):
    name: str
    fetched_at: datetime


class NewsArticle(BaseModel):
    title: str
    url: str | None = None
    source: str | None = None
    published_at: str | None = None


class SnapshotFeatures(BaseModel):
    price_history: list[float] = Field(default_factory=list)
    technical_indicators: dict[str, float] = Field(default_factory=dict)
    fundamental_metrics: dict[str, float] = Field(default_factory=dict)
    sector: str | None = None
    industry: str | None = None
    news_items: list[str] = Field(default_factory=list)
    news_articles: list[NewsArticle] = Field(default_factory=list)
    sentiment_signals: dict[str, float] = Field(default_factory=dict)
    risk_metrics: dict[str, float] = Field(default_factory=dict)


class DataSnapshot(BaseModel):
    snapshot_id: str
    target_id: str
    as_of: datetime
    providers: list[ProviderManifest] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)
    features: SnapshotFeatures


class AgentReportEnvelope(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    snapshot_id: str
    agent_name: str
    target_type: TargetType = TargetType.STOCK
    target_id: str
    timeframe: Timeframe
    as_of: datetime
    status: AgentStatus
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    key_points: list[str] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)


class FinalVerdictReport(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    target_type: TargetType = TargetType.STOCK
    target_id: str
    timeframe: Timeframe
    as_of: datetime
    status: RunStatus
    final_verdict: FinalVerdict
    synthesis_source: FinalSynthesisSource = FinalSynthesisSource.HEURISTIC
    model_version: str | None = None
    prompt_version: str | None = None
    llm_fallback_reason: str | None = None
    # Net directional conviction in [-1, +1] (negative bearish, positive bullish).
    bias_score: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    decision_factors: list[str] = Field(default_factory=list)
    conflicting_signals: list[str] = Field(default_factory=list)
    required_followups: list[str] = Field(default_factory=list)
    summary: str


class CreateAnalysisResponse(BaseModel):
    run_id: str
    status: RunStatus


class AnalysisRunResponse(BaseModel):
    run_id: str
    target_type: TargetType
    target_id: str
    timeframe: Timeframe
    status: RunStatus
    created_at: datetime
    completed_at: datetime | None = None
    snapshot: DataSnapshot | None = None
    selected_agents: list[str] = Field(default_factory=list)
    agent_reports: dict[str, AgentReportEnvelope | None] = Field(default_factory=dict)
    final_report: FinalVerdictReport | None = None
    error_summary: str | None = None


class AnalysisRunSummary(BaseModel):
    run_id: str
    target_id: str
    timeframe: Timeframe
    status: RunStatus
    created_at: datetime
    completed_at: datetime | None = None
    final_verdict: FinalVerdict | None = None
    risk_level: RiskLevel | None = None
    confidence: float | None = None


class StockSearchResult(BaseModel):
    ticker: str
    name: str
    sector: str


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class OpenInvestmentRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    amount: float = Field(gt=0)
    run_id: str | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return normalize_indian_ticker(value)


class PaperPosition(BaseModel):
    id: str
    run_id: str | None = None
    ticker: str
    verdict: FinalVerdict | None = None
    status: PositionStatus
    entry_price: float
    quantity: float
    invested_amount: float
    opened_at: datetime
    closed_at: datetime | None = None
    close_price: float | None = None
    # Live valuation (current price for open positions; close price for closed).
    current_price: float | None = None
    current_value: float | None = None
    pnl: float = 0.0
    pnl_pct: float = 0.0


class WalletSummary(BaseModel):
    starting_cash: float
    cash: float
    invested: float
    holdings_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float


class InvestmentsResponse(BaseModel):
    wallet: WalletSummary
    positions: list[PaperPosition] = Field(default_factory=list)


class PriceRange(str, Enum):
    ONE_DAY = "1D"
    FIVE_DAY = "5D"
    ONE_WEEK = "1W"
    ONE_MONTH = "1M"
    THREE_MONTH = "3M"
    SIX_MONTH = "6M"


class CandleBar(BaseModel):
    # UNIX epoch seconds (UTC); compatible with lightweight-charts UTCTimestamp.
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class PriceHistoryResponse(BaseModel):
    ticker: str
    range: PriceRange
    interval: str
    bars: list[CandleBar] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class AnalysisRunRecord(BaseModel):
    run_id: str
    target_type: TargetType
    target_id: str
    timeframe: Timeframe
    status: RunStatus
    created_at: datetime
    completed_at: datetime | None = None
    snapshot: DataSnapshot | None = None
    selected_agents: list[str] = Field(default_factory=list)
    agent_reports: dict[str, AgentReportEnvelope | None] = Field(default_factory=dict)
    final_report: FinalVerdictReport | None = None
    error_summary: str | None = None
    attempt_log: dict[str, int] = Field(default_factory=dict)
