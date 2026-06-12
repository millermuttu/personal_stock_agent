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

    is_financial = _is_financial_sector(snapshot.features.sector, snapshot.features.industry)

    if is_financial:
        # Banks/NBFCs/insurers are structurally leveraged and do not report
        # meaningful free cash flow, so judge them on profitability, returns and
        # growth rather than D/E and FCF (which would falsely flag them "weak").
        company_quality, quality_score = _financial_quality(revenue_growth, profit_margin, roe)
        valuation = _valuation(pe_ratio, financial=True)
        risks = _financial_risks(roe, profit_margin, pe_ratio)
    else:
        company_quality, quality_score = _generic_quality(
            revenue_growth, profit_margin, de_ratio, roe, fcf
        )
        valuation = _valuation(pe_ratio, financial=False)
        risks = _generic_risks(de_ratio, fcf, pe_ratio)

    if company_quality == "strong" and valuation != "overvalued":
        signal = "buy"
    elif company_quality == "weak":
        signal = "sell"
    else:
        signal = "hold"

    # Continuous score in [-1, +1]: quality (0-5 scale mapped to [-1,1]) plus a
    # valuation adjustment.
    quality_component = (quality_score - 2.5) / 2.5
    valuation_adj = {
        "undervalued": 0.30,
        "fair": 0.0,
        "overvalued": -0.40,
        "unclear": 0.0,
    }.get(valuation, 0.0)
    fundamental_score = round(max(-1.0, min(1.0, quality_component * 0.7 + valuation_adj)), 4)

    return build_agent_report(
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        agent_name=AGENT_NAME,
        ticker=ticker,
        timeframe=timeframe,
        as_of=snapshot.as_of,
        status=AgentStatus.SUCCESS,
        confidence=0.7,
        summary=(
            f"Fundamental view is {company_quality} with {valuation} valuation"
            f"{f' ({snapshot.features.sector} scoring)' if is_financial else ''}."
        ),
        key_points=[
            f"Revenue growth={revenue_growth}, margin={profit_margin}, ROE={roe}",
            (
                f"P/E={pe_ratio} (financial-sector scoring: D/E & FCF excluded)"
                if is_financial
                else f"Debt/Equity={de_ratio}, P/E={pe_ratio}, FCF={fcf}"
            ),
        ],
        signals={
            "revenue_growth": revenue_growth,
            "profit_margin": profit_margin,
            "de_ratio": de_ratio,
            "roe": roe,
            "pe_ratio": pe_ratio,
            "fcf": fcf,
            "is_financial": is_financial,
            "quality_score": quality_score,
        },
        result={
            "company_quality": company_quality,
            "valuation": valuation,
            "investment_signal": signal,
            "score": fundamental_score,
            "fundamental_risks": risks,
            "sector": snapshot.features.sector,
            "scoring_model": "financial" if is_financial else "generic",
        },
    )


FINANCIAL_KEYWORDS = (
    "financial",
    "bank",
    "insurance",
    "capital markets",
    "nbfc",
    "asset management",
)


def _is_financial_sector(sector: str | None, industry: str | None) -> bool:
    text = f"{sector or ''} {industry or ''}".lower()
    return any(keyword in text for keyword in FINANCIAL_KEYWORDS)


def _bucket(score: int) -> str:
    if score >= 4:
        return "strong"
    if score >= 2:
        return "moderate"
    return "weak"


def _generic_quality(
    revenue_growth: float,
    profit_margin: float,
    de_ratio: float,
    roe: float,
    fcf: float,
) -> tuple[str, int]:
    score = 0
    if revenue_growth > 0.1:
        score += 1
    if profit_margin > 0.15:
        score += 1
    if de_ratio < 1.2:
        score += 1
    if roe > 0.12:
        score += 1
    if fcf > 0:
        score += 1
    return _bucket(score), score


def _financial_quality(revenue_growth: float, profit_margin: float, roe: float) -> tuple[str, int]:
    # Five profitability/return/growth criteria, replacing the D/E and FCF checks
    # that do not apply to leveraged financial businesses.
    score = 0
    if revenue_growth > 0.08:
        score += 1
    if profit_margin > 0.18:
        score += 1
    if roe > 0.12:
        score += 1
    if roe > 0.16:  # strong return-on-equity tier
        score += 1
    if profit_margin > 0.26:  # strong profitability tier
        score += 1
    return _bucket(score), score


def _valuation(pe_ratio: float, *, financial: bool) -> str:
    if pe_ratio <= 0:
        return "unclear"
    if financial:
        # Banks/NBFCs typically trade at lower multiples than the broad market.
        if pe_ratio < 14:
            return "undervalued"
        if pe_ratio > 28:
            return "overvalued"
        return "fair"
    if pe_ratio < 15:
        return "undervalued"
    if pe_ratio > 35:
        return "overvalued"
    return "fair"


def _generic_risks(de_ratio: float, fcf: float, pe_ratio: float) -> list[str]:
    risks = []
    if de_ratio > 1.5:
        risks.append("high_balance_sheet_leverage")
    if fcf < 0:
        risks.append("negative_free_cash_flow")
    if pe_ratio > 40:
        risks.append("stretched_valuation_multiple")
    return risks


def _financial_risks(roe: float, profit_margin: float, pe_ratio: float) -> list[str]:
    risks = []
    if roe < 0.08:
        risks.append("weak_return_on_equity")
    if profit_margin < 0.10:
        risks.append("thin_profitability")
    if pe_ratio > 30:
        risks.append("stretched_valuation_multiple")
    return risks

