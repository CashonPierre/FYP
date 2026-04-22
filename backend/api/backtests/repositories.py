# STL
import uuid
import json
from datetime import datetime, timezone

# External
from sqlalchemy.orm import Session
from sqlalchemy import select

# Custom
from database.models import BacktestRun, BacktestBatch, RunMetrics, Trade


def create_backtest_run(
  session: Session,
  user_id: uuid.UUID,
  settings_json: dict,
  batch_id: uuid.UUID | None = None,
) -> BacktestRun:
  run = BacktestRun(
    user_id=user_id,
    status="queued",
    settings_json=json.dumps(settings_json),
    batch_id=batch_id,
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


# ---------------------------------------------------------------------------
# Batch CRUD
# ---------------------------------------------------------------------------

def create_batch(
  session: Session,
  user_id: uuid.UUID,
  symbols: list[str],
  settings_json: dict,
) -> BacktestBatch:
  batch = BacktestBatch(
    user_id=user_id,
    status="queued",
    symbols_json=json.dumps(symbols),
    settings_json=json.dumps(settings_json),
  )
  session.add(batch)
  session.flush()
  return batch


def get_batch_by_id(session: Session, batch_id: uuid.UUID) -> BacktestBatch | None:
  return session.execute(
    select(BacktestBatch).where(BacktestBatch.id == batch_id)
  ).scalar_one_or_none()


def get_runs_by_batch(session: Session, batch_id: uuid.UUID) -> list[BacktestRun]:
  statement = (
    select(BacktestRun)
    .where(BacktestRun.batch_id == batch_id)
    .order_by(BacktestRun.created_at)
  )
  return list(session.execute(statement).scalars().all())


def get_batches_by_user(session: Session, user_id: uuid.UUID) -> list[BacktestBatch]:
  statement = (
    select(BacktestBatch)
    .where(BacktestBatch.user_id == user_id)
    .order_by(BacktestBatch.created_at.desc())
  )
  return list(session.execute(statement).scalars().all())


def update_batch_status_from_runs(session: Session, batch_id: uuid.UUID) -> None:
  """Recompute and persist batch status based on current child run statuses."""
  runs = get_runs_by_batch(session, batch_id)
  if not runs:
    return

  statuses = {r.status for r in runs}

  if statuses <= {"completed"}:
    new_status = "completed"
  elif statuses <= {"failed"}:
    new_status = "failed"
  elif "running" in statuses or "queued" in statuses:
    new_status = "running"
  else:
    # Mix of completed + failed
    new_status = "partial"

  batch = session.execute(
    select(BacktestBatch).where(BacktestBatch.id == batch_id)
  ).scalar_one_or_none()

  if not batch:
    return

  batch.status = new_status
  if new_status in ("completed", "failed", "partial"):
    if batch.ended_at is None:
      batch.ended_at = datetime.now(timezone.utc)
