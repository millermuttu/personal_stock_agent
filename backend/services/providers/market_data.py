from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from backend.models.schemas import Timeframe, utc_now


class MarketDataProviderError(Exception):
    pass


@dataclass
class MarketDataFetchResult:
    provider_name: str
    fetched_at: datetime
    closes: list[float]
    quality_flags: list[str] = field(default_factory=list)


class MarketDataProvider(Protocol):
    async def fetch_price_history(self, *, ticker: str, timeframe: Timeframe) -> MarketDataFetchResult:
        ...


class YahooFinanceMarketDataProvider:
    provider_name = "yahoo_finance"

    def __init__(self, timeout_seconds: float = 20.0, max_attempts: int = 3) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max(1, max_attempts)

    async def fetch_price_history(self, *, ticker: str, timeframe: Timeframe) -> MarketDataFetchResult:
        period = self._period_for_timeframe(timeframe)
        last_exc: Exception | None = None
        closes: list[float] = []
        for _ in range(self._max_attempts):
            try:
                closes = await asyncio.to_thread(self._fetch_sync, ticker, period, self._timeout_seconds)
                if len(closes) < 30:
                    raise MarketDataProviderError(
                        f"insufficient close history from yahoo: {len(closes)} points"
                    )
                break
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc

        if len(closes) < 30:
            if last_exc is None:
                raise MarketDataProviderError("yahoo market data fetch failed")
            raise MarketDataProviderError(str(last_exc)) from last_exc

        return MarketDataFetchResult(
            provider_name=self.provider_name,
            fetched_at=utc_now(),
            closes=closes,
        )

    @staticmethod
    def _period_for_timeframe(timeframe: Timeframe) -> str:
        if timeframe == Timeframe.SHORT:
            return "3mo"
        if timeframe == Timeframe.MEDIUM:
            return "6mo"
        return "1y"

    @staticmethod
    def _fetch_sync(ticker: str, period: str, timeout_seconds: float) -> list[float]:
        try:
            import yfinance as yf
        except Exception as exc:  # pylint: disable=broad-except
            raise MarketDataProviderError("yfinance package not installed") from exc

        history = yf.download(
            tickers=ticker,
            period=period,
            interval="1d",
            progress=False,
            threads=False,
            auto_adjust=False,
            timeout=timeout_seconds,
        )
        if history is None or getattr(history, "empty", True):
            raise MarketDataProviderError("empty yahoo history response")

        return YahooFinanceMarketDataProvider._extract_closes(history)

    @staticmethod
    def _extract_closes(history) -> list[float]:
        try:
            closes_raw = history["Close"]
        except Exception as exc:  # pylint: disable=broad-except
            raise MarketDataProviderError("missing close prices in yahoo history") from exc

        # Depending on yfinance/pandas versions, selecting "Close" can produce
        # either a Series or a single/multi-column DataFrame.
        if hasattr(closes_raw, "ndim") and getattr(closes_raw, "ndim", 1) > 1:
            if getattr(closes_raw, "empty", True):
                raise MarketDataProviderError("no close prices in yahoo history")
            closes_raw = closes_raw.iloc[:, 0]

        if hasattr(closes_raw, "dropna"):
            closes_raw = closes_raw.dropna()

        values = closes_raw.tolist() if hasattr(closes_raw, "tolist") else list(closes_raw)

        # Defensive flattening in case values arrive as rows/tuples.
        if values and isinstance(values[0], (list, tuple)):
            values = [item[0] for item in values if item]

        closes: list[float] = []
        for value in values:
            try:
                closes.append(float(value))
            except Exception:  # pylint: disable=broad-except
                continue

        if not closes:
            raise MarketDataProviderError("no usable close prices in yahoo history")
        return closes


def calculate_volatility(closes: list[float]) -> float:
    if len(closes) < 2:
        return 0.2
    returns = []
    for prev, current in zip(closes[:-1], closes[1:]):
        if prev <= 0 or current <= 0:
            continue
        returns.append(math.log(current / prev))
    if len(returns) < 2:
        return 0.2
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return round((variance ** 0.5) * (252 ** 0.5), 4)


def calculate_max_drawdown(closes: list[float]) -> float:
    if not closes:
        return -0.25
    peak = closes[0]
    max_dd = 0.0
    for price in closes:
        if price > peak:
            peak = price
        drawdown = (price - peak) / peak
        if drawdown < max_dd:
            max_dd = drawdown
    return round(max_dd, 4)
