"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-03-15 17:45:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("run_id", sa.String(length=32), primary_key=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=24), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selected_agents", sa.JSON(), nullable=False),
        sa.Column("attempt_log", sa.JSON(), nullable=False),
        sa.Column("final_report_json", sa.JSON(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_analysis_runs_target_id", "analysis_runs", ["target_id"])

    op.create_table(
        "data_snapshots",
        sa.Column("snapshot_id", sa.String(length=32), primary_key=True),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=24), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_manifest_json", sa.JSON(), nullable=False),
        sa.Column("quality_flags_json", sa.JSON(), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", name="uq_data_snapshots_run_id"),
    )
    op.create_index("ix_data_snapshots_run_id", "data_snapshots", ["run_id"])
    op.create_index("ix_data_snapshots_target_id", "data_snapshots", ["target_id"])

    op.create_table(
        "agent_reports",
        sa.Column("report_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("error_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "agent_name", name="uq_agent_reports_run_agent"),
    )
    op.create_index("ix_agent_reports_run_id", "agent_reports", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_reports_run_id", table_name="agent_reports")
    op.drop_table("agent_reports")

    op.drop_index("ix_data_snapshots_target_id", table_name="data_snapshots")
    op.drop_index("ix_data_snapshots_run_id", table_name="data_snapshots")
    op.drop_table("data_snapshots")

    op.drop_index("ix_analysis_runs_target_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")

