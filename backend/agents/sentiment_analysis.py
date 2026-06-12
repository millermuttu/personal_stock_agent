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
    provider_score = snapshot.features.sentiment_signals.get("headline_sentiment_score")
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
                "provider_sentiment_score": provider_score,
            },
            errors=["missing_news_data"],
        )

    positive_hits = 0
    negative_hits = 0
    for headline in headlines:
        normalized = headline.lower()
        positive_hits += sum(1 for token in POSITIVE_WORDS if token in normalized)
        negative_hits += sum(1 for token in NEGATIVE_WORDS if token in normalized)

    lexical_sentiment = _sentiment_from_hit_counts(positive_hits=positive_hits, negative_hits=negative_hits)
    provider_sentiment = _sentiment_from_provider_score(provider_score)
    sentiment = _combine_sentiment(lexical_sentiment=lexical_sentiment, provider_sentiment=provider_sentiment)

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
    if sentiment in {"negative", "mixed"}:
        risks.append("headline_tone_negative")
    if "market_uncertainty" in themes:
        risks.append("macro_headline_volatility")

    key_points = [
        f"Positive token hits={positive_hits}, negative token hits={negative_hits}",
        f"Dominant themes: {', '.join(themes)}",
    ]
    if provider_score is not None:
        key_points.append(f"Provider sentiment score={provider_score:.3f}")

    signals = {
        "headline_count": len(headlines),
        "positive_hits": positive_hits,
        "negative_hits": negative_hits,
    }
    if provider_score is not None:
        signals["provider_sentiment_score"] = provider_score

    # Continuous score in [-1, +1]: prefer the provider's headline score, else
    # fall back to the lexical hit balance.
    if provider_score is not None:
        sentiment_score = max(-1.0, min(1.0, float(provider_score)))
    else:
        total_hits = positive_hits + negative_hits
        sentiment_score = 0.0 if total_hits == 0 else (positive_hits - negative_hits) / total_hits
    sentiment_score = round(sentiment_score, 4)

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
        key_points=key_points,
        signals=signals,
        result={
            "sentiment": sentiment,
            "score": sentiment_score,
            "key_themes": themes,
            "sentiment_risks": risks,
            "provider_sentiment_score": provider_score,
        },
        citations=headlines[:3],
    )


def _sentiment_from_hit_counts(*, positive_hits: int, negative_hits: int) -> str:
    if positive_hits > negative_hits:
        return "positive"
    if negative_hits > positive_hits:
        return "negative"
    return "neutral"


def _sentiment_from_provider_score(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score >= 0.2:
        return "positive"
    if score <= -0.2:
        return "negative"
    return "neutral"


def _combine_sentiment(*, lexical_sentiment: str, provider_sentiment: str) -> str:
    if lexical_sentiment == provider_sentiment:
        return lexical_sentiment
    if lexical_sentiment == "neutral":
        return provider_sentiment
    if provider_sentiment == "neutral":
        return lexical_sentiment
    return "mixed"
