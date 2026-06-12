from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import get_analysis_service
from backend.db.repositories import RunNotFoundError
from backend.models.schemas import (
    AnalysisRequest,
    AnalysisRunResponse,
    AnalysisRunSummary,
    CreateAnalysisResponse,
)
from backend.services.analysis_service import AnalysisService


router = APIRouter(tags=["analysis"])


@router.post(
    "/analysis",
    response_model=CreateAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_analysis(
    payload: AnalysisRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> CreateAnalysisResponse:
    return await service.create_analysis(payload)


@router.get("/analysis", response_model=list[AnalysisRunSummary])
async def list_analysis_runs(
    limit: int = Query(default=50, ge=1, le=200),
    service: AnalysisService = Depends(get_analysis_service),
) -> list[AnalysisRunSummary]:
    return await service.list_runs(limit)


@router.get("/analysis/{run_id}", response_model=AnalysisRunResponse)
async def get_analysis(
    run_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisRunResponse:
    try:
        return await service.get_analysis(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"analysis run not found: {run_id}",
        ) from exc

