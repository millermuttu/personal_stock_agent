from __future__ import annotations

from backend.models.schemas import AgentStatus, Timeframe


REQUIRED_AGENTS_BY_TIMEFRAME: dict[Timeframe, list[str]] = {
    Timeframe.SHORT: ["technical_analysis", "risk_analysis"],
    Timeframe.MEDIUM: ["technical_analysis", "fundamental_analysis", "risk_analysis"],
    Timeframe.LONG: ["fundamental_analysis", "risk_analysis"],
}

OPTIONAL_AGENTS_BY_TIMEFRAME: dict[Timeframe, list[str]] = {
    Timeframe.SHORT: ["sentiment_analysis"],
    Timeframe.MEDIUM: ["sentiment_analysis"],
    Timeframe.LONG: ["sentiment_analysis"],
}


def selected_agents_for_timeframe(timeframe: Timeframe) -> list[str]:
    return REQUIRED_AGENTS_BY_TIMEFRAME[timeframe] + OPTIONAL_AGENTS_BY_TIMEFRAME[timeframe]


def is_success_like(status: AgentStatus) -> bool:
    return status in {AgentStatus.SUCCESS, AgentStatus.PARTIAL_SUCCESS}

