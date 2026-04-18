"""add sortino and calmar to run_metrics

Revision ID: d8c4e2f1a9b6
Revises: c4d92f1a7b05
Create Date: 2026-04-19 04:30:00.000000

Adds nullable `sortino` and `calmar` columns to `run_metrics` so the
perf-metrics helper can persist everything it derives from the equity
curve (previously Sharpe + max_drawdown were the only ratios stored,
and both were sourced from the engine's `TradingMetrics` which leaves
them `None`).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8c4e2f1a9b6"
down_revision: Union[str, None] = "c4d92f1a7b05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column(
    "run_metrics",
    sa.Column("sortino", sa.Float(), nullable=True),
  )
  op.add_column(
    "run_metrics",
    sa.Column("calmar", sa.Float(), nullable=True),
  )


def downgrade() -> None:
  op.drop_column("run_metrics", "calmar")
  op.drop_column("run_metrics", "sortino")
