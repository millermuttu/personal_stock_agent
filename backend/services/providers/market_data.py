from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from backend.models.schemas import PriceRange, Timeframe, utc_now


class MarketDataProviderError(Exception):
    pass


@dataclass
class MarketDataFetchResult:
    provider_name: str
    fetched_at: datetime
    closes: list[float]
    quality_flags: list[str] = field(default_factory=list)


@dataclass
class CandleBarResult:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass
class CandleFetchResult:
    provider_name: str
    fetched_at: datetime
    interval: str
    bars: list[CandleBarResult]


# Maps each UI range to a yfinance window + candle interval. ``period`` uses
# yfinance's native period strings; ``days`` uses a start/end window for ranges
# (like 1W) that have no native period string.
RANGE_CONFIG: dict[PriceRange, dict[str, object]] = {
    PriceRange.ONE_DAY: {"period": "1d", "interval": "5m"},
    PriceRange.FIVE_DAY: {"period": "5d", "interval": "15m"},
    PriceRange.ONE_WEEK: {"days": 7, "interval": "60m"},
    PriceRange.ONE_MONTH: {"period": "1mo", "interval": "1d"},
    PriceRange.THREE_MONTH: {"period": "3mo", "interval": "1d"},
    PriceRange.SIX_MONTH: {"period": "6mo", "interval": "1d"},
}


class MarketDataProvider(Protocol):
    async def fetch_price_history(self, *, ticker: str, timeframe: Timeframe) -> MarketDataFetchResult:
        ...

    async def fetch_candles(self, *, ticker: str, price_range: PriceRange) -> CandleFetchResult:
        ...

    async def fetch_current_price(self, *, ticker: str) -> float:
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

    async def fetch_candles(self, *, ticker: str, price_range: PriceRange) -> CandleFetchResult:
        config = RANGE_CONFIG[price_range]
        interval = str(config["interval"])
        last_exc: Exception | None = None
        bars: list[CandleBarResult] = []
        for _ in range(self._max_attempts):
            try:
                bars = await asyncio.wait_for(
                    asyncio.to_thread(self._fetch_candles_sync, ticker, config),
                    timeout=self._timeout_seconds,
                )
                if bars:
                    break
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc

        if not bars:
            if last_exc is None:
                raise MarketDataProviderError(f"no candle data for {ticker} ({price_range.value})")
            raise MarketDataProviderError(str(last_exc)) from last_exc

        return CandleFetchResult(
            provider_name=self.provider_name,
            fetched_at=utc_now(),
            interval=interval,
            bars=bars,
        )

    async def fetch_current_price(self, *, ticker: str) -> float:
        """Latest traded price, derived from the most recent intraday candle."""
        last_exc: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                bars = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._fetch_candles_sync,
                        ticker,
                        {"period": "1d", "interval": "5m"},
                    ),
                    timeout=self._timeout_seconds,
                )
                if bars:
                    return bars[-1].close
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc

        # Fall back to the daily close window if intraday data is unavailable.
        try:
            bars = await asyncio.wait_for(
                asyncio.to_thread(
                    self._fetch_candles_sync,
                    ticker,
                    {"period": "5d", "interval": "1d"},
                ),
                timeout=self._timeout_seconds,
            )
            if bars:
                return bars[-1].close
        except Exception as exc:  # pylint: disable=broad-except
            last_exc = exc

        raise MarketDataProviderError(
            str(last_exc) if last_exc else f"no current price for {ticker}"
        )

    @staticmethod
    def _fetch_candles_sync(ticker: str, config: dict[str, object]) -> list[CandleBarResult]:
        try:
            import yfinance as yf
        except Exception as exc:  # pylint: disable=broad-except
            raise MarketDataProviderError("yfinance package not installed") from exc

        interval = str(config["interval"])
        download_kwargs: dict[str, object] = {
            "tickers": ticker,
            "interval": interval,
            "progress": False,
            "threads": False,
            "auto_adjust": False,
        }
        if "period" in config:
            download_kwargs["period"] = str(config["period"])
        else:
            from datetime import timedelta

            days = int(config["days"])  # type: ignore[arg-type]
            end = utc_now()
            start = end - timedelta(days=days)
            download_kwargs["start"] = start.strftime("%Y-%m-%d")
            download_kwargs["end"] = (end + timedelta(days=1)).strftime("%Y-%m-%d")

        history = yf.download(**download_kwargs)
        if history is None or getattr(history, "empty", True):
            raise MarketDataProviderError("empty yahoo candle response")

        return YahooFinanceMarketDataProvider._extract_bars(history)

    @staticmethod
    def _extract_bars(history) -> list[CandleBarResult]:
        # yfinance can return a MultiIndex on columns (field, ticker) for a
        # single symbol; flatten to the field level so column lookups work.
        columns = getattr(history, "columns", None)
        if columns is not None and getattr(columns, "nlevels", 1) > 1:
            try:
                history = history.droplevel(1, axis=1)
            except Exception:  # pylint: disable=broad-except
                history = history.copy()
                history.columns = [col[0] for col in columns]

        required = ("Open", "High", "Low", "Close")
        if not all(field_name in history.columns for field_name in required):
            raise MarketDataProviderError("missing OHLC columns in yahoo history")

        bars: list[CandleBarResult] = []
        has_volume = "Volume" in history.columns
        for index, row in history.iterrows():
            try:
                open_v = float(row["Open"])
                high_v = float(row["High"])
                low_v = float(row["Low"])
                close_v = float(row["Close"])
            except Exception:  # pylint: disable=broad-except
                continue
            if any(not math.isfinite(value) for value in (open_v, high_v, low_v, close_v)):
                continue

            try:
                epoch_seconds = int(index.timestamp())
            except Exception:  # pylint: disable=broad-except
                continue

            volume: float | None = None
            if has_volume:
                try:
                    raw_volume = float(row["Volume"])
                    if math.isfinite(raw_volume):
                        volume = raw_volume
                except Exception:  # pylint: disable=broad-except
                    volume = None

            bars.append(
                CandleBarResult(
                    time=epoch_seconds,
                    open=round(open_v, 4),
                    high=round(high_v, 4),
                    low=round(low_v, 4),
                    close=round(close_v, 4),
                    volume=volume,
                )
            )

        if not bars:
            raise MarketDataProviderError("no usable OHLC bars in yahoo history")
        return bars

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
