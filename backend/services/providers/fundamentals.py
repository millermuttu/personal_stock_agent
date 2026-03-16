from __future__ import annotations

import asyncio
import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from backend.models.schemas import Timeframe, utc_now


class FundamentalsProviderError(Exception):
    pass


@dataclass
class FundamentalsFetchResult:
    provider_name: str
    fetched_at: datetime
    metrics: dict[str, float]
    quality_flags: list[str] = field(default_factory=list)


class FundamentalsProvider(Protocol):
    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe) -> FundamentalsFetchResult:
        ...


class MockFundamentalsProvider:
    provider_name = "mock_fundamentals_provider"

    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe) -> FundamentalsFetchResult:
        seed = self._seed_from_inputs(ticker=ticker, timeframe=timeframe.value)
        rng = random.Random(seed)
        metrics = {
            "revenue_growth": round(rng.uniform(-0.08, 0.35), 3),
            "profit_margin": round(rng.uniform(0.02, 0.4), 3),
            "de_ratio": round(rng.uniform(0.05, 2.2), 2),
            "roe": round(rng.uniform(0.01, 0.42), 3),
            "pe_ratio": round(rng.uniform(8, 52), 2),
            "fcf": round(rng.uniform(-1.5, 12.0), 2),
        }
        return FundamentalsFetchResult(
            provider_name=self.provider_name,
            fetched_at=utc_now(),
            metrics=metrics,
        )

    @staticmethod
    def _seed_from_inputs(*, ticker: str, timeframe: str) -> int:
        digest = hashlib.sha256(f"{ticker}:{timeframe}:fundamentals".encode("utf-8")).hexdigest()
        return int(digest[:10], 16)


class YahooFundamentalsProvider:
    provider_name = "yahoo_fundamentals"

    def __init__(self, timeout_seconds: float = 15.0, max_attempts: int = 2) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max(1, max_attempts)

    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe) -> FundamentalsFetchResult:
        del timeframe
        metrics: dict[str, float] | None = None
        last_exc: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                metrics = await asyncio.wait_for(
                    asyncio.to_thread(self._fetch_sync, ticker),
                    timeout=self._timeout_seconds,
                )
                break
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc

        if metrics is None:
            if last_exc is None:
                raise FundamentalsProviderError("yahoo fundamentals fetch failed")
            raise FundamentalsProviderError(str(last_exc)) from last_exc

        quality_flags = self._quality_flags(metrics)
        return FundamentalsFetchResult(
            provider_name=self.provider_name,
            fetched_at=utc_now(),
            metrics=metrics,
            quality_flags=quality_flags,
        )

    @staticmethod
    def _fetch_sync(ticker: str) -> dict[str, float]:
        try:
            import yfinance as yf
        except Exception as exc:  # pylint: disable=broad-except
            raise FundamentalsProviderError("yfinance package not installed") from exc

        data = yf.Ticker(ticker).info
        if not isinstance(data, dict) or not data:
            raise FundamentalsProviderError("empty yahoo fundamentals response")

        revenue_growth = YahooFundamentalsProvider._to_float(data.get("revenueGrowth"), default=0.0)
        profit_margin = YahooFundamentalsProvider._to_float(data.get("profitMargins"), default=0.0)
        debt_to_equity_raw = YahooFundamentalsProvider._to_float(data.get("debtToEquity"), default=1.0)
        return_on_equity = YahooFundamentalsProvider._to_float(data.get("returnOnEquity"), default=0.0)
        pe_ratio = YahooFundamentalsProvider._to_float(
            data.get("trailingPE") or data.get("forwardPE"),
            default=20.0,
        )
        free_cash_flow = YahooFundamentalsProvider._to_float(data.get("freeCashflow"), default=0.0)

        # Yahoo may return debtToEquity as percentage-style values.
        de_ratio = debt_to_equity_raw / 100 if debt_to_equity_raw > 10 else debt_to_equity_raw

        # Scale free cash flow to billions so it stays close to model expectations.
        fcf_billions = free_cash_flow / 1_000_000_000

        return {
            "revenue_growth": round(revenue_growth, 4),
            "profit_margin": round(profit_margin, 4),
            "de_ratio": round(de_ratio, 4),
            "roe": round(return_on_equity, 4),
            "pe_ratio": round(pe_ratio, 4),
            "fcf": round(fcf_billions, 4),
        }

    @staticmethod
    def _to_float(value, default: float) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:  # pylint: disable=broad-except
            return default

    @staticmethod
    def _quality_flags(metrics: dict[str, float]) -> list[str]:
        flags: list[str] = []
        if metrics["pe_ratio"] <= 0:
            flags.append("fundamentals_non_positive_pe")
        if metrics["de_ratio"] < 0:
            flags.append("fundamentals_negative_de_ratio")
        return flags


class HybridFundamentalsProvider:
    def __init__(self, primary: FundamentalsProvider, fallback: FundamentalsProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe) -> FundamentalsFetchResult:
        try:
            return await self._primary.fetch_metrics(ticker=ticker, timeframe=timeframe)
        except Exception as exc:  # pylint: disable=broad-except
            fallback_result = await self._fallback.fetch_metrics(ticker=ticker, timeframe=timeframe)
            fallback_result.quality_flags.append(
                f"fundamentals_primary_failed:{type(exc).__name__}"
            )
            fallback_result.quality_flags.append("fundamentals_fallback_used")
            return fallback_result
