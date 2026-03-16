from __future__ import annotations

import hashlib
import random

from backend.models.schemas import DataSnapshot, ProviderManifest, SnapshotFeatures, Timeframe
from backend.services.providers.fundamentals import (
    FundamentalsProvider,
    MockFundamentalsProvider,
)
from backend.services.providers.market_data import (
    MarketDataProvider,
    MockMarketDataProvider,
    calculate_max_drawdown,
    calculate_volatility,
)
from backend.services.providers.news_sentiment import (
    MockNewsSentimentProvider,
    NewsSentimentProvider,
)


class SnapshotBuilder:
    """Builds normalized snapshots from provider data with fallback-safe defaults."""

    def __init__(
        self,
        market_data_provider: MarketDataProvider | None = None,
        fundamentals_provider: FundamentalsProvider | None = None,
        news_provider: NewsSentimentProvider | None = None,
    ) -> None:
        self._market_data_provider = market_data_provider or MockMarketDataProvider()
        self._fundamentals_provider = fundamentals_provider or MockFundamentalsProvider()
        self._news_provider = news_provider or MockNewsSentimentProvider()

    async def build(self, ticker: str, timeframe: Timeframe) -> DataSnapshot:
        seed = self._seed_from_inputs(ticker=ticker, timeframe=timeframe.value)
        rng = random.Random(seed)
        market_data = await self._market_data_provider.fetch_price_history(
            ticker=ticker,
            timeframe=timeframe,
        )
        fundamentals_data = await self._fundamentals_provider.fetch_metrics(
            ticker=ticker,
            timeframe=timeframe,
        )
        news_data = await self._news_provider.fetch_news_sentiment(
            ticker=ticker,
            timeframe=timeframe,
        )
        as_of = max(market_data.fetched_at, fundamentals_data.fetched_at, news_data.fetched_at)
        price_history = market_data.closes

        technical_indicators, technical_flags = self._technical_indicators(price_history)
        quality_flags: list[str] = (
            list(market_data.quality_flags)
            + technical_flags
            + list(fundamentals_data.quality_flags)
            + list(news_data.quality_flags)
        )

        volatility = calculate_volatility(price_history)
        max_drawdown = calculate_max_drawdown(price_history)

        risk_metrics = {
            "volatility": volatility,
            "beta": round(rng.uniform(0.6, 2.1), 2),
            "max_drawdown": max_drawdown,
        }

        snapshot_id = f"snap_{hashlib.sha1(f'{ticker}:{as_of.isoformat()}'.encode('utf-8')).hexdigest()[:12]}"
        return DataSnapshot(
            snapshot_id=snapshot_id,
            target_id=ticker,
            as_of=as_of,
            providers=[
                ProviderManifest(name=market_data.provider_name, fetched_at=market_data.fetched_at),
                ProviderManifest(
                    name=fundamentals_data.provider_name,
                    fetched_at=fundamentals_data.fetched_at,
                ),
                ProviderManifest(name=news_data.provider_name, fetched_at=news_data.fetched_at),
            ],
            data_quality_flags=quality_flags,
            features=SnapshotFeatures(
                price_history=price_history,
                technical_indicators=technical_indicators,
                fundamental_metrics=fundamentals_data.metrics,
                news_items=news_data.headlines,
                sentiment_signals=news_data.sentiment_signals,
                risk_metrics=risk_metrics,
            ),
        )

    @staticmethod
    def _seed_from_inputs(*, ticker: str, timeframe: str) -> int:
        digest = hashlib.sha256(f"{ticker}:{timeframe}".encode("utf-8")).hexdigest()
        return int(digest[:10], 16)

    @staticmethod
    def _technical_indicators(price_history: list[float]) -> tuple[dict[str, float], list[str]]:
        flags: list[str] = []
        if len(price_history) < 30:
            flags.append("short_price_history_window")

        ma20 = SnapshotBuilder._moving_average(price_history, 20)
        ma50 = SnapshotBuilder._moving_average(price_history, 50)
        ma200 = SnapshotBuilder._moving_average(price_history, 200)
        if len(price_history) < 200:
            flags.append("ma200_approximation")

        rsi = SnapshotBuilder._rsi(price_history, 14)
        macd_signal = SnapshotBuilder._macd_signal(price_history)
        bollinger_position = SnapshotBuilder._bollinger_position(price_history, 20)
        volatility = calculate_volatility(price_history)

        return (
            {
                "rsi": rsi,
                "macd_signal": macd_signal,
                "ma20": ma20,
                "ma50": ma50,
                "ma200": ma200,
                "bollinger_position": bollinger_position,
                "volatility": volatility,
            },
            flags,
        )

    @staticmethod
    def _moving_average(values: list[float], window: int) -> float:
        if not values:
            return 0.0
        window_slice = values[-window:] if len(values) >= window else values
        return round(sum(window_slice) / len(window_slice), 4)

    @staticmethod
    def _rsi(values: list[float], period: int) -> float:
        if len(values) <= period:
            return 50.0
        changes = [current - prev for prev, current in zip(values[:-1], values[1:])]
        gains = [max(change, 0.0) for change in changes]
        losses = [abs(min(change, 0.0)) for change in changes]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 4)

    @staticmethod
    def _ema(values: list[float], span: int) -> float:
        if not values:
            return 0.0
        multiplier = 2 / (span + 1)
        ema = values[0]
        for value in values[1:]:
            ema = (value - ema) * multiplier + ema
        return ema

    @staticmethod
    def _macd_signal(values: list[float]) -> float:
        if len(values) < 26:
            return 0.0
        ema12 = SnapshotBuilder._ema(values, 12)
        ema26 = SnapshotBuilder._ema(values, 26)
        return round(ema12 - ema26, 4)

    @staticmethod
    def _bollinger_position(values: list[float], window: int) -> float:
        if len(values) < 2:
            return 0.5
        window_slice = values[-window:] if len(values) >= window else values
        mean = sum(window_slice) / len(window_slice)
        variance = sum((value - mean) ** 2 for value in window_slice) / len(window_slice)
        std_dev = variance**0.5
        if std_dev == 0:
            return 0.5
        lower = mean - (2 * std_dev)
        upper = mean + (2 * std_dev)
        latest = values[-1]
        position = (latest - lower) / (upper - lower)
        return round(max(0.0, min(1.0, position)), 4)
