"""add_user_datasets_and_user_ohlc_bars

Revision ID: 7b9d4e2c8a31
Revises: 3a1f7c9b2e04
Create Date: 2026-04-19 01:00:00.000000

Adds two tables for the BYOD (bring-your-own-data) feature:
  - user_datasets   : logical container (name, symbol, timeframe) per upload
  - user_ohlc_bars  : bars keyed by (dataset_id, time); TimescaleDB hypertable

The hypertable conversion is wrapped in a DO block so this migration remains
compatible with plain PostgreSQL (used by unit tests) where the timescaledb
extension is absent.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b9d4e2c8a31"
down_revision: Union[str, None] = "3a1f7c9b2e04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "user_datasets",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("name", sa.String(length=64), nullable=False),
    sa.Column("symbol", sa.String(length=32), nullable=False),
    sa.Column("timeframe", sa.String(length=8), nullable=False),
    sa.Column("rows_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("first_bar", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_bar", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
      "created_at",
      sa.DateTime(timezone=True),
      nullable=False,
      server_default=sa.text("now()"),
    ),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_datasets_user_id"),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("user_id", "name", name="uq_user_datasets_user_name"),
  )
  op.create_index(
    op.f("ix_user_datasets_user_id"), "user_datasets", ["user_id"], unique=False
  )

  op.create_table(
    "user_ohlc_bars",
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("time", sa.DateTime(timezone=True), nullable=False),
    sa.Column("open", sa.Float(), nullable=False),
    sa.Column("high", sa.Float(), nullable=False),
    sa.Column("low", sa.Float(), nullable=False),
    sa.Column("close", sa.Float(), nullable=False),
    sa.Column("volume", sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(
      ["dataset_id"], ["user_datasets.id"],
      name="fk_user_ohlc_bars_dataset_id", ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("dataset_id", "time"),
  )
  op.create_index(
    op.f("ix_user_ohlc_bars_time"), "user_ohlc_bars", ["time"], unique=False
  )

  # Convert to Timescale hypertable on `time` when the extension is available.
  # Guarded so SQLite/plain-Postgres test environments don't fail.
  op.execute(
    """
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
          'user_ohlc_bars', 'time',
          chunk_time_interval => INTERVAL '30 days',
          if_not_exists => TRUE
        );
      END IF;
    END$$;
    """
  )


def downgrade() -> None:
  op.drop_index(op.f("ix_user_ohlc_bars_time"), table_name="user_ohlc_bars")
  op.drop_table("user_ohlc_bars")
  op.drop_index(op.f("ix_user_datasets_user_id"), table_name="user_datasets")
  op.drop_table("user_datasets")
