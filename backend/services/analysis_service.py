from __future__ import annotations

import asyncio

from backend.db.repositories import RunNotFoundError, RunRepository
from backend.models.schemas import (
    AnalysisRequest,
    AnalysisRunResponse,
    AnalysisRunSummary,
    CandleBar,
    CreateAnalysisResponse,
    HealthResponse,
    PriceHistoryResponse,
    PriceRange,
    RunStatus,
    StockSearchResult,
    normalize_indian_ticker,
    utc_now,
)
from backend.orchestrator.engine import OrchestratorEngine
from backend.services.providers.market_data import (
    MarketDataProvider,
    YahooFinanceMarketDataProvider,
)
from backend.services.providers.symbol_search import (
    SymbolSearchProvider,
    YahooSymbolSearchProvider,
)


class AnalysisService:
    def __init__(
        self,
        repository: RunRepository,
        orchestrator: OrchestratorEngine,
        symbol_search_provider: SymbolSearchProvider | None = None,
        market_data_provider: MarketDataProvider | None = None,
    ) -> None:
        self._repository = repository
        self._orchestrator = orchestrator
        self._symbol_search_provider = symbol_search_provider or YahooSymbolSearchProvider()
        self._market_data_provider = market_data_provider or YahooFinanceMarketDataProvider()
        self._tasks: set[asyncio.Task] = set()

    async def create_analysis(self, request: AnalysisRequest) -> CreateAnalysisResponse:
        record = await self._repository.create_run(request)
        task = asyncio.create_task(self._orchestrator.process_run(record.run_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return CreateAnalysisResponse(run_id=record.run_id, status=RunStatus.QUEUED)

    async def get_analysis(self, run_id: str) -> AnalysisRunResponse:
        record = await self._repository.get_run(run_id)
        return self._repository.to_response(record)

    async def list_runs(self, limit: int = 50) -> list[AnalysisRunSummary]:
        return await self._repository.list_runs(limit=limit)

    async def search_stocks(self, query: str = "") -> list[StockSearchResult]:
        return await self._symbol_search_provider.search(query)

    async def get_price_history(self, ticker: str, price_range: PriceRange) -> PriceHistoryResponse:
        normalized = normalize_indian_ticker(ticker)
        result = await self._market_data_provider.fetch_candles(
            ticker=normalized,
            price_range=price_range,
        )
        return PriceHistoryResponse(
            ticker=normalized,
            range=price_range,
            interval=result.interval,
            bars=[
                CandleBar(
                    time=bar.time,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
                for bar in result.bars
            ],
        )

    @staticmethod
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", timestamp=utc_now())


__all__ = ["AnalysisService", "RunNotFoundError"]
