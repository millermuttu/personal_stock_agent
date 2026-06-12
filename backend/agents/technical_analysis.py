from __future__ import annotations

from backend.agents.common import build_agent_report
from backend.models.schemas import AgentReportEnvelope, AgentStatus, DataSnapshot, Timeframe


AGENT_NAME = "technical_analysis"


async def run(
    *,
    run_id: str,
    ticker: str,
    timeframe: Timeframe,
    snapshot: DataSnapshot,
) -> AgentReportEnvelope:
    indicators = snapshot.features.technical_indicators
    required_keys = {"rsi", "macd_signal", "ma20", "ma50", "ma200", "bollinger_position", "volatility"}
    if not required_keys.issubset(indicators.keys()):
        return build_agent_report(
            run_id=run_id,
            snapshot_id=snapshot.snapshot_id,
            agent_name=AGENT_NAME,
            ticker=ticker,
            timeframe=timeframe,
            as_of=snapshot.as_of,
            status=AgentStatus.INSUFFICIENT_DATA,
            confidence=0.0,
            summary="Missing technical indicators in snapshot.",
            key_points=["Unable to compute complete technical view from available features."],
            signals=indicators,
            result={
                "trend": "unclear",
                "trade_signal": "no_recommendation",
                "entry_zone": "",
                "risk_factors": ["incomplete_indicator_set"],
            },
            errors=["missing_required_technical_indicators"],
        )

    rsi = float(indicators["rsi"])
    macd_signal = float(indicators["macd_signal"])
    ma20 = float(indicators["ma20"])
    ma50 = float(indicators["ma50"])
    ma200 = float(indicators["ma200"])
    volatility = float(indicators["volatility"])

    bullish_count = 0
    bearish_count = 0

    if macd_signal > 0:
        bullish_count += 1
    else:
        bearish_count += 1

    if ma20 > ma50:
        bullish_count += 1
    else:
        bearish_count += 1

    if ma50 > ma200:
        bullish_count += 1
    else:
        bearish_count += 1

    if rsi < 30:
        bullish_count += 1
    elif rsi > 70:
        bearish_count += 1

    if bullish_count > bearish_count:
        trend = "bullish"
        trade_signal = "buy"
    elif bearish_count > bullish_count:
        trend = "bearish"
        trade_signal = "sell"
    else:
        trend = "neutral"
        trade_signal = "hold"

    risk_factors = []
    if volatility > 0.5:
        risk_factors.append("elevated_short_term_volatility")
    if rsi > 75:
        risk_factors.append("overbought_condition")
    if rsi < 25:
        risk_factors.append("oversold_condition")

    rsi_zone = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
    if ma20 > ma50 > ma200:
        ma_stack = "bullish stack (MA20>MA50>MA200)"
    elif ma20 < ma50 < ma200:
        ma_stack = "bearish stack (MA20<MA50<MA200)"
    else:
        ma_stack = "mixed/transitioning MA stack"
    macd_dir = "positive" if macd_signal > 0 else "negative"

    # Continuous directional score in [-1, +1]: MA trend (±0.70), MACD magnitude
    # relative to price (±0.30), with a small RSI mean-reversion nudge.
    score = 0.35 if ma20 > ma50 else -0.35
    score += 0.35 if ma50 > ma200 else -0.35
    macd_rel = (macd_signal / ma20) if ma20 else 0.0
    score += max(-0.30, min(0.30, macd_rel * 15))
    if rsi < 30:
        score += 0.15
    elif rsi > 70:
        score -= 0.15
    technical_score = round(max(-1.0, min(1.0, score)), 4)

    return build_agent_report(
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        agent_name=AGENT_NAME,
        ticker=ticker,
        timeframe=timeframe,
        as_of=snapshot.as_of,
        status=AgentStatus.SUCCESS,
        confidence=0.68,
        summary=(
            f"Technical posture is {trend} with a {trade_signal} bias: {ma_stack}, "
            f"MACD {macd_dir}, RSI {rsi} ({rsi_zone})."
        ),
        key_points=[
            f"Trend {trend}: {ma_stack}; MACD {macd_dir} ({macd_signal})",
            f"RSI {rsi} ({rsi_zone}); annualized volatility {volatility}",
            f"MA20={ma20}, MA50={ma50}, MA200={ma200}",
            f"Bullish factors={bullish_count} vs bearish factors={bearish_count}",
        ],
        signals={
            "rsi": rsi,
            "macd_signal": macd_signal,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "volatility": volatility,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
        },
        result={
            "trend": trend,
            "trade_signal": trade_signal,
            "score": technical_score,
            "entry_zone": f"{round(ma20 * 0.98, 2)} - {round(ma20 * 1.02, 2)}",
            "risk_factors": risk_factors,
        },
    )

