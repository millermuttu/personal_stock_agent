import asyncio

from backend.models.schemas import Timeframe, utc_now
from backend.services.providers.fundamentals import FundamentalsFetchResult
from backend.services.providers.market_data import MarketDataFetchResult
from backend.services.providers.news_sentiment import (
    NewsSentimentFetchResult,
    _derive_sentiment_signals,
)
from backend.services.snapshot_builder import SnapshotBuilder


class StubMarketDataProvider:
    name = "stub_market_data"

    def __init__(self, beta_points: int = 260) -> None:
        self._points = beta_points

    async def fetch_price_history(self, *, ticker: str, timeframe: Timeframe):
        closes = [round(100 + index * 0.5, 2) for index in range(self._points)]
        return MarketDataFetchResult(
            provider_name=self.name,
            fetched_at=utc_now(),
            closes=closes,
        )


class StubFundamentalsProvider:
    name = "stub_fundamentals"

    def __init__(self, beta: float | None = 1.2) -> None:
        self._beta = beta

    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe):
        return FundamentalsFetchResult(
            provider_name=self.name,
            fetched_at=utc_now(),
            metrics={
                "revenue_growth": 0.12,
                "profit_margin": 0.21,
                "de_ratio": 0.8,
                "roe": 0.18,
                "pe_ratio": 24.0,
                "fcf": 9.5,
            },
            beta=self._beta,
        )


class StubNewsProvider:
    name = "stub_news"

    async def fetch_news_sentiment(self, *, ticker: str, timeframe: Timeframe):
        headlines = [
            f"{ticker} raises guidance after stronger demand outlook",
            f"{ticker} expands partnership with enterprise customer",
        ]
        return NewsSentimentFetchResult(
            provider_name=self.name,
            fetched_at=utc_now(),
            headlines=headlines,
            sentiment_signals=_derive_sentiment_signals(headlines),
        )


def _build(builder: SnapshotBuilder):
    return asyncio.run(builder.build("NVDA", Timeframe.SHORT))


def test_snapshot_builder_normalizes_provider_data():
    builder = SnapshotBuilder(
        market_data_provider=StubMarketDataProvider(),
        fundamentals_provider=StubFundamentalsProvider(),
        news_provider=StubNewsProvider(),
    )
    snapshot = _build(builder)

    provider_names = {provider.name for provider in snapshot.providers}
    assert provider_names == {"stub_market_data", "stub_fundamentals", "stub_news"}
    assert len(snapshot.features.price_history) >= 30
    assert len(snapshot.features.news_items) >= 1
    assert snapshot.features.technical_indicators["ma20"] > 0
    assert "pe_ratio" in snapshot.features.fundamental_metrics
    assert "headline_sentiment_score" in snapshot.features.sentiment_signals


def test_snapshot_builder_uses_real_beta_from_fundamentals():
    builder = SnapshotBuilder(
        market_data_provider=StubMarketDataProvider(),
        fundamentals_provider=StubFundamentalsProvider(beta=1.65),
        news_provider=StubNewsProvider(),
    )
    snapshot = _build(builder)

    assert snapshot.features.risk_metrics["beta"] == 1.65
    assert "risk_beta_unavailable" not in snapshot.data_quality_flags


def test_snapshot_builder_flags_missing_beta():
    builder = SnapshotBuilder(
        market_data_provider=StubMarketDataProvider(),
        fundamentals_provider=StubFundamentalsProvider(beta=None),
        news_provider=StubNewsProvider(),
    )
    snapshot = _build(builder)

    assert snapshot.features.risk_metrics["beta"] == 1.0
    assert "risk_beta_unavailable" in snapshot.data_quality_flags
