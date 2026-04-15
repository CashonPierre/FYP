# STL
import uuid
import json

# External
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

# Custom
from database.make_db import get_session
from database.models import BacktestRun, RunMetrics, Trade, OhlcBar
from api.auth.dependencies import get_current_user
from api.auth.schemas import CurrentUser
from api.auth.repositories import get_user_by_email
from app_common.exceptions import NotFoundError
from .schemas import (
  BacktestCreate,
  BacktestSubmitted,
  BacktestStatus,
  BacktestResults,
  BacktestListItem,
  ResultSummary,
  ResultSeries,
  OhlcPoint,
  EquityPoint,
  TradePoint,
)
from background.tasks import run_backtest_task
from .repositories import (
  create_backtest_run,
  get_run_by_id,
  get_runs_by_user,
  get_metrics_by_run,
  get_trades_by_run,
)

backtest_router = APIRouter(prefix="/backtests", tags=["Backtest endpoints"])


@backtest_router.post(
  path="",
  response_model=BacktestSubmitted,
  status_code=status.HTTP_201_CREATED,
)
def submit_backtest(
  payload: BacktestCreate,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> BacktestSubmitted:
  """Submit a new backtest job."""
  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  settings_json = payload.model_dump()
  run = create_backtest_run(
    session=session,
    user_id=user.id,
    settings_json=settings_json,
  )

  # Enqueue backtest in background
  run_backtest_task.delay(str(run.id))

  return BacktestSubmitted(id=run.id, status=run.status)


@backtest_router.get(
  path="",
  response_model=list[BacktestListItem],
  status_code=status.HTTP_200_OK,
)
def list_backtests(
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> list[BacktestListItem]:
  """List all backtest runs for the current user."""
  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  runs: list[BacktestRun] = get_runs_by_user(session=session, user_id=user.id)

  result = []
  for run in runs:
    settings = json.loads(run.settings_json)
    metrics = get_metrics_by_run(session=session, run_id=run.id)
    result.append(BacktestListItem(
      id=run.id,
      status=run.status,
      symbol=settings.get("settings", {}).get("symbol", ""),
      timeframe=settings.get("settings", {}).get("timeframe", "1D"),
      created_at=run.created_at,
      total_return=metrics.total_return if metrics else None,
    ))

  return result


@backtest_router.get(
  path="/{run_id}/status",
  response_model=BacktestStatus,
  status_code=status.HTTP_200_OK,
)
def get_backtest_status(
  run_id: uuid.UUID,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> BacktestStatus:
  """Get the status of a backtest run."""
  run: BacktestRun | None = get_run_by_id(session=session, run_id=run_id)
  if not run:
    raise NotFoundError(message="Backtest run not found")

  return BacktestStatus(
    id=run.id,
    status=run.status,
    started_at=run.started_at,
    ended_at=run.ended_at,
    error_message=run.error_message,
  )


@backtest_router.get(
  path="/{run_id}/results",
  response_model=BacktestResults,
  status_code=status.HTTP_200_OK,
)
def get_backtest_results(
  run_id: uuid.UUID,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> BacktestResults:
  """Get the full results of a completed backtest run."""
  run: BacktestRun | None = get_run_by_id(session=session, run_id=run_id)
  if not run:
    raise NotFoundError(message="Backtest run not found")

  if run.status != "completed":
    return BacktestResults(id=run.id, status=run.status)

  metrics: RunMetrics | None = get_metrics_by_run(session=session, run_id=run_id)
  trades: list[Trade] = get_trades_by_run(session=session, run_id=run_id)

  summary = None
  if metrics:
    summary = ResultSummary(
      initial_capital=metrics.initial_capital,
      final_nav=metrics.final_nav,
      total_return=metrics.total_return,
      annualized_return=metrics.annualized_return,
      max_drawdown=metrics.max_drawdown,
      volatility=metrics.volatility,
      sharpe=metrics.sharpe,
      total_trades=metrics.total_trades,
      win_rate=metrics.win_rate,
      fees=metrics.fees,
      slippage=metrics.slippage,
    )

  trade_points = [
    TradePoint(
      time=t.time.isoformat(),
      side=t.side,
      price=t.price,
      quantity=t.quantity,
      symbol=t.symbol,
    )
    for t in trades
  ]

  # Fetch OHLC data for the symbol/timeframe used in this run
  settings = json.loads(run.settings_json)
  run_settings = settings.get("settings", {})
  symbol = run_settings.get("symbol", "")
  timeframe = run_settings.get("timeframe", "1D")
  start_date = run_settings.get("start_date")
  end_date = run_settings.get("end_date")

  from sqlalchemy import select, and_
  stmt = select(OhlcBar).where(
    and_(
      OhlcBar.symbol == symbol,
      OhlcBar.timeframe == timeframe,
    )
  )
  if start_date:
    stmt = stmt.where(OhlcBar.time >= start_date)
  if end_date:
    stmt = stmt.where(OhlcBar.time <= end_date)
  stmt = stmt.order_by(OhlcBar.time)

  ohlc_rows = list(session.execute(stmt).scalars().all())
  ohlc_points = [
    OhlcPoint(
      time=row.time.isoformat(),
      open=row.open,
      high=row.high,
      low=row.low,
      close=row.close,
      volume=row.volume,
    )
    for row in ohlc_rows
  ]

  return BacktestResults(
    id=run.id,
    status=run.status,
    summary=summary,
    series=ResultSeries(
      ohlc=ohlc_points,
      trades=trade_points,
      equity=[],  # TODO: populate from equity_curve table once implemented
    ),
  )
