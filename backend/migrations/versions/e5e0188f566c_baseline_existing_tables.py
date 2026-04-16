"""baseline_existing_tables

Revision ID: e5e0188f566c
Revises:
Create Date: 2026-04-13 16:49:41.807047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5e0188f566c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table (existed before migrations were introduced)
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Create ohlc_bars hypertable (existed before migrations were introduced)
    # TimescaleDB requires create_hypertable to be called after table creation,
    # but that requires the timescaledb extension. We use plain SQL here.
    op.create_table(
        'ohlc_bars',
        sa.Column('symbol', sa.Text(), nullable=False),
        sa.Column('timeframe', sa.Text(), nullable=False, server_default='1D'),
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('symbol', 'timeframe', 'time'),
    )
    op.execute("SELECT create_hypertable('ohlc_bars', 'time', if_not_exists => TRUE)")
    op.execute("CREATE INDEX ohlc_bars_time_idx ON ohlc_bars (time DESC)")
    op.execute("CREATE INDEX idx_ohlc_bars_symbol_time_desc ON ohlc_bars (symbol, timeframe, time DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ohlc_bars_symbol_time_desc")
    op.execute("DROP INDEX IF EXISTS ohlc_bars_time_idx")
    op.drop_table('ohlc_bars')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
