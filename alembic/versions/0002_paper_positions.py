"""paper trading positions

Revision ID: 0002_paper_positions
Revises: 0001_initial_schema
Create Date: 2026-06-12 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_paper_positions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_positions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("run_id", sa.String(length=32), nullable=True),
        sa.Column("ticker", sa.String(length=24), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("invested_amount", sa.Float(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_price", sa.Float(), nullable=True),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
    )
    op.create_index("ix_paper_positions_run_id", "paper_positions", ["run_id"])
    op.create_index("ix_paper_positions_ticker", "paper_positions", ["ticker"])
    op.create_index("ix_paper_positions_status", "paper_positions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_paper_positions_status", table_name="paper_positions")
    op.drop_index("ix_paper_positions_ticker", table_name="paper_positions")
    op.drop_index("ix_paper_positions_run_id", table_name="paper_positions")
    op.drop_table("paper_positions")
