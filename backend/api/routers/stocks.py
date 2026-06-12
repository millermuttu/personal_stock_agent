from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import get_analysis_service
from backend.models.schemas import PriceHistoryResponse, PriceRange, StockSearchResult
from backend.services.analysis_service import AnalysisService
from backend.services.providers.market_data import MarketDataProviderError


router = APIRouter(tags=["stocks"])


@router.get("/stocks/search", response_model=list[StockSearchResult])
async def search_stocks(
    q: str = Query(default="", max_length=50),
    service: AnalysisService = Depends(get_analysis_service),
) -> list[StockSearchResult]:
    return await service.search_stocks(q)


@router.get("/stocks/{ticker}/candles", response_model=PriceHistoryResponse)
async def get_candles(
    ticker: str,
    range: PriceRange = Query(default=PriceRange.ONE_MONTH),
    service: AnalysisService = Depends(get_analysis_service),
) -> PriceHistoryResponse:
    try:
        return await service.get_price_history(ticker, range)
    except MarketDataProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"price history unavailable for {ticker}: {exc}",
        ) from exc

