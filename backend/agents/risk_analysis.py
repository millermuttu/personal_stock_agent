from __future__ import annotations

from backend.agents.common import build_agent_report
from backend.models.schemas import (
    AgentReportEnvelope,
    AgentStatus,
    DataSnapshot,
    RecommendationConstraint,
    RiskLevel,
    Timeframe,
)


AGENT_NAME = "risk_analysis"


async def run(
    *,
    run_id: str,
    ticker: str,
    timeframe: Timeframe,
    snapshot: DataSnapshot,
) -> AgentReportEnvelope:
    risk_metrics = snapshot.features.risk_metrics
    required_keys = {"volatility", "beta", "max_drawdown"}
    if not required_keys.issubset(risk_metrics.keys()):
        return build_agent_report(
            run_id=run_id,
            snapshot_id=snapshot.snapshot_id,
            agent_name=AGENT_NAME,
            ticker=ticker,
            timeframe=timeframe,
            as_of=snapshot.as_of,
            status=AgentStatus.INSUFFICIENT_DATA,
            confidence=0.0,
            summary="Missing risk metrics in snapshot.",
            key_points=["Risk profile cannot be assessed without core volatility inputs."],
            signals=risk_metrics,
            result={
                "risk_level": RiskLevel.UNKNOWN.value,
                "key_risks": ["incomplete_risk_inputs"],
                "recommendation_constraint": RecommendationConstraint.BLOCK.value,
            },
            errors=["missing_required_risk_metrics"],
        )

    volatility = float(risk_metrics["volatility"])
    beta = float(risk_metrics["beta"])
    max_drawdown = float(risk_metrics["max_drawdown"])

    high_risk_signals = 0
    if volatility > 0.5:
        high_risk_signals += 1
    if beta > 1.5:
        high_risk_signals += 1
    if max_drawdown < -0.5:
        high_risk_signals += 1

    if high_risk_signals >= 2:
        risk_level = RiskLevel.HIGH
        constraint = RecommendationConstraint.BLOCK
    elif high_risk_signals == 1:
        risk_level = RiskLevel.MEDIUM
        constraint = RecommendationConstraint.CAUTION
    else:
        risk_level = RiskLevel.LOW
        constraint = RecommendationConstraint.NONE

    key_risks = []
    if volatility > 0.5:
        key_risks.append("high_realized_volatility")
    if beta > 1.5:
        key_risks.append("high_market_beta")
    if max_drawdown < -0.5:
        key_risks.append("deep_historical_drawdown")
    if "low_news_coverage" in snapshot.data_quality_flags:
        key_risks.append("low_news_signal_quality")

    return build_agent_report(
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        agent_name=AGENT_NAME,
        ticker=ticker,
        timeframe=timeframe,
        as_of=snapshot.as_of,
        status=AgentStatus.SUCCESS,
        confidence=0.74,
        summary=f"Risk level assessed as {risk_level.value}.",
        key_points=[
            f"Volatility={volatility}, beta={beta}, max_drawdown={max_drawdown}",
            f"Recommendation constraint={constraint.value}",
        ],
        signals={
            "volatility": volatility,
            "beta": beta,
            "max_drawdown": max_drawdown,
            "data_quality_flags": snapshot.data_quality_flags,
        },
        result={
            "risk_level": risk_level.value,
            "key_risks": key_risks,
            "recommendation_constraint": constraint.value,
        },
    )

