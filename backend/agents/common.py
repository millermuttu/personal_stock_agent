from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.models.schemas import AgentReportEnvelope, AgentStatus, Timeframe


def build_agent_report(
    *,
    run_id: str,
    snapshot_id: str,
    agent_name: str,
    ticker: str,
    timeframe: Timeframe,
    as_of: datetime,
    status: AgentStatus,
    confidence: float,
    summary: str,
    key_points: list[str],
    signals: dict[str, Any],
    result: dict[str, Any],
    citations: list[str] | None = None,
    errors: list[str] | None = None,
) -> AgentReportEnvelope:
    return AgentReportEnvelope(
        run_id=run_id,
        snapshot_id=snapshot_id,
        agent_name=agent_name,
        target_id=ticker,
        timeframe=timeframe,
        as_of=as_of,
        status=status,
        confidence=confidence,
        summary=summary,
        key_points=key_points,
        signals=signals,
        citations=citations or [],
        errors=errors or [],
        result=result,
    )

