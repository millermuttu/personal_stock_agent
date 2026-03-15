from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    ticker: str = Field(min_length=1, max_length=10)
    timeframe: Timeframe

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class ProviderManifest(BaseModel):
    name: str
    fetched_at: datetime


class SnapshotFeatures(BaseModel):
    price_history: list[float] = Field(default_factory=list)
    technical_indicators: dict[str, float] = Field(default_factory=dict)
    fundamental_metrics: dict[str, float] = Field(default_factory=dict)
    news_items: list[str] = Field(default_factory=list)
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
    agent_reports: dict[str, AgentReportEnvelope | None] = Field(default_factory=dict)
    final_report: FinalVerdictReport | None = None
    error_summary: str | None = None


class StockSearchResult(BaseModel):
    ticker: str
    name: str
    sector: str


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

