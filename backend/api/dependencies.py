from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.db.postgres_repository import PostgresRunRepository
from backend.orchestrator.engine import OrchestratorEngine
from backend.db.session import SessionLocal
from backend.llm.client import LLMClient
from backend.services.analysis_service import AnalysisService
from backend.services.snapshot_builder import SnapshotBuilder


@lru_cache
def get_session_factory() -> async_sessionmaker:
    return SessionLocal


@lru_cache
def get_repository() -> PostgresRunRepository:
    return PostgresRunRepository(get_session_factory())


@lru_cache
def get_snapshot_builder() -> SnapshotBuilder:
    return SnapshotBuilder()


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
    )
