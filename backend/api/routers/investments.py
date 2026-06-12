from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_paper_trading_service
from backend.models.schemas import InvestmentsResponse, OpenInvestmentRequest, PaperPosition
from backend.services.paper_trading_service import (
    InsufficientFundsError,
    PaperTradingError,
    PaperTradingService,
)


router = APIRouter(tags=["investments"])


@router.post("/investments", response_model=PaperPosition, status_code=status.HTTP_201_CREATED)
async def open_investment(
    payload: OpenInvestmentRequest,
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> PaperPosition:
    try:
        return await service.open_investment(payload)
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PaperTradingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/investments", response_model=InvestmentsResponse)
async def list_investments(
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> InvestmentsResponse:
    return await service.list_investments()


@router.post("/investments/{position_id}/close", response_model=PaperPosition)
async def close_investment(
    position_id: str,
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> PaperPosition:
    try:
        return await service.close_investment(position_id)
    except PaperTradingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
