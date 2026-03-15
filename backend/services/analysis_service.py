from __future__ import annotations

import asyncio

from backend.db.repositories import RunNotFoundError, RunRepository
from backend.models.schemas import (
    AnalysisRequest,
    AnalysisRunResponse,
    CreateAnalysisResponse,
    HealthResponse,
    RunStatus,
    StockSearchResult,
    utc_now,
)
from backend.orchestrator.engine import OrchestratorEngine


STOCK_CATALOG = [
    StockSearchResult(ticker="AAPL", name="Apple Inc.", sector="Technology"),
    StockSearchResult(ticker="MSFT", name="Microsoft Corporation", sector="Technology"),
    StockSearchResult(ticker="NVDA", name="NVIDIA Corporation", sector="Technology"),
    StockSearchResult(ticker="AMZN", name="Amazon.com, Inc.", sector="Consumer Discretionary"),
    StockSearchResult(ticker="TSLA", name="Tesla, Inc.", sector="Consumer Discretionary"),
    StockSearchResult(ticker="JPM", name="JPMorgan Chase & Co.", sector="Financials"),
]


class AnalysisService:
    def __init__(self, repository: RunRepository, orchestrator: OrchestratorEngine) -> None:
        self._repository = repository
        self._orchestrator = orchestrator
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

    async def search_stocks(self, query: str = "") -> list[StockSearchResult]:
        normalized = query.strip().lower()
        if not normalized:
            return STOCK_CATALOG
        return [
            item
            for item in STOCK_CATALOG
            if normalized in item.ticker.lower() or normalized in item.name.lower()
        ]

    @staticmethod
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", timestamp=utc_now())


__all__ = ["AnalysisService", "RunNotFoundError"]
