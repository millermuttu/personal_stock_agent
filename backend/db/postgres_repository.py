from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from backend.db.models import AgentReportORM, AnalysisRunORM, DataSnapshotORM
from backend.db.repositories import (
    AGENT_SLOTS,
    AgentWriteIsolationError,
    RunNotFoundError,
)
from backend.models.schemas import (
    AgentReportEnvelope,
    AnalysisRequest,
    AnalysisRunRecord,
    AnalysisRunResponse,
    AnalysisRunSummary,
    DataSnapshot,
    FinalVerdict,
    FinalVerdictReport,
    RiskLevel,
    RunStatus,
    TargetType,
    Timeframe,
    utc_now,
)


def _safe_enum(enum_cls, value):
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None


class PostgresRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_run(self, request: AnalysisRequest) -> AnalysisRunRecord:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        row = AnalysisRunORM(
            run_id=run_id,
            target_type=TargetType.STOCK.value,
            target_id=request.ticker,
            timeframe=request.timeframe.value,
            status=RunStatus.QUEUED.value,
            created_at=now,
            selected_agents=[],
            attempt_log={name: 0 for name in AGENT_SLOTS},
            final_report_json=None,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
        return await self.get_run(run_id)

    async def get_run(self, run_id: str) -> AnalysisRunRecord:
        async with self._session_factory() as session:
            run_row = await self._fetch_run_row(session, run_id)
            if run_row is None:
                raise RunNotFoundError(run_id)
            return self._to_record(run_row)

    async def list_runs(self, *, limit: int = 50) -> list[AnalysisRunSummary]:
        async with self._session_factory() as session:
            stmt = (
                select(AnalysisRunORM)
                .order_by(AnalysisRunORM.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [self._row_to_summary(row) for row in rows]

    @staticmethod
    def _row_to_summary(run_row: AnalysisRunORM) -> AnalysisRunSummary:
        final = run_row.final_report_json or {}
        return AnalysisRunSummary(
            run_id=run_row.run_id,
            target_id=run_row.target_id,
            timeframe=Timeframe(run_row.timeframe),
            status=RunStatus(run_row.status),
            created_at=run_row.created_at,
            completed_at=run_row.completed_at,
            final_verdict=_safe_enum(FinalVerdict, final.get("final_verdict")),
            risk_level=_safe_enum(RiskLevel, final.get("risk_level")),
            confidence=final.get("confidence") if isinstance(final.get("confidence"), (int, float)) else None,
        )

    async def update_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error_summary: str | None = None,
    ) -> AnalysisRunRecord:
        async with self._session_factory() as session:
            run_row = await self._fetch_run_row_for_update(session, run_id)
            if run_row is None:
                raise RunNotFoundError(run_id)
            run_row.status = status.value
            run_row.error_summary = error_summary
            if status in {RunStatus.COMPLETED, RunStatus.PARTIAL_SUCCESS, RunStatus.FAILED}:
                run_row.completed_at = utc_now()
            await session.commit()
        return await self.get_run(run_id)

    async def set_selected_agents(self, run_id: str, selected_agents: list[str]) -> AnalysisRunRecord:
        async with self._session_factory() as session:
            run_row = await self._fetch_run_row_for_update(session, run_id)
            if run_row is None:
                raise RunNotFoundError(run_id)
            run_row.selected_agents = list(selected_agents)
            await session.commit()
        return await self.get_run(run_id)

    async def save_snapshot(self, run_id: str, snapshot: DataSnapshot) -> AnalysisRunRecord:
        snapshot_payload = snapshot.model_dump(mode="json")
        async with self._session_factory() as session:
            run_row = await self._fetch_run_row_for_update(session, run_id)
            if run_row is None:
                raise RunNotFoundError(run_id)

            existing_snapshot = run_row.snapshot
            if existing_snapshot is None:
                session.add(
                    DataSnapshotORM(
                        snapshot_id=snapshot.snapshot_id,
                        run_id=run_id,
                        target_id=snapshot.target_id,
                        as_of=snapshot.as_of,
                        provider_manifest_json=snapshot_payload["providers"],
                        quality_flags_json=snapshot_payload["data_quality_flags"],
                        features_json=snapshot_payload["features"],
                    )
                )
            else:
                existing_snapshot.snapshot_id = snapshot.snapshot_id
                existing_snapshot.target_id = snapshot.target_id
                existing_snapshot.as_of = snapshot.as_of
                existing_snapshot.provider_manifest_json = snapshot_payload["providers"]
                existing_snapshot.quality_flags_json = snapshot_payload["data_quality_flags"]
                existing_snapshot.features_json = snapshot_payload["features"]
            await session.commit()
        return await self.get_run(run_id)

    async def upsert_agent_report(
        self,
        run_id: str,
        *,
        actor_agent_name: str,
        report: AgentReportEnvelope,
    ) -> AnalysisRunRecord:
        if actor_agent_name != report.agent_name:
            raise AgentWriteIsolationError("actor_agent_name and report.agent_name must match")
        if actor_agent_name not in AGENT_SLOTS:
            raise AgentWriteIsolationError(f"unknown agent slot: {actor_agent_name}")

        report_payload = report.model_dump(mode="json")
        async with self._session_factory() as session:
            run_row = await self._fetch_run_row_for_update(session, run_id)
            if run_row is None:
                raise RunNotFoundError(run_id)

            attempts = dict(run_row.attempt_log or {})
            attempts[actor_agent_name] = attempts.get(actor_agent_name, 0) + 1
            run_row.attempt_log = attempts

            existing_stmt = select(AgentReportORM).where(
                AgentReportORM.run_id == run_id,
                AgentReportORM.agent_name == actor_agent_name,
            )
            existing_row = (await session.execute(existing_stmt)).scalar_one_or_none()
            if existing_row is None:
                session.add(
                    AgentReportORM(
                        run_id=run_id,
                        agent_name=actor_agent_name,
                        status=report.status.value,
                        as_of=report.as_of,
                        confidence=report.confidence,
                        report_json=report_payload,
                        error_json=report.errors,
                    )
                )
            else:
                existing_row.status = report.status.value
                existing_row.as_of = report.as_of
                existing_row.confidence = report.confidence
                existing_row.report_json = report_payload
                existing_row.error_json = report.errors

            await session.commit()
        return await self.get_run(run_id)

    async def set_final_report(
        self,
        run_id: str,
        final_report: FinalVerdictReport,
        *,
        status: RunStatus,
    ) -> AnalysisRunRecord:
        async with self._session_factory() as session:
            run_row = await self._fetch_run_row_for_update(session, run_id)
            if run_row is None:
                raise RunNotFoundError(run_id)
            run_row.final_report_json = final_report.model_dump(mode="json")
            run_row.status = status.value
            run_row.completed_at = utc_now()
            await session.commit()
        return await self.get_run(run_id)

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

    async def _fetch_run_row(self, session: AsyncSession, run_id: str) -> AnalysisRunORM | None:
        stmt = (
            select(AnalysisRunORM)
            .options(
                selectinload(AnalysisRunORM.snapshot),
                selectinload(AnalysisRunORM.agent_reports),
            )
            .where(AnalysisRunORM.run_id == run_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _fetch_run_row_for_update(self, session: AsyncSession, run_id: str) -> AnalysisRunORM | None:
        stmt = (
            select(AnalysisRunORM)
            .options(
                selectinload(AnalysisRunORM.snapshot),
                selectinload(AnalysisRunORM.agent_reports),
            )
            .where(AnalysisRunORM.run_id == run_id)
            .with_for_update()
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _to_record(run_row: AnalysisRunORM) -> AnalysisRunRecord:
        snapshot = None
        if run_row.snapshot is not None:
            snapshot = DataSnapshot.model_validate(
                {
                    "snapshot_id": run_row.snapshot.snapshot_id,
                    "target_id": run_row.snapshot.target_id,
                    "as_of": run_row.snapshot.as_of,
                    "providers": run_row.snapshot.provider_manifest_json,
                    "data_quality_flags": run_row.snapshot.quality_flags_json,
                    "features": run_row.snapshot.features_json,
                }
            )

        report_map: dict[str, AgentReportEnvelope | None] = {name: None for name in AGENT_SLOTS}
        for row in run_row.agent_reports:
            report_map[row.agent_name] = AgentReportEnvelope.model_validate(row.report_json)

        final_report = None
        if run_row.final_report_json is not None:
            final_report = FinalVerdictReport.model_validate(run_row.final_report_json)

        return AnalysisRunRecord(
            run_id=run_row.run_id,
            target_type=TargetType(run_row.target_type),
            target_id=run_row.target_id,
            timeframe=run_row.timeframe,
            status=run_row.status,
            created_at=run_row.created_at,
            completed_at=run_row.completed_at,
            snapshot=snapshot,
            selected_agents=run_row.selected_agents or [],
            agent_reports=report_map,
            final_report=final_report,
            error_summary=run_row.error_summary,
            attempt_log=run_row.attempt_log or {},
        )

