from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.db.paper_repository import PostgresPaperRepository
from backend.db.postgres_repository import PostgresRunRepository
from backend.orchestrator.engine import OrchestratorEngine
from backend.db.session import SessionLocal
from backend.llm.client import LLMClient
from backend.services.analysis_service import AnalysisService
from backend.services.paper_trading_service import PaperTradingService
from backend.services.snapshot_builder import SnapshotBuilder
from backend.services.providers.fundamentals import (
    FundamentalsProvider,
    YahooFundamentalsProvider,
)
from backend.services.providers.market_data import (
    MarketDataProvider,
    YahooFinanceMarketDataProvider,
)
from backend.services.providers.news_sentiment import (
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
    timeout_seconds = _env_float("MARKET_DATA_TIMEOUT_SECONDS", 20.0)
    max_attempts = _env_int("MARKET_DATA_MAX_ATTEMPTS", 3)
    return YahooFinanceMarketDataProvider(timeout_seconds=timeout_seconds, max_attempts=max_attempts)


@lru_cache
def get_fundamentals_provider() -> FundamentalsProvider:
    timeout_seconds = _env_float("FUNDAMENTALS_TIMEOUT_SECONDS", 15.0)
    max_attempts = _env_int("FUNDAMENTALS_MAX_ATTEMPTS", 2)
    return YahooFundamentalsProvider(timeout_seconds=timeout_seconds, max_attempts=max_attempts)


@lru_cache
def get_news_sentiment_provider() -> NewsSentimentProvider:
    timeout_seconds = _env_float("NEWS_TIMEOUT_SECONDS", 15.0)
    max_attempts = _env_int("NEWS_MAX_ATTEMPTS", 2)
    max_headlines = _env_int("NEWS_MAX_HEADLINES", 8)
    return YahooNewsSentimentProvider(
        timeout_seconds=timeout_seconds,
        max_headlines=max_headlines,
        max_attempts=max_attempts,
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
        market_data_provider=get_market_data_provider(),
    )


@lru_cache
def get_paper_repository() -> PostgresPaperRepository:
    return PostgresPaperRepository(get_session_factory())


@lru_cache
def get_paper_trading_service() -> PaperTradingService:
    return PaperTradingService(
        repository=get_paper_repository(),
        run_repository=get_repository(),
        market_data_provider=get_market_data_provider(),
    )
