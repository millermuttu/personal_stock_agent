import os
import sys
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/stock_agent",
)
os.environ.pop("OPENAI_API_KEY", None)

from backend.main import app
from backend.db.repositories import InMemoryRunRepository
from backend.llm.client import LLMClient
from backend.models.schemas import AnalysisRequest, Timeframe, utc_now
from backend.orchestrator.engine import OrchestratorEngine
from backend.services.analysis_service import AnalysisService
from backend.services.providers.fundamentals import FundamentalsFetchResult
from backend.services.providers.market_data import MarketDataFetchResult
from backend.services.providers.news_sentiment import (
    NewsSentimentFetchResult,
    _derive_sentiment_signals,
)
from backend.services.snapshot_builder import SnapshotBuilder


class StubMarketDataProvider:
    name = "stub_market_data"

    async def fetch_price_history(self, *, ticker: str, timeframe: Timeframe):
        closes = [round(100 + index * 0.5, 2) for index in range(260)]
        return MarketDataFetchResult(provider_name=self.name, fetched_at=utc_now(), closes=closes)


class StubFundamentalsProvider:
    name = "stub_fundamentals"

    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe):
        return FundamentalsFetchResult(
            provider_name=self.name,
            fetched_at=utc_now(),
            metrics={
                "revenue_growth": 0.12,
                "profit_margin": 0.21,
                "de_ratio": 0.8,
                "roe": 0.18,
                "pe_ratio": 24.0,
                "fcf": 9.5,
            },
            beta=1.1,
        )


class StubNewsProvider:
    name = "stub_news"

    async def fetch_news_sentiment(self, *, ticker: str, timeframe: Timeframe):
        headlines = [f"{ticker} raises guidance after stronger demand outlook"]
        return NewsSentimentFetchResult(
            provider_name=self.name,
            fetched_at=utc_now(),
            headlines=headlines,
            sentiment_signals=_derive_sentiment_signals(headlines),
        )


class BearishHighRiskMarketDataProvider:
    name = "stub_bear_market_data"

    async def fetch_price_history(self, *, ticker: str, timeframe: Timeframe):
        # Steep, steady decline: bearish MAs + MACD, and a >50% drawdown so the
        # risk agent flags a deep historical drawdown.
        closes = [round(200 - index * 0.45, 2) for index in range(260)]
        return MarketDataFetchResult(provider_name=self.name, fetched_at=utc_now(), closes=closes)


class BearishHighRiskFundamentalsProvider:
    name = "stub_bear_fundamentals"

    async def fetch_metrics(self, *, ticker: str, timeframe: Timeframe):
        return FundamentalsFetchResult(
            provider_name=self.name,
            fetched_at=utc_now(),
            metrics={
                "revenue_growth": -0.05,
                "profit_margin": 0.02,
                "de_ratio": 1.6,
                "roe": 0.03,
                "pe_ratio": 22.0,
                "fcf": 1.0,
            },
            beta=1.8,  # high beta -> second high-risk signal -> BLOCK
        )


class BearishNewsProvider:
    name = "stub_bear_news"

    async def fetch_news_sentiment(self, *, ticker: str, timeframe: Timeframe):
        headlines = [f"{ticker} faces downgrade amid regulatory risk and concern"]
        return NewsSentimentFetchResult(
            provider_name=self.name,
            fetched_at=utc_now(),
            headlines=headlines,
            sentiment_signals=_derive_sentiment_signals(headlines),
        )


def _build_bearish_high_risk_service() -> AnalysisService:
    repository = InMemoryRunRepository()
    snapshot_builder = SnapshotBuilder(
        market_data_provider=BearishHighRiskMarketDataProvider(),
        fundamentals_provider=BearishHighRiskFundamentalsProvider(),
        news_provider=BearishNewsProvider(),
    )
    orchestrator = OrchestratorEngine(
        repository=repository,
        snapshot_builder=snapshot_builder,
        llm_client=LLMClient(api_key=None),
    )
    return AnalysisService(repository=repository, orchestrator=orchestrator)


def _build_offline_service() -> AnalysisService:
    repository = InMemoryRunRepository()
    snapshot_builder = SnapshotBuilder(
        market_data_provider=StubMarketDataProvider(),
        fundamentals_provider=StubFundamentalsProvider(),
        news_provider=StubNewsProvider(),
    )
    orchestrator = OrchestratorEngine(
        repository=repository,
        snapshot_builder=snapshot_builder,
        llm_client=LLMClient(api_key=None),
    )
    return AnalysisService(repository=repository, orchestrator=orchestrator)


async def _run_to_terminal(service: AnalysisService, ticker: str):
    created = await service.create_analysis(AnalysisRequest(ticker=ticker, timeframe="short"))
    run_id = created.run_id
    for _ in range(80):
        payload = await service.get_analysis(run_id)
        if payload.status.value in {"completed", "partial_success", "failed"}:
            return payload
        await asyncio.sleep(0.05)
    return None


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_analysis_run_completes_and_returns_agent_reports():
    service = _build_offline_service()
    final_payload = asyncio.run(_run_to_terminal(service, "NVDA"))

    assert final_payload is not None, "run did not reach terminal state in time"
    assert final_payload.status.value in {"completed", "partial_success"}
    assert final_payload.final_report is not None
    assert final_payload.final_report.final_verdict.value in {
        "buy",
        "hold",
        "sell",
        "no_recommendation",
    }
    assert final_payload.final_report.synthesis_source.value == "heuristic"
    assert final_payload.final_report.model_version is None
    assert final_payload.final_report.prompt_version == "heuristic_v1"
    assert final_payload.final_report.llm_fallback_reason == "llm_unavailable_no_api_key"

    reports = final_payload.agent_reports
    assert reports["technical_analysis"] is not None
    assert reports["risk_analysis"] is not None


def test_high_risk_bearish_run_yields_sell_not_blocked():
    # A hard risk block must still allow a de-risking SELL to surface, rather
    # than collapsing the bearish-majority call into no_recommendation.
    service = _build_bearish_high_risk_service()
    final_payload = asyncio.run(_run_to_terminal(service, "WEAKCO"))

    assert final_payload is not None, "run did not reach terminal state in time"
    assert final_payload.final_report is not None
    assert final_payload.final_report.final_verdict.value == "sell"
    # Conviction score must agree in sign with the bearish verdict.
    assert final_payload.final_report.bias_score is not None
    assert final_payload.final_report.bias_score < 0
    assert final_payload.final_report.risk_level.value == "high"
    assert final_payload.agent_reports["risk_analysis"].result[
        "recommendation_constraint"
    ] == "block"


def test_sample_run_returns_snapshot_and_verdict():
    service = _build_offline_service()
    final_payload = asyncio.run(_run_to_terminal(service, "AAPL"))

    assert final_payload is not None, "run did not reach terminal state in time"
    assert final_payload.status.value in {"completed", "partial_success"}
    assert final_payload.snapshot is not None
    assert len(final_payload.snapshot.features.price_history) >= 30
    assert "headline_sentiment_score" in final_payload.snapshot.features.sentiment_signals
    assert final_payload.snapshot.features.risk_metrics["beta"] == 1.1
    assert final_payload.final_report is not None
