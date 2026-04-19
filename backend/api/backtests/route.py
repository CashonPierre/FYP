# STL
import uuid
import json

# External
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

# Custom
from database.make_db import get_session
from database.models import BacktestRun, BacktestBatch, RunMetrics, Trade, OhlcBar, EquityPoint as EquityPointModel, UserDataset
from api.auth.dependencies import get_current_user
from api.auth.schemas import CurrentUser
from api.auth.repositories import get_user_by_email
from api.market.universes import get_universe_symbols
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
  BatchStatus,
  BatchRunSummary,
  BatchAggregate,
)
from background.tasks import run_backtest_batch_task, run_universe_backtest_task
from .repositories import (
  create_batch,
  create_backtest_run,
  get_batch_by_id,
  get_run_by_id,
  get_runs_by_batch,
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
  """Submit a new backtest job (single or multi-symbol)."""
  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  # --- BYOD path: one run against a user-uploaded dataset, no fan-out ---
  if payload.settings.dataset_id:
    dataset = session.get(UserDataset, payload.settings.dataset_id)
    if not dataset or dataset.user_id != user.id:
      raise NotFoundError(message="Dataset not found")
    base_settings = payload.model_dump(mode="json")
    # Pin the concrete symbol so list/results endpoints can label the run.
    base_settings["settings"]["symbol"] = dataset.symbol
    base_settings["settings"]["timeframe"] = dataset.timeframe
    run = create_backtest_run(
      session=session,
      user_id=user.id,
      settings_json=base_settings,
      batch_id=None,
    )
    session.commit()

    # Dispatch the single-run task directly — no batch wrapper needed.
    from background.tasks import run_backtest_task
    run_backtest_task.delay(str(run.id))

    return BacktestSubmitted(id=run.id, status="queued")

  # --- Resolve symbol list ---
  if payload.universe:
    try:
      symbols = get_universe_symbols(payload.universe)
    except KeyError:
      from fastapi import HTTPException
      raise HTTPException(status_code=400, detail=f"Unknown universe: {payload.universe}")
  elif payload.symbols:
    symbols = payload.symbols
  else:
    symbols = [payload.settings.symbol]  # type: ignore[list-item]

  execution_mode = payload.settings.execution_mode

  # --- Universe mode: ONE cross-sectional run over the whole symbol list ---
  if execution_mode == "universe":
    if len(symbols) < 2:
      from fastapi import HTTPException
      raise HTTPException(
        status_code=400,
        detail="Universe mode requires at least 2 symbols",
      )

    base_settings = payload.model_dump()
    # Keep the full symbol list inside run.settings so the executor can read it
    base_settings["settings"]["symbols"] = symbols
    batch = create_batch(
      session=session,
      user_id=user.id,
      symbols=symbols,
      settings_json=base_settings,
    )
    run = create_backtest_run(
      session=session,
      user_id=user.id,
      settings_json=base_settings,
      batch_id=batch.id,
    )
    session.commit()
    run_universe_backtest_task.delay(str(run.id))

    return BacktestSubmitted(
      id=run.id,
      status="queued",
      batch_id=batch.id,
      run_ids=[run.id],
    )

  # --- Single / multi-symbol: one run per symbol (existing fan-out path) ---
  base_settings = payload.model_dump()
  batch = create_batch(
    session=session,
    user_id=user.id,
    symbols=symbols,
    settings_json=base_settings,
  )

  runs: list[BacktestRun] = []
  for sym in symbols:
    # Each run gets its own settings with the concrete symbol
    run_settings = json.loads(json.dumps(base_settings))  # deep copy
    run_settings["settings"]["symbol"] = sym
    run = create_backtest_run(
      session=session,
      user_id=user.id,
      settings_json=run_settings,
      batch_id=batch.id,
    )
    runs.append(run)

  session.commit()

  # Dispatch single batch task — it fans out run_backtest per child run
  run_backtest_batch_task.delay(str(batch.id))

  is_multi = len(symbols) > 1
  return BacktestSubmitted(
    id=batch.id if is_multi else runs[0].id,
    status="queued",
    batch_id=batch.id,
    run_ids=[r.id for r in runs] if is_multi else [],
  )


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
      batch_id=run.batch_id,
    ))

  return result


