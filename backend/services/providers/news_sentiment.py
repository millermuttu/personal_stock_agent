from __future__ import annotations

import asyncio
import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from backend.models.schemas import Timeframe, utc_now


class NewsSentimentProviderError(Exception):
    pass


@dataclass
class NewsSentimentFetchResult:
    provider_name: str
    fetched_at: datetime
    headlines: list[str]
    sentiment_signals: dict[str, float]
    quality_flags: list[str] = field(default_factory=list)


class NewsSentimentProvider(Protocol):
    async def fetch_news_sentiment(
        self,
        *,
        ticker: str,
        timeframe: Timeframe,
    ) -> NewsSentimentFetchResult:
        ...


class MockNewsSentimentProvider:
    provider_name = "mock_news_provider"

    async def fetch_news_sentiment(
        self,
        *,
        ticker: str,
        timeframe: Timeframe,
    ) -> NewsSentimentFetchResult:
        seed = self._seed_from_inputs(ticker=ticker, timeframe=timeframe.value)
        rng = random.Random(seed)
        pool = [
            f"{ticker} expands cloud partnership with enterprise customer",
            f"{ticker} faces analyst debate on valuation after earnings",
            f"{ticker} announces product roadmap update for next quarter",
            f"Macro data drives sector-wide volatility impacting {ticker}",
            f"{ticker} reports stronger-than-expected operating margin",
            f"{ticker} raises guidance after stronger demand outlook",
            f"{ticker} faces regulatory review creating investor concern",
        ]
        rng.shuffle(pool)
        count = rng.randint(1, 6)
        headlines = pool[:count]
        quality_flags = []
        if len(headlines) < 2:
            quality_flags.append("low_news_coverage")
        return NewsSentimentFetchResult(
            provider_name=self.provider_name,
            fetched_at=utc_now(),
            headlines=headlines,
            sentiment_signals=_derive_sentiment_signals(headlines),
            quality_flags=quality_flags,
        )

    @staticmethod
    def _seed_from_inputs(*, ticker: str, timeframe: str) -> int:
        digest = hashlib.sha256(f"{ticker}:{timeframe}:news".encode("utf-8")).hexdigest()
        return int(digest[:10], 16)


class YahooNewsSentimentProvider:
    provider_name = "yahoo_news"

    def __init__(
        self,
        timeout_seconds: float = 15.0,
        max_headlines: int = 8,
        max_attempts: int = 2,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_headlines = max_headlines
        self._max_attempts = max(1, max_attempts)

    async def fetch_news_sentiment(
        self,
        *,
        ticker: str,
        timeframe: Timeframe,
    ) -> NewsSentimentFetchResult:
        del timeframe
        headlines: list[str] | None = None
        last_exc: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                headlines = await asyncio.wait_for(
                    asyncio.to_thread(self._fetch_sync, ticker, self._max_headlines),
                    timeout=self._timeout_seconds,
                )
                break
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc

        if headlines is None:
            if last_exc is None:
                raise NewsSentimentProviderError("yahoo news fetch failed")
            raise NewsSentimentProviderError(str(last_exc)) from last_exc

        quality_flags = []
        if len(headlines) < 2:
            quality_flags.append("low_news_coverage")

        return NewsSentimentFetchResult(
            provider_name=self.provider_name,
            fetched_at=utc_now(),
            headlines=headlines,
            sentiment_signals=_derive_sentiment_signals(headlines),
            quality_flags=quality_flags,
        )

    @staticmethod
    def _fetch_sync(ticker: str, max_headlines: int) -> list[str]:
        try:
            import yfinance as yf
        except Exception as exc:  # pylint: disable=broad-except
            raise NewsSentimentProviderError("yfinance package not installed") from exc

        payload = yf.Ticker(ticker).news
        if not isinstance(payload, list) or not payload:
            raise NewsSentimentProviderError("empty yahoo news response")

        seen: set[str] = set()
        headlines: list[str] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            title = YahooNewsSentimentProvider._extract_title(item)
            if title is None:
                continue
            normalized = title.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            headlines.append(normalized)
            if len(headlines) >= max_headlines:
                break

        if not headlines:
            raise NewsSentimentProviderError("no usable Yahoo news headlines")
        return headlines

    @staticmethod
    def _extract_title(item: dict) -> str | None:
        direct_title = item.get("title")
        if isinstance(direct_title, str) and direct_title.strip():
            return direct_title

        content = item.get("content")
        if isinstance(content, dict):
            nested_title = content.get("title")
            if isinstance(nested_title, str) and nested_title.strip():
                return nested_title

            nested_headline = content.get("headline")
            if isinstance(nested_headline, str) and nested_headline.strip():
                return nested_headline
        return None


class HybridNewsSentimentProvider:
    def __init__(self, primary: NewsSentimentProvider, fallback: NewsSentimentProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def fetch_news_sentiment(
        self,
        *,
        ticker: str,
        timeframe: Timeframe,
    ) -> NewsSentimentFetchResult:
        try:
            return await self._primary.fetch_news_sentiment(ticker=ticker, timeframe=timeframe)
        except Exception as exc:  # pylint: disable=broad-except
            fallback_result = await self._fallback.fetch_news_sentiment(
                ticker=ticker,
                timeframe=timeframe,
            )
            fallback_result.quality_flags.append(f"news_primary_failed:{type(exc).__name__}")
            fallback_result.quality_flags.append("news_fallback_used")
            return fallback_result


def _derive_sentiment_signals(headlines: list[str]) -> dict[str, float]:
    positive_tokens = (
        "strong",
        "expands",
        "partnership",
        "roadmap",
        "higher",
        "improving",
        "raises guidance",
        "beat",
    )
    negative_tokens = (
        "debate",
        "volatility",
        "concern",
        "downgrade",
        "risk",
        "regulatory",
        "miss",
    )

    positive_hits = 0
    negative_hits = 0
    for headline in headlines:
        normalized = headline.lower()
        positive_hits += sum(1 for token in positive_tokens if token in normalized)
        negative_hits += sum(1 for token in negative_tokens if token in normalized)

    total_hits = positive_hits + negative_hits
    score = 0.0 if total_hits == 0 else (positive_hits - negative_hits) / total_hits
    coverage_score = min(len(headlines) / 5, 1.0)
    return {
        "headline_sentiment_score": round(score, 4),
        "positive_hits": float(positive_hits),
        "negative_hits": float(negative_hits),
        "coverage_score": round(coverage_score, 4),
    }
