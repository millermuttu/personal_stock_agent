from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisRunORM(Base):
    __tablename__ = "analysis_runs"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    selected_agents: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    attempt_log: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    final_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshot: Mapped["DataSnapshotORM | None"] = relationship(
        back_populates="run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    agent_reports: Mapped[list["AgentReportORM"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class DataSnapshotORM(Base):
    __tablename__ = "data_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("analysis_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    target_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_manifest_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    quality_flags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    features_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    run: Mapped[AnalysisRunORM] = relationship(back_populates="snapshot")


class AgentReportORM(Base):
    __tablename__ = "agent_reports"
    __table_args__ = (
        UniqueConstraint("run_id", "agent_name", name="uq_agent_reports_run_agent"),
    )

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("analysis_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    run: Mapped[AnalysisRunORM] = relationship(back_populates="agent_reports")
