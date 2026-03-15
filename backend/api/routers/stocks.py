from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_analysis_service
from backend.models.schemas import StockSearchResult
from backend.services.analysis_service import AnalysisService


router = APIRouter(tags=["stocks"])


@router.get("/stocks/search", response_model=list[StockSearchResult])
async def search_stocks(
    q: str = Query(default="", max_length=50),
    service: AnalysisService = Depends(get_analysis_service),
) -> list[StockSearchResult]:
    return await service.search_stocks(q)

