# STL
import uuid
import json

# External
from sqlalchemy.orm import Session
from sqlalchemy import select

# Custom
from database.models import BacktestRun, RunMetrics, Trade


def create_backtest_run(
  session: Session,
  user_id: uuid.UUID,
  settings_json: dict,
) -> BacktestRun:
  run = BacktestRun(
    user_id=user_id,
    status="queued",
    settings_json=json.dumps(settings_json),
  )
  session.add(run)
  session.flush()  # get the ID without committing
  return run


def get_run_by_id(session: Session, run_id: uuid.UUID) -> BacktestRun | None:
  statement = select(BacktestRun).where(BacktestRun.id == run_id)
  return session.execute(statement).scalar_one_or_none()


def get_runs_by_user(session: Session, user_id: uuid.UUID) -> list[BacktestRun]:
  statement = (
    select(BacktestRun)
    .where(BacktestRun.user_id == user_id)
    .order_by(BacktestRun.created_at.desc())
  )
  return list(session.execute(statement).scalars().all())


def get_metrics_by_run(session: Session, run_id: uuid.UUID) -> RunMetrics | None:
  statement = select(RunMetrics).where(RunMetrics.run_id == run_id)
  return session.execute(statement).scalar_one_or_none()


def get_trades_by_run(session: Session, run_id: uuid.UUID) -> list[Trade]:
  statement = select(Trade).where(Trade.run_id == run_id).order_by(Trade.time)
  return list(session.execute(statement).scalars().all())
