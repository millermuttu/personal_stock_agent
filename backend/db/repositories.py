from __future__ import annotations

import asyncio
import uuid
from typing import Protocol

from backend.models.schemas import (
    AgentReportEnvelope,
    AnalysisRequest,
    AnalysisRunRecord,
    AnalysisRunResponse,
    AnalysisRunSummary,
    DataSnapshot,
    FinalVerdictReport,
    RunStatus,
    TargetType,
    utc_now,
)


AGENT_SLOTS: tuple[str, ...] = (
    "technical_analysis",
    "fundamental_analysis",
    "sentiment_analysis",
    "risk_analysis",
)


def summarize_run(record: AnalysisRunRecord) -> AnalysisRunSummary:
    final_report = record.final_report
    return AnalysisRunSummary(
        run_id=record.run_id,
        target_id=record.target_id,
        timeframe=record.timeframe,
        status=record.status,
        created_at=record.created_at,
        completed_at=record.completed_at,
        final_verdict=final_report.final_verdict if final_report else None,
        risk_level=final_report.risk_level if final_report else None,
        confidence=final_report.confidence if final_report else None,
    )


class RunNotFoundError(Exception):
    pass


class AgentWriteIsolationError(Exception):
    pass


class RunRepository(Protocol):
    async def create_run(self, request: AnalysisRequest) -> AnalysisRunRecord: ...

    async def get_run(self, run_id: str) -> AnalysisRunRecord: ...

    async def list_runs(self, *, limit: int = 50) -> list[AnalysisRunSummary]: ...

    async def update_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error_summary: str | None = None,
    ) -> AnalysisRunRecord: ...

    async def set_selected_agents(self, run_id: str, selected_agents: list[str]) -> AnalysisRunRecord: ...

    async def save_snapshot(self, run_id: str, snapshot: DataSnapshot) -> AnalysisRunRecord: ...

    async def upsert_agent_report(
        self,
        run_id: str,
        *,
        actor_agent_name: str,
        report: AgentReportEnvelope,
    ) -> AnalysisRunRecord: ...

    async def set_final_report(
        self,
        run_id: str,
        final_report: FinalVerdictReport,
        *,
        status: RunStatus,
    ) -> AnalysisRunRecord: ...

    @staticmethod
    def to_response(record: AnalysisRunRecord) -> AnalysisRunResponse: ...


class InMemoryRunRepository:
    """In-memory repository for fast local iteration.

    The repository enforces agent write isolation:
    an agent worker can only update its own report slot.
    """

    def __init__(self) -> None:
        self._runs: dict[str, AnalysisRunRecord] = {}
        self._lock = asyncio.Lock()

    async def create_run(self, request: AnalysisRequest) -> AnalysisRunRecord:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        record = AnalysisRunRecord(
            run_id=run_id,
            target_type=TargetType.STOCK,
            target_id=request.ticker,
            timeframe=request.timeframe,
            status=RunStatus.QUEUED,
            created_at=now,
            agent_reports={name: None for name in AGENT_SLOTS},
            attempt_log={name: 0 for name in AGENT_SLOTS},
        )
        async with self._lock:
            self._runs[run_id] = record
        return record

    async def get_run(self, run_id: str) -> AnalysisRunRecord:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            return run

    async def list_runs(self, *, limit: int = 50) -> list[AnalysisRunSummary]:
        async with self._lock:
            ordered = sorted(
                self._runs.values(),
                key=lambda record: record.created_at,
                reverse=True,
            )
            return [summarize_run(record) for record in ordered[:limit]]

    async def update_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error_summary: str | None = None,
    ) -> AnalysisRunRecord:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            run.status = status
            run.error_summary = error_summary
            if status in {RunStatus.COMPLETED, RunStatus.PARTIAL_SUCCESS, RunStatus.FAILED}:
                run.completed_at = utc_now()
            return run

    async def set_selected_agents(self, run_id: str, selected_agents: list[str]) -> AnalysisRunRecord:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            run.selected_agents = list(selected_agents)
            return run

    async def save_snapshot(self, run_id: str, snapshot: DataSnapshot) -> AnalysisRunRecord:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            run.snapshot = snapshot
            return run

    async def upsert_agent_report(
        self,
        run_id: str,
        *,
        actor_agent_name: str,
        report: AgentReportEnvelope,
    ) -> AnalysisRunRecord:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise RunNotFoundError(run_id)

            if actor_agent_name != report.agent_name:
                raise AgentWriteIsolationError(
                    "actor_agent_name and report.agent_name must match"
                )
            if actor_agent_name not in run.agent_reports:
                raise AgentWriteIsolationError(f"unknown agent slot: {actor_agent_name}")

            run.agent_reports[actor_agent_name] = report
            run.attempt_log[actor_agent_name] = run.attempt_log.get(actor_agent_name, 0) + 1
            return run

    async def set_final_report(
        self,
        run_id: str,
        final_report: FinalVerdictReport,
        *,
        status: RunStatus,
    ) -> AnalysisRunRecord:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise RunNotFoundError(run_id)
            run.final_report = final_report
            run.status = status
            run.completed_at = utc_now()
            return run

    @staticmethod
    def to_response(record: AnalysisRunRecord) -> AnalysisRunResponse:
        return AnalysisRunResponse(
            run_id=record.run_id,
            target_type=record.target_type,
            target_id=record.target_id,
            timeframe=record.timeframe,
            status=record.status,
            created_at=record.created_at,
            completed_at=record.completed_at,
            snapshot=record.snapshot,
            selected_agents=record.selected_agents,
            agent_reports=record.agent_reports,
            final_report=record.final_report,
            error_summary=record.error_summary,
        )