@backtest_router.get(
  path="/status",
  response_model=list[BacktestStatus],
  status_code=status.HTTP_200_OK,
)
def get_backtest_statuses_batch(
  ids: str,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> list[BacktestStatus]:
  """Batch status endpoint: `GET /backtests/status?ids=a,b,c`.

  Returns status records for every requested id in one DB round trip.
  Used by the sweep page so polling 15-36 runs doesn't fan out into
  15-36 parallel requests every 2s (which exhausted the connection pool).
  Unknown or unauthorised ids are silently skipped.
  """
  from sqlalchemy import select

  run_ids: list[uuid.UUID] = []
  for tok in (ids or "").split(","):
    tok = tok.strip()
    if not tok:
      continue
    try:
      run_ids.append(uuid.UUID(tok))
    except ValueError:
      continue  # ignore junk, don't 400 the whole batch

  if not run_ids:
    return []

  # Cap to prevent pathological query sizes (current UI cap: 36 runs per sweep)
  run_ids = run_ids[:64]

  rows = session.execute(
    select(BacktestRun).where(BacktestRun.id.in_(run_ids))
  ).scalars().all()

  return [
    BacktestStatus(
      id=r.id,
      status=r.status,
      started_at=r.started_at,
      ended_at=r.ended_at,
      error_message=r.error_message,
    )
    for r in rows
  ]


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
      sortino=metrics.sortino,
      calmar=metrics.calmar,
      total_trades=metrics.total_trades,
      win_rate=metrics.win_rate,
      fees=metrics.fees,
      slippage=metrics.slippage,
    )

  trade_points = [
    TradePoint(
      id=str(t.id),
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

  equity_stmt = (
    select(EquityPointModel)
    .where(EquityPointModel.run_id == run.id)
    .order_by(EquityPointModel.time)
  )
  equity_points = [
    EquityPoint(time=row.time.isoformat(), equity=row.equity)
    for row in session.execute(equity_stmt).scalars().all()
  ]

  strategy_name: str | None = None
  if run.strategy_id is not None:
    from database.models import Strategy
    strat = session.get(Strategy, run.strategy_id)
    if strat is not None:
      strategy_name = strat.name

  return BacktestResults(
    id=run.id,
    status=run.status,
    symbol=symbol or None,
    timeframe=timeframe or None,
    start_date=start_date or None,
    end_date=end_date or None,
    strategy_name=strategy_name,
    summary=summary,
    series=ResultSeries(
      ohlc=ohlc_points,
      trades=trade_points,
      equity=equity_points,
    ),
  )


@backtest_router.get(
  path="/batch/{batch_id}",
  response_model=BatchStatus,
  status_code=status.HTTP_200_OK,
)
def get_batch_status(
  batch_id: uuid.UUID,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> BatchStatus:
  """Get status and per-symbol results for a multi-asset batch."""
  batch: BacktestBatch | None = get_batch_by_id(session=session, batch_id=batch_id)
  if not batch:
    raise NotFoundError(message="Backtest batch not found")

  runs = get_runs_by_batch(session=session, batch_id=batch_id)
  symbols = json.loads(batch.symbols_json)

  run_summaries: list[BatchRunSummary] = []
  returns: list[float] = []

  for run in runs:
    run_settings = json.loads(run.settings_json)
    sym = run_settings.get("settings", {}).get("symbol", "")
    metrics = get_metrics_by_run(session=session, run_id=run.id)

    total_return = metrics.total_return if metrics else None
    if total_return is not None:
      returns.append(total_return)

    run_summaries.append(BatchRunSummary(
      run_id=run.id,
      symbol=sym,
      status=run.status,
      total_return=total_return,
      max_drawdown=metrics.max_drawdown if metrics else None,
      sharpe=metrics.sharpe if metrics else None,
      total_trades=metrics.total_trades if metrics else None,
      error_message=run.error_message,
    ))

  # Aggregate stats
  status_counts = {"completed": 0, "failed": 0, "running": 0, "queued": 0}
  for r in run_summaries:
    key = r.status if r.status in status_counts else "queued"
    status_counts[key] += 1

  best_run = max(run_summaries, key=lambda r: r.total_return or float("-inf"), default=None)
  worst_run = min(run_summaries, key=lambda r: r.total_return or float("inf"), default=None)

  aggregate = BatchAggregate(
    total_symbols=len(symbols),
    completed=status_counts["completed"],
    failed=status_counts["failed"],
    running=status_counts["running"],
    queued=status_counts["queued"],
    best_symbol=best_run.symbol if best_run and best_run.total_return is not None else None,
    best_return=best_run.total_return if best_run else None,
    worst_symbol=worst_run.symbol if worst_run and worst_run.total_return is not None else None,
    worst_return=worst_run.total_return if worst_run else None,
    avg_return=sum(returns) / len(returns) if returns else None,
  )

  return BatchStatus(
    id=batch.id,
    status=batch.status,
    symbols=symbols,
    runs=run_summaries,
    aggregate=aggregate,
    created_at=batch.created_at,
    started_at=batch.started_at,
    ended_at=batch.ended_at,
  )
