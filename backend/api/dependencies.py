from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.db.postgres_repository import PostgresRunRepository
from backend.orchestrator.engine import OrchestratorEngine
from backend.db.session import SessionLocal
from backend.llm.client import LLMClient
from backend.services.analysis_service import AnalysisService
from backend.services.snapshot_builder import SnapshotBuilder
from backend.services.providers.fundamentals import (
    FundamentalsProvider,
    HybridFundamentalsProvider,
    MockFundamentalsProvider,
    YahooFundamentalsProvider,
)
from backend.services.providers.market_data import (
    HybridMarketDataProvider,
    MarketDataProvider,
    MockMarketDataProvider,
    YahooFinanceMarketDataProvider,
)
from backend.services.providers.news_sentiment import (
    HybridNewsSentimentProvider,
    MockNewsSentimentProvider,
    NewsSentimentProvider,
    YahooNewsSentimentProvider,
)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return max(1, value)
    except ValueError:
        return default


@lru_cache
def get_session_factory() -> async_sessionmaker:
    return SessionLocal


@lru_cache
def get_repository() -> PostgresRunRepository:
    return PostgresRunRepository(get_session_factory())


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    provider_mode = os.getenv("MARKET_DATA_PROVIDER", "hybrid").strip().lower()
    timeout_seconds = _env_float("MARKET_DATA_TIMEOUT_SECONDS", 20.0)
    max_attempts = _env_int("MARKET_DATA_MAX_ATTEMPTS", 3)
    if provider_mode == "mock":
        return MockMarketDataProvider()
    if provider_mode == "yahoo":
        return YahooFinanceMarketDataProvider(timeout_seconds=timeout_seconds, max_attempts=max_attempts)
    return HybridMarketDataProvider(
        primary=YahooFinanceMarketDataProvider(timeout_seconds=timeout_seconds, max_attempts=max_attempts),
        fallback=MockMarketDataProvider(),
    )


@lru_cache
def get_fundamentals_provider() -> FundamentalsProvider:
    provider_mode = os.getenv("FUNDAMENTALS_PROVIDER", "hybrid").strip().lower()
    timeout_seconds = _env_float("FUNDAMENTALS_TIMEOUT_SECONDS", 15.0)
    max_attempts = _env_int("FUNDAMENTALS_MAX_ATTEMPTS", 2)
    if provider_mode == "mock":
        return MockFundamentalsProvider()
    if provider_mode == "yahoo":
        return YahooFundamentalsProvider(timeout_seconds=timeout_seconds, max_attempts=max_attempts)
    return HybridFundamentalsProvider(
        primary=YahooFundamentalsProvider(timeout_seconds=timeout_seconds, max_attempts=max_attempts),
        fallback=MockFundamentalsProvider(),
    )


@lru_cache
def get_news_sentiment_provider() -> NewsSentimentProvider:
    provider_mode = os.getenv("NEWS_PROVIDER", "hybrid").strip().lower()
    timeout_seconds = _env_float("NEWS_TIMEOUT_SECONDS", 15.0)
    max_attempts = _env_int("NEWS_MAX_ATTEMPTS", 2)
    max_headlines = _env_int("NEWS_MAX_HEADLINES", 8)
    if provider_mode == "mock":
        return MockNewsSentimentProvider()
    if provider_mode == "yahoo":
        return YahooNewsSentimentProvider(
            timeout_seconds=timeout_seconds,
            max_headlines=max_headlines,
            max_attempts=max_attempts,
        )
    return HybridNewsSentimentProvider(
        primary=YahooNewsSentimentProvider(
            timeout_seconds=timeout_seconds,
            max_headlines=max_headlines,
            max_attempts=max_attempts,
        ),
        fallback=MockNewsSentimentProvider(),
    )


@lru_cache
def get_snapshot_builder() -> SnapshotBuilder:
    return SnapshotBuilder(
        market_data_provider=get_market_data_provider(),
        fundamentals_provider=get_fundamentals_provider(),
        news_provider=get_news_sentiment_provider(),
    )


@lru_cache
def get_llm_client() -> LLMClient:
    return LLMClient()


@lru_cache
def get_orchestrator() -> OrchestratorEngine:
    return OrchestratorEngine(
        repository=get_repository(),
        snapshot_builder=get_snapshot_builder(),
        llm_client=get_llm_client(),
    )


@lru_cache
def get_analysis_service() -> AnalysisService:
    return AnalysisService(
        repository=get_repository(),
        orchestrator=get_orchestrator(),
    )
