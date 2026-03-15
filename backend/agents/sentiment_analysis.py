from __future__ import annotations

from backend.agents.common import build_agent_report
from backend.models.schemas import AgentReportEnvelope, AgentStatus, DataSnapshot, Timeframe


AGENT_NAME = "sentiment_analysis"

POSITIVE_WORDS = ("strong", "expands", "partnership", "roadmap", "higher", "improving")
NEGATIVE_WORDS = ("debate", "volatility", "concern", "downgrade", "risk")


async def run(
    *,
    run_id: str,
    ticker: str,
    timeframe: Timeframe,
    snapshot: DataSnapshot,
) -> AgentReportEnvelope:
    headlines = snapshot.features.news_items
    if not headlines:
        return build_agent_report(
            run_id=run_id,
            snapshot_id=snapshot.snapshot_id,
            agent_name=AGENT_NAME,
            ticker=ticker,
            timeframe=timeframe,
            as_of=snapshot.as_of,
            status=AgentStatus.INSUFFICIENT_DATA,
            confidence=0.0,
            summary="No headlines available for sentiment evaluation.",
            key_points=["Sentiment signal is unavailable without recent headline coverage."],
            signals={"headline_count": 0},
            result={
                "sentiment": "unclear",
                "key_themes": [],
                "sentiment_risks": ["no_recent_headlines"],
            },
            errors=["missing_news_data"],
        )

    positive_hits = 0
    negative_hits = 0
    for headline in headlines:
        normalized = headline.lower()
        positive_hits += sum(1 for token in POSITIVE_WORDS if token in normalized)
        negative_hits += sum(1 for token in NEGATIVE_WORDS if token in normalized)

    if positive_hits > negative_hits:
        sentiment = "positive"
    elif negative_hits > positive_hits:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    themes = []
    if any("partnership" in item.lower() for item in headlines):
        themes.append("business_expansion")
    if any("earnings" in item.lower() for item in headlines):
        themes.append("earnings_reaction")
    if any("volatility" in item.lower() for item in headlines):
        themes.append("market_uncertainty")
    if not themes:
        themes.append("general_coverage")

    risks = []
    if sentiment == "negative":
        risks.append("headline_tone_negative")
    if "market_uncertainty" in themes:
        risks.append("macro_headline_volatility")

    return build_agent_report(
        run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        agent_name=AGENT_NAME,
        ticker=ticker,
        timeframe=timeframe,
        as_of=snapshot.as_of,
        status=AgentStatus.SUCCESS,
        confidence=0.6,
        summary=f"Sentiment is {sentiment} based on {len(headlines)} recent headlines.",
        key_points=[
            f"Positive token hits={positive_hits}, negative token hits={negative_hits}",
            f"Dominant themes: {', '.join(themes)}",
        ],
        signals={
            "headline_count": len(headlines),
            "positive_hits": positive_hits,
            "negative_hits": negative_hits,
        },
        result={
            "sentiment": sentiment,
            "key_themes": themes,
            "sentiment_risks": risks,
        },
        citations=headlines[:3],
    )

