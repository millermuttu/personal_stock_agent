from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from backend.models.schemas import Timeframe, utc_now


class NewsSentimentProviderError(Exception):
    pass


@dataclass
class NewsArticle:
    title: str
    url: str | None = None
    source: str | None = None
    published_at: str | None = None


@dataclass
class NewsSentimentFetchResult:
    provider_name: str
    fetched_at: datetime
    headlines: list[str]
    sentiment_signals: dict[str, float]
    articles: list[NewsArticle] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)


class NewsSentimentProvider(Protocol):
    async def fetch_news_sentiment(
        self,
        *,
        ticker: str,
        timeframe: Timeframe,
    ) -> NewsSentimentFetchResult:
        ...


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
        articles: list[NewsArticle] | None = None
        last_exc: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                articles = await asyncio.wait_for(
                    asyncio.to_thread(self._fetch_sync, ticker, self._max_headlines),
                    timeout=self._timeout_seconds,
                )
                break
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc

        if articles is None:
            if last_exc is None:
                raise NewsSentimentProviderError("yahoo news fetch failed")
            raise NewsSentimentProviderError(str(last_exc)) from last_exc

        headlines = [article.title for article in articles]

        quality_flags = []
        if len(headlines) < 2:
            quality_flags.append("low_news_coverage")

        return NewsSentimentFetchResult(
            provider_name=self.provider_name,
            fetched_at=utc_now(),
            headlines=headlines,
            sentiment_signals=_derive_sentiment_signals(headlines),
            articles=articles,
            quality_flags=quality_flags,
        )

    @staticmethod
    def _fetch_sync(ticker: str, max_headlines: int) -> list[NewsArticle]:
        try:
            import yfinance as yf
        except Exception as exc:  # pylint: disable=broad-except
            raise NewsSentimentProviderError("yfinance package not installed") from exc

        payload = yf.Ticker(ticker).news
        if not isinstance(payload, list) or not payload:
            raise NewsSentimentProviderError("empty yahoo news response")

        seen: set[str] = set()
        articles: list[NewsArticle] = []
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
            articles.append(
                NewsArticle(
                    title=normalized,
                    url=YahooNewsSentimentProvider._extract_url(item),
                    source=YahooNewsSentimentProvider._extract_source(item),
                    published_at=YahooNewsSentimentProvider._extract_published_at(item),
                )
            )
            if len(articles) >= max_headlines:
                break

        if not articles:
            raise NewsSentimentProviderError("no usable Yahoo news headlines")
        return articles

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

    @staticmethod
    def _extract_url(item: dict) -> str | None:
        direct_link = item.get("link")
        if isinstance(direct_link, str) and direct_link.strip():
            return direct_link.strip()

        content = item.get("content")
        if isinstance(content, dict):
            # Newer Yahoo payloads nest the canonical URL under content.
            click_through = content.get("clickThroughUrl")
            if isinstance(click_through, dict):
                url = click_through.get("url")
                if isinstance(url, str) and url.strip():
                    return url.strip()
            canonical = content.get("canonicalUrl")
            if isinstance(canonical, dict):
                url = canonical.get("url")
                if isinstance(url, str) and url.strip():
                    return url.strip()
        return None

    @staticmethod
    def _extract_source(item: dict) -> str | None:
        publisher = item.get("publisher")
        if isinstance(publisher, str) and publisher.strip():
            return publisher.strip()

        content = item.get("content")
        if isinstance(content, dict):
            provider = content.get("provider")
            if isinstance(provider, dict):
                name = provider.get("displayName") or provider.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        return None

    @staticmethod
    def _extract_published_at(item: dict) -> str | None:
        content = item.get("content")
        if isinstance(content, dict):
            for key in ("pubDate", "displayTime"):
                value = content.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None


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
