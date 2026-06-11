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
    ) -> None:
        self._repository = repository
        self._orchestrator = orchestrator
        self._symbol_search_provider = symbol_search_provider or YahooSymbolSearchProvider()
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
        return await self._symbol_search_provider.search(query)

    @staticmethod
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", timestamp=utc_now())


__all__ = ["AnalysisService", "RunNotFoundError"]
