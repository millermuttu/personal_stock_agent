from __future__ import annotations

import asyncio
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
    beta: float | None = None
    sector: str | None = None
    industry: str | None = None
    quality_flags: list[str] = field(default_factory=list)


class FundamentalsProvider(Protocol):
    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe) -> FundamentalsFetchResult:
        ...


class YahooFundamentalsProvider:
    provider_name = "yahoo_fundamentals"

    def __init__(self, timeout_seconds: float = 15.0, max_attempts: int = 2) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max(1, max_attempts)

    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe) -> FundamentalsFetchResult:
        del timeframe
        fetched: tuple[dict[str, float], float | None, str | None, str | None] | None = None
        last_exc: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                fetched = await asyncio.wait_for(
                    asyncio.to_thread(self._fetch_sync, ticker),
                    timeout=self._timeout_seconds,
                )
                break
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc

        if fetched is None:
            if last_exc is None:
                raise FundamentalsProviderError("yahoo fundamentals fetch failed")
            raise FundamentalsProviderError(str(last_exc)) from last_exc

        metrics, beta, sector, industry = fetched
        quality_flags = self._quality_flags(metrics)
        return FundamentalsFetchResult(
            provider_name=self.provider_name,
            fetched_at=utc_now(),
            metrics=metrics,
            beta=beta,
            sector=sector,
            industry=industry,
            quality_flags=quality_flags,
        )

    @staticmethod
    def _fetch_sync(ticker: str) -> tuple[dict[str, float], float | None, str | None, str | None]:
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

        beta_raw = data.get("beta")
        beta = float(beta_raw) if isinstance(beta_raw, (int, float)) else None

        sector = data.get("sector")
        sector = sector.strip() if isinstance(sector, str) and sector.strip() else None
        industry = data.get("industry")
        industry = industry.strip() if isinstance(industry, str) and industry.strip() else None

        metrics = {
            "revenue_growth": round(revenue_growth, 4),
            "profit_margin": round(profit_margin, 4),
            "de_ratio": round(de_ratio, 4),
            "roe": round(return_on_equity, 4),
            "pe_ratio": round(pe_ratio, 4),
            "fcf": round(fcf_billions, 4),
        }
        return metrics, (round(beta, 4) if beta is not None else None), sector, industry

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
