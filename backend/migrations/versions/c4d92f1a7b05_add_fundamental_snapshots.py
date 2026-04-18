"""add_fundamental_snapshots

Revision ID: c4d92f1a7b05
Revises: 7b9d4e2c8a31
Create Date: 2026-04-19 02:30:00.000000

Adds `fundamental_snapshots` for company fundamentals at a quarterly cadence.
PK is (symbol, period_end). `available_from` = period_end + 45d (SEC filing
lag) is indexed so strategy queries can efficiently filter to point-in-time
rows during backtest.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d92f1a7b05"
down_revision: Union[str, None] = "7b9d4e2c8a31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "fundamental_snapshots",
    sa.Column("symbol", sa.String(length=32), nullable=False),
    sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
    sa.Column("available_from", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revenue", sa.Float(), nullable=True),
    sa.Column("net_income", sa.Float(), nullable=True),
    sa.Column("diluted_eps", sa.Float(), nullable=True),
    sa.Column("total_assets", sa.Float(), nullable=True),
    sa.Column("total_equity", sa.Float(), nullable=True),
    sa.Column("total_debt", sa.Float(), nullable=True),
    sa.Column("shares_outstanding", sa.BigInteger(), nullable=True),
    sa.Column("dividend_per_share", sa.Float(), nullable=True),
    sa.Column("roe", sa.Float(), nullable=True),
    sa.Column("debt_to_equity", sa.Float(), nullable=True),
    sa.Column("profit_margin", sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint("symbol", "period_end"),
  )
  op.create_index(
    op.f("ix_fundamental_snapshots_available_from"),
    "fundamental_snapshots",
    ["available_from"],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index(
    op.f("ix_fundamental_snapshots_available_from"),
    table_name="fundamental_snapshots",
  )
  op.drop_table("fundamental_snapshots")
