from __future__ import annotations

from backend.agents.common import build_agent_report
from backend.models.schemas import AgentReportEnvelope, AgentStatus, DataSnapshot, Timeframe


AGENT_NAME = "fundamental_analysis"


async def run(
    *,
    run_id: str,
    ticker: str,
    timeframe: Timeframe,
    snapshot: DataSnapshot,
) -> AgentReportEnvelope:
    metrics = snapshot.features.fundamental_metrics
    required_keys = {"revenue_growth", "profit_margin", "de_ratio", "roe", "pe_ratio", "fcf"}
    if not required_keys.issubset(metrics.keys()):
        return build_agent_report(
            run_id=run_id,
            snapshot_id=snapshot.snapshot_id,
            agent_name=AGENT_NAME,
            ticker=ticker,
            timeframe=timeframe,
            as_of=snapshot.as_of,
            status=AgentStatus.INSUFFICIENT_DATA,
            confidence=0.0,
            summary="Missing fundamental metrics in snapshot.",
            key_points=["Unable to compute complete fundamental view from available features."],
            signals=metrics,
            result={
                "company_quality": "unclear",
                "valuation": "unclear",
                "investment_signal": "no_recommendation",
                "fundamental_risks": ["incomplete_fundamental_set"],
            },
            errors=["missing_required_fundamental_metrics"],
        )

    revenue_growth = float(metrics["revenue_growth"])
    profit_margin = float(metrics["profit_margin"])
    de_ratio = float(metrics["de_ratio"])
    roe = float(metrics["roe"])
    pe_ratio = float(metrics["pe_ratio"])
    fcf = float(metrics["fcf"])

    quality_score = 0
    if revenue_growth > 0.1:
        quality_score += 1
    if profit_margin > 0.15:
        quality_score += 1
    if de_ratio < 1.2:
        quality_score += 1
    if roe > 0.12:
        quality_score += 1
    if fcf > 0:
        quality_score += 1

    if quality_score >= 4:
        company_quality = "strong"
    elif quality_score >= 2:
        company_quality = "moderate"
    else:
        company_quality = "weak"

    if pe_ratio < 15:
        valuation = "undervalued"
    elif pe_ratio > 35:
        valuation = "overvalued"
    else:
        valuation = "fair"

    if company_quality == "strong" and valuation != "overvalued":
        signal = "buy"
    elif company_quality == "weak":
        signal = "sell"
    else:
        signal = "hold"

    risks = []
    if de_ratio > 1.5:
        risks.append("high_balance_sheet_leverage")
    if fcf < 0:
        risks.append("negative_free_cash_flow")
    if pe_ratio > 40:
        risks.append("stretched_valuation_multiple")

    return build_agent_report(
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        agent_name=AGENT_NAME,
        ticker=ticker,
        timeframe=timeframe,
        as_of=snapshot.as_of,
        status=AgentStatus.SUCCESS,
        confidence=0.7,
        summary=f"Fundamental view is {company_quality} with {valuation} valuation.",
        key_points=[
            f"Revenue growth={revenue_growth}, margin={profit_margin}, ROE={roe}",
            f"Debt/Equity={de_ratio}, P/E={pe_ratio}, FCF={fcf}",
        ],
        signals={
            "revenue_growth": revenue_growth,
            "profit_margin": profit_margin,
            "de_ratio": de_ratio,
            "roe": roe,
            "pe_ratio": pe_ratio,
            "fcf": fcf,
        },
        result={
            "company_quality": company_quality,
            "valuation": valuation,
            "investment_signal": signal,
            "fundamental_risks": risks,
        },
    )

