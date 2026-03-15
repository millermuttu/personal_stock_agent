from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_analysis_service
from backend.models.schemas import HealthResponse
from backend.services.analysis_service import AnalysisService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    service: AnalysisService = Depends(get_analysis_service),
) -> HealthResponse:
    return await service.health()

