import asyncio

from backend.models.schemas import Timeframe
from backend.services.providers.fundamentals import (
    HybridFundamentalsProvider,
    FundamentalsProviderError,
    MockFundamentalsProvider,
)
from backend.services.providers.market_data import (
    HybridMarketDataProvider,
    MarketDataProviderError,
    MockMarketDataProvider,
)
from backend.services.providers.news_sentiment import (
    HybridNewsSentimentProvider,
    MockNewsSentimentProvider,
    NewsSentimentProviderError,
)
from backend.services.snapshot_builder import SnapshotBuilder


def test_snapshot_builder_uses_mock_market_data_provider():
    builder = SnapshotBuilder(
        market_data_provider=MockMarketDataProvider(),
        fundamentals_provider=MockFundamentalsProvider(),
        news_provider=MockNewsSentimentProvider(),
    )
    snapshot = asyncio.run(builder.build("NVDA", Timeframe.SHORT))

    provider_names = {provider.name for provider in snapshot.providers}
    assert "mock_market_data_provider" in provider_names
    assert "mock_fundamentals_provider" in provider_names
    assert "mock_news_provider" in provider_names
    assert len(snapshot.features.price_history) >= 30
    assert len(snapshot.features.news_items) >= 1
    assert snapshot.features.technical_indicators["ma20"] > 0
    assert "pe_ratio" in snapshot.features.fundamental_metrics
    assert "headline_sentiment_score" in snapshot.features.sentiment_signals


def test_snapshot_builder_hybrid_fallback_sets_quality_flags():
    class FailingProvider:
        async def fetch_price_history(self, *, ticker: str, timeframe: Timeframe):
            raise MarketDataProviderError("primary down")

    hybrid = HybridMarketDataProvider(
        primary=FailingProvider(),  # type: ignore[arg-type]
        fallback=MockMarketDataProvider(),
    )
    builder = SnapshotBuilder(market_data_provider=hybrid)

    snapshot = asyncio.run(builder.build("AAPL", Timeframe.MEDIUM))
    assert "market_data_fallback_used" in snapshot.data_quality_flags
    assert any(flag.startswith("market_data_primary_failed:") for flag in snapshot.data_quality_flags)


def test_snapshot_builder_fundamentals_hybrid_fallback_sets_quality_flags():
    class FailingFundamentalsProvider:
        async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe):
            raise FundamentalsProviderError("primary down")

    hybrid = HybridFundamentalsProvider(
        primary=FailingFundamentalsProvider(),  # type: ignore[arg-type]
        fallback=MockFundamentalsProvider(),
    )
    builder = SnapshotBuilder(
        market_data_provider=MockMarketDataProvider(),
        fundamentals_provider=hybrid,
    )

    snapshot = asyncio.run(builder.build("AAPL", Timeframe.MEDIUM))
    assert "fundamentals_fallback_used" in snapshot.data_quality_flags
    assert any(
        flag.startswith("fundamentals_primary_failed:")
        for flag in snapshot.data_quality_flags
    )


def test_snapshot_builder_news_hybrid_fallback_sets_quality_flags():
    class FailingNewsProvider:
        async def fetch_news_sentiment(self, *, ticker: str, timeframe: Timeframe):
            raise NewsSentimentProviderError("primary down")

    hybrid = HybridNewsSentimentProvider(
        primary=FailingNewsProvider(),  # type: ignore[arg-type]
        fallback=MockNewsSentimentProvider(),
    )
    builder = SnapshotBuilder(
        market_data_provider=MockMarketDataProvider(),
        fundamentals_provider=MockFundamentalsProvider(),
        news_provider=hybrid,
    )

    snapshot = asyncio.run(builder.build("AAPL", Timeframe.MEDIUM))
    assert "news_fallback_used" in snapshot.data_quality_flags
    assert any(
        flag.startswith("news_primary_failed:")
        for flag in snapshot.data_quality_flags
    )
