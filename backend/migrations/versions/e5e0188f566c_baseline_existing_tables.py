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
    conn = op.get_bind()

    # users table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID NOT NULL,
            username VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            is_verified BOOLEAN NOT NULL,
            PRIMARY KEY (id)
        )
    """))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))

    # ohlc_bars hypertable
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ohlc_bars (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL DEFAULT '1D',
            time TIMESTAMPTZ NOT NULL,
            open FLOAT NOT NULL,
            high FLOAT NOT NULL,
            low FLOAT NOT NULL,
            close FLOAT NOT NULL,
            volume BIGINT,
            PRIMARY KEY (symbol, timeframe, time)
        )
    """))
    conn.execute(sa.text("SELECT create_hypertable('ohlc_bars', 'time', if_not_exists => TRUE)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ohlc_bars_time_idx ON ohlc_bars (time DESC)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_ohlc_bars_symbol_time_desc ON ohlc_bars (symbol, timeframe, time DESC)"))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ohlc_bars_symbol_time_desc")
    op.execute("DROP INDEX IF EXISTS ohlc_bars_time_idx")
    op.drop_table('ohlc_bars')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
