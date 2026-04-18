"""add_equity_points

Revision ID: 3a1f7c9b2e04
Revises: 216897ee6c5a
Create Date: 2026-04-18 03:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a1f7c9b2e04'
down_revision: Union[str, None] = '216897ee6c5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'equity_points',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('equity', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ['run_id'], ['backtest_runs.id'],
            name='fk_equity_points_run_id',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_equity_points_run_id'),
        'equity_points',
        ['run_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_equity_points_run_id'), table_name='equity_points')
    op.drop_table('equity_points')
