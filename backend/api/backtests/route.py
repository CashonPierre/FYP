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
  BatchCombinedResults,
  BatchListItem,
)
from ._combine import combine_equity_curves
from background.tasks import run_backtest_batch_task, run_universe_backtest_task
from .repositories import (
  create_batch,
  create_backtest_run,
  get_batch_by_id,
  get_batches_by_user,
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
      # None for universe-mode runs; fan-out runs have a concrete symbol.
      symbol=settings.get("settings", {}).get("symbol"),
      timeframe=settings.get("settings", {}).get("timeframe", "1D"),
      created_at=run.created_at,
      total_return=metrics.total_return if metrics else None,
      batch_id=run.batch_id,
    ))

  return result


@backtest_router.get(
  path="/batches",
  response_model=list[BatchListItem],
  status_code=status.HTTP_200_OK,
)
def list_batches(
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> list[BatchListItem]:
  """List batch backtests for the current user — one row per batch, collapsing
  fan-out children into an aggregate summary (returns, completed/failed counts).

  History page uses this to avoid exploding a 20-symbol fan-out into 20 rows.
  For universe-mode batches the batch IS the portfolio (a single run over many
  symbols); `avg_return` is that run's total return.
  """
  from database.models import Strategy

  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  batches = get_batches_by_user(session=session, user_id=user.id)
  if not batches:
    return []

  result: list[BatchListItem] = []
  for batch in batches:
    symbols = json.loads(batch.symbols_json)
    batch_settings = json.loads(batch.settings_json)
    execution_mode = batch_settings.get("settings", {}).get("execution_mode")

    runs = get_runs_by_batch(session=session, batch_id=batch.id)
    completed = sum(1 for r in runs if r.status == "completed")
    failed = sum(1 for r in runs if r.status == "failed")

    returns: list[float] = []
    for run in runs:
      metrics = get_metrics_by_run(session=session, run_id=run.id)
      if metrics and metrics.total_return is not None:
        returns.append(metrics.total_return)
    avg_return = sum(returns) / len(returns) if returns else None

    strategy_name: str | None = None
    if batch.strategy_id is not None:
      strat = session.get(Strategy, batch.strategy_id)
      if strat is not None:
        strategy_name = strat.name

    result.append(BatchListItem(
      id=batch.id,
      status=batch.status,
      symbols=symbols,
      total_symbols=len(symbols),
      completed=completed,
      failed=failed,
      created_at=batch.created_at,
      ended_at=batch.ended_at,
      avg_return=avg_return,
      execution_mode=execution_mode,
      strategy_name=strategy_name,
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
    # None for universe-mode runs; single/multi fan-out runs inject a concrete symbol.
    sym = run_settings.get("settings", {}).get("symbol")
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


@backtest_router.get(
  path="/batch/{batch_id}/combined",
  response_model=BatchCombinedResults,
  status_code=status.HTTP_200_OK,
)
def get_batch_combined_results(
  batch_id: uuid.UUID,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> BatchCombinedResults:
  """Equal-weight portfolio view of a multi-symbol fan-out batch.

  Pools each completed child run's equity curve into a single NAV series
  with `initial_capital / N` allocated per symbol, then recomputes the
  portfolio-level metrics. Failed / incomplete runs are excluded from N.
  """
  from sqlalchemy import select
  from background.tasks._perf_metrics import compute as compute_metrics

  batch: BacktestBatch | None = get_batch_by_id(session=session, batch_id=batch_id)
  if not batch:
    raise NotFoundError(message="Backtest batch not found")

  batch_settings = json.loads(batch.settings_json)
  initial_capital = float(
    batch_settings.get("settings", {}).get("initial_capital", 10000.0)
  )

  runs = get_runs_by_batch(session=session, batch_id=batch_id)

  included_symbols: list[str] = []
  skipped_symbols: list[str] = []
  curves: list[list[tuple[object, float]]] = []

  for run in runs:
    run_settings = json.loads(run.settings_json)
    sym = run_settings.get("settings", {}).get("symbol") or ""
    if run.status != "completed":
      if sym:
        skipped_symbols.append(sym)
      continue

    stmt = (
      select(EquityPointModel)
      .where(EquityPointModel.run_id == run.id)
      .order_by(EquityPointModel.time)
    )
    points = [(p.time, p.equity) for p in session.execute(stmt).scalars().all()]
    if not points:
      if sym:
        skipped_symbols.append(sym)
      continue

    included_symbols.append(sym)
    curves.append(points)

  if not curves:
    return BatchCombinedResults(
      id=batch.id,
      status=batch.status,
      symbols=[],
      skipped_symbols=skipped_symbols,
      initial_capital=initial_capital,
      summary=None,
      equity=[],
    )

  combined = combine_equity_curves(curves, initial_capital)
  perf = compute_metrics(combined, initial_capital)

  # Aggregate trade count and fees/slippage by summing across included runs
  # — these are portfolio-level totals for the combined view.
  total_trades = 0
  total_fees = 0.0
  total_slippage = 0.0
  for run in runs:
    if run.status != "completed":
      continue
    m = get_metrics_by_run(session=session, run_id=run.id)
    if m is None:
      continue
    total_trades += m.total_trades or 0
    total_fees += m.fees or 0.0
    total_slippage += m.slippage or 0.0

  final_nav = combined[-1][1]
  summary = ResultSummary(
    initial_capital=initial_capital,
    final_nav=final_nav,
    total_return=perf.total_return,
    annualized_return=perf.annualized_return,
    max_drawdown=perf.max_drawdown,
    volatility=perf.volatility,
    sharpe=perf.sharpe,
    sortino=perf.sortino,
    calmar=perf.calmar,
    total_trades=total_trades,
    win_rate=None,  # can't aggregate without trade-level PnL
    fees=total_fees,
    slippage=total_slippage,
  )

  equity_points = [
    EquityPoint(time=t.isoformat(), equity=e) for t, e in combined
  ]

  return BatchCombinedResults(
    id=batch.id,
    status=batch.status,
    symbols=included_symbols,
    skipped_symbols=skipped_symbols,
    initial_capital=initial_capital,
    summary=summary,
    equity=equity_points,
  )
