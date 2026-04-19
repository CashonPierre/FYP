# STL
import sys
import os
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import cast

# External
from celery import Task
from sqlalchemy import func, select, and_

# Custom
from background.celery_app import celery_worker
from database.make_db import SessionLocal
from database.models import BacktestRun, RunMetrics, Trade, OhlcBar, EquityPoint, UserDataset, UserOhlcBar
from configs import get_logger

ENGINE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'trading_engine')

logger = get_logger()


def _parse_date(value, fallback: datetime) -> datetime:
  """Best-effort parse of a settings date (ISO string or already-a-datetime).
  Falls back to `fallback` on any failure."""
  if not value:
    return fallback
  try:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
  except ValueError:
    return fallback
  if dt.tzinfo is None:
    dt = dt.replace(tzinfo=timezone.utc)
  return dt


def _auto_refresh_if_needed(
  symbol: str,
  timeframe: str,
  start_date,
  end_date,
) -> None:
  """Ensure DB covers the requested [start_date, end_date] window for this
  symbol/timeframe; fetch via the configured OHLC source if either end is
  missing.

  Branches:
    - No bars at all                         → full fetch (start_date → today)
    - Earliest bar is AFTER start_date       → re-fetch from start_date
    - Latest bar is >1 day behind end_date   → incremental tail fetch
    - Otherwise                              → skip

  Best-effort: failures are logged and swallowed so the run can still
  proceed against whatever data exists.
  """
  from background.tasks.market_refresh import _TF_MAP
  from background.tasks.ohlc_dispatch import fetch_and_upsert_any

  if timeframe not in _TF_MAP:
    return  # not a refresh-pipeline timeframe (e.g. "5m")

  session = SessionLocal()
  try:
    row = session.execute(
      select(
        func.min(OhlcBar.time),
        func.max(OhlcBar.time),
      ).where(
        OhlcBar.symbol == symbol,
        OhlcBar.timeframe == timeframe,
      )
    ).one()
    earliest, latest = row[0], row[1]
  finally:
    session.close()

  # SQLite stores naive datetimes; Postgres returns aware. Normalise so
  # comparisons below don't blow up in either environment.
  if earliest is not None and earliest.tzinfo is None:
    earliest = earliest.replace(tzinfo=timezone.utc)
  if latest is not None and latest.tzinfo is None:
    latest = latest.replace(tzinfo=timezone.utc)

  today_utc = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
  )

  # Cap target_end at today — no source can return future bars.
  target_end = min(_parse_date(end_date, today_utc), today_utc)
  # target_start is only used to force a backfill when requested window
  # starts earlier than what we have.
  target_start = _parse_date(start_date, None)  # type: ignore[arg-type]

  tail_stale = latest is None or latest < target_end - timedelta(days=1)
  head_missing = (
    target_start is not None
    and earliest is not None
    and earliest > target_start
  )
  completely_missing = latest is None

  if not (tail_stale or head_missing or completely_missing):
    return

  # Force a full-range fetch when the head is missing; otherwise let
  # fetch_and_upsert resume incrementally from latest.
  force_start: str | None = None
  if completely_missing or head_missing:
    force_start = (
      target_start.strftime("%Y-%m-%d") if target_start else None
    )

  try:
    logger.info(
      "auto-refresh: %s %s — earliest=%s latest=%s target=[%s→%s] start=%s",
      symbol, timeframe, earliest, latest, target_start, target_end, force_start,
    )
    fetch_and_upsert_any(symbol=symbol, timeframe=timeframe, start=force_start)
  except Exception as exc:
    logger.warning(
      "auto-refresh %s %s failed: %s — proceeding with existing data",
      symbol, timeframe, exc,
    )


class _BarRow:
  """Minimal duck-typed OHLC row used when loading UserOhlcBar rows.

  Lets the downstream loop treat user-uploaded bars and preset OhlcBar rows
  identically (same attribute access pattern).
  """
  __slots__ = ("symbol", "time", "open", "high", "low", "close", "volume")

  def __init__(self, *, symbol, time, open, high, low, close, volume):
    self.symbol = symbol
    self.time = time
    self.open = open
    self.high = high
    self.low = low
    self.close = close
    self.volume = volume


def _strategy_from_graph(graph: dict, ohlcv_df=None):
  """
  Parse a builder graph JSON and return a GraphStrategy instance.

  When ohlcv_df is provided (a pandas DataFrame with open/high/low/close/volume
  columns), indicator series are precomputed with pandas_ta upfront so that
  on_event performs O(1) lookups instead of incremental rolling calculations.

  Falls back to DCA(buyframe=1, buy_amount=10) if the graph is empty or
  unparseable, so existing tests and integrations keep working.
  """
  from background.tasks.graph_strategy import GraphStrategy
  from strategies.dca import DCA

  nodes = graph.get("nodes", [])
  if not nodes:
    logger.warning("graph parser: empty graph, falling back to DCA default")
    return DCA(buyframe=1, buy_amount=10)

  logger.info("graph parser: building GraphStrategy (%d nodes, %d edges, precompute=%s)",
              len(nodes), len(graph.get("edges", [])), ohlcv_df is not None)
  return GraphStrategy(graph, ohlcv_df=ohlcv_df)


def _make_engine(initial_cash: float):
  """
  Return a patched Engine that handles CloseSignal(order_id=None).

  The engine's default close_position(symbol, order_id=None) calls
  positions.pop(None) which always returns None, so positions are never
  closed and portfolio._trades stays empty.

  This subclass falls back to close_positions() (close all open positions
  for the symbol) whenever order_id is None.
  """
  if ENGINE_PATH not in sys.path:
    sys.path.insert(0, ENGINE_PATH)

  from core.engine import Engine
  from events.event import MarketDataEvent
  from strategies.signal import CloseSignal

  class _PatchedEngine(Engine):
    def _run_strategies(self, event):
      for signal in self._strategy_handler.run_all_strategy(event=event):
        if isinstance(signal, CloseSignal) and isinstance(event, MarketDataEvent):
          if signal.order_id is None:
            # Close ALL open positions for this symbol (handles order_id=None)
            closed_list = self._positionManager.close_positions(
              symbol=event.payload.symbol
            )
            for closed in closed_list:
              self._portfolio.add_trade(
                order_fill=closed,
                current_price=event.payload.price,
                exit_timestamp=self._clock.now,
              )
          else:
            closed = self._positionManager.close_position(
              symbol=event.payload.symbol,
              order_id=signal.order_id,
            )
            if closed:
              self._portfolio.add_trade(
                order_fill=closed,
                current_price=event.payload.price,
                exit_timestamp=self._clock.now,
              )
        else:
          self._orderManager.handle_signal(
            signal=signal, time=self._clock.now
          )

  return _PatchedEngine(initial_cash=initial_cash)


@celery_worker.task(bind=True, max_retries=0)
def run_backtest(self: Task, run_id: str) -> None:
  if ENGINE_PATH not in sys.path:
    sys.path.insert(0, ENGINE_PATH)

  from events.event import MarketDataEvent
  from events.payloads.market_payload import MarketDataPayload

  session = SessionLocal()
  try:
    # --- 1. Load the run ---
    run: BacktestRun | None = session.execute(
      select(BacktestRun).where(BacktestRun.id == uuid.UUID(run_id))
    ).scalar_one_or_none()

    if not run:
      logger.error(f"BacktestRun {run_id} not found")
      return

    # Mark as running
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    session.commit()

    # --- 2. Parse settings ---
    settings = json.loads(run.settings_json)
    run_settings = settings.get("settings", {})
    symbol: str = run_settings.get("symbol", "")
    timeframe: str = run_settings.get("timeframe", "1D")
    start_date = run_settings.get("start_date")
    end_date = run_settings.get("end_date")
    initial_capital: float = float(run_settings.get("initial_capital", 10000.0))
    dataset_id_raw = run_settings.get("dataset_id")

    # --- 3. Fetch OHLC data from DB ---
    if dataset_id_raw:
      # BYOD path: load bars from user_ohlc_bars for this dataset.
      dataset = session.get(UserDataset, uuid.UUID(str(dataset_id_raw)))
      if not dataset or dataset.user_id != run.user_id:
        raise ValueError(f"Dataset {dataset_id_raw} not found or not owned by user")
      symbol = dataset.symbol
      timeframe = dataset.timeframe

      stmt = select(UserOhlcBar).where(UserOhlcBar.dataset_id == dataset.id)
      if start_date:
        stmt = stmt.where(UserOhlcBar.time >= start_date)
      if end_date:
        stmt = stmt.where(UserOhlcBar.time <= end_date)
      user_bars: list[UserOhlcBar] = list(
        session.execute(stmt.order_by(UserOhlcBar.time)).scalars().all()
      )
      if not user_bars:
        raise ValueError(f"No bars found in dataset {dataset.name!r}")
      # Normalise to a shape the downstream loop can consume uniformly.
      bars = [
        _BarRow(symbol=symbol, time=b.time, open=b.open, high=b.high,
                low=b.low, close=b.close, volume=b.volume)
        for b in user_bars
      ]
    else:
      if not symbol:
        raise ValueError("No symbol provided in backtest settings")

      # Auto-fetch from the configured OHLC source (FMP or yfinance) if DB
      # doesn't fully cover the requested [start_date, end_date] window.
      # Best-effort — failures are swallowed.
      _auto_refresh_if_needed(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
      )

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

      bars = list(session.execute(stmt).scalars().all())

      if not bars:
        raise ValueError(f"No market data found for {symbol} ({timeframe})")

    # --- 4. Set up engine ---
    engine = _make_engine(initial_cash=initial_capital)

    graph = settings.get("graph", {})

    # Build a DataFrame so GraphStrategy can precompute indicators with pandas_ta
    import pandas as pd
    ohlcv_df = pd.DataFrame({
      "open":   [b.open for b in bars],
      "high":   [b.high for b in bars],
      "low":    [b.low for b in bars],
      "close":  [b.close for b in bars],
      "volume": [b.volume or 0 for b in bars],
    })

    strategy = _strategy_from_graph(graph, ohlcv_df=ohlcv_df)
    engine.add_strategy(strategy)

    # Push market data events one bar at a time so we can snapshot the
    # portfolio NAV after each bar. NAV = realized capital + mark-to-market
    # value of any open positions; without the unrealized leg the curve stays
    # flat through any period the strategy is holding (a long-only strategy
    # with no exit would otherwise look like a straight line).
    equity_snapshots: list[tuple[datetime, float]] = []
    portfolio = engine._portfolio
    position_manager = engine._positionManager
    for bar in bars:
      ts = int(bar.time.strftime("%Y%m%d"))
      payload = MarketDataPayload(
        timestamp=ts,
        symbol=bar.symbol,
        price=bar.close,
        volume=bar.volume or 0,
        Open=bar.open,
        High=bar.high,
        Low=bar.low,
        Close=bar.close,
      )
      engine.push_event(MarketDataEvent(timestamp=ts, payload=payload))
      engine.run()
      nav = float(portfolio.current_capital) + float(
        position_manager.total_unrealized_pnl
      )
      equity_snapshots.append((bar.time, nav))

    # --- 6. Extract results ---
    metrics = portfolio.get_trading_metrics()
    engine_trades = portfolio._trades
    final_nav = float(portfolio.current_capital) + float(
      position_manager.total_unrealized_pnl
    )
    final_capital = final_nav
    total_return = (final_nav - initial_capital) / initial_capital if initial_capital else 0.0

    # --- 7. Store RunMetrics ---
    run_metrics = RunMetrics(
      run_id=run.id,
      initial_capital=initial_capital,
      final_nav=final_capital,
      total_return=total_return,
      max_drawdown=metrics.max_drawdown,
      sharpe=metrics.sharpe_ratio,
      total_trades=metrics.total_trades,
      win_rate=metrics.win_rate / 100 if metrics.win_rate else None,
      fees=0.0,
      slippage=0.0,
    )
    session.add(run_metrics)

    # --- 8. Store Trades ---
    # Each engine trade dict is a round-trip (entry + exit).
    # Store two rows: a BUY at entry_time and a SELL at exit_time
    # so the chart can show {B} and {S} markers separately.
    def _parse_ts(ts_int: int) -> datetime:
      try:
        return datetime.strptime(str(ts_int), "%Y%m%d").replace(tzinfo=timezone.utc)
      except ValueError:
        return datetime.now(timezone.utc)

    for t in engine_trades:
      qty = float(t.get("quantity", 0))
      sym = t.get("symbol", symbol)

      # Entry — BUY
      session.add(Trade(
        run_id=run.id,
        time=_parse_ts(t.get("entry_time", 0)),
        symbol=sym,
        side="buy",
        price=float(t.get("entry_price", 0)),
        quantity=qty,
        fee=float(t.get("commission", 0)),
        slippage=0.0,
      ))

      # Exit — SELL (only if position actually closed on a different bar)
      entry_ts = t.get("entry_time", 0)
      exit_ts = t.get("exit_time", 0)
      if exit_ts and exit_ts != entry_ts:
        session.add(Trade(
          run_id=run.id,
          time=_parse_ts(exit_ts),
          symbol=sym,
          side="sell",
          price=float(t.get("exit_price", 0)),
          quantity=qty,
          fee=0.0,
          slippage=0.0,
        ))

    # --- 9. Store EquityPoints (batch insert; one row per bar) ---
    if equity_snapshots:
      session.bulk_save_objects([
        EquityPoint(run_id=run.id, time=t, equity=eq)
        for t, eq in equity_snapshots
      ])

    # --- 10. Mark completed ---
    run.status = "completed"
    run.ended_at = datetime.now(timezone.utc)
    session.commit()
    logger.info(f"Backtest {run_id} completed successfully")

    # Update parent batch status if this run belongs to one
    if run.batch_id:
      _refresh_batch_status(session, run.batch_id)

  except Exception as e:
    logger.error(f"Backtest {run_id} failed: {e}")
    try:
      run.status = "failed"
      run.error_message = str(e)
      run.ended_at = datetime.now(timezone.utc)
      session.commit()
      if run.batch_id:
        _refresh_batch_status(session, run.batch_id)
    except Exception:
      session.rollback()
    raise

  finally:
    session.close()


def _refresh_batch_status(session, batch_id) -> None:
  """Wrapper to avoid circular import: import repositories at call time."""
  from api.backtests.repositories import update_batch_status_from_runs
  update_batch_status_from_runs(session, batch_id)
  session.commit()


@celery_worker.task(bind=True, max_retries=0)
def run_backtest_batch(self: Task, batch_id: str) -> None:
  """Mark the batch as running and fan out one run_backtest task per child run."""
  from api.backtests.repositories import get_batch_by_id, get_runs_by_batch

  session = SessionLocal()
  try:
    batch = get_batch_by_id(session, uuid.UUID(batch_id))
    if not batch:
      logger.error(f"BacktestBatch {batch_id} not found")
      return

    batch.status = "running"
    batch.started_at = datetime.now(timezone.utc)
    session.commit()

    runs = get_runs_by_batch(session, batch.id)
    for run in runs:
      run_backtest.delay(str(run.id))

    logger.info(f"BacktestBatch {batch_id} dispatched {len(runs)} run(s)")

  except Exception as e:
    logger.error(f"BacktestBatch {batch_id} failed to start: {e}")
    session.rollback()
    raise

  finally:
    session.close()


run_backtest_task: Task = cast(Task, run_backtest)
run_backtest_batch_task: Task = cast(Task, run_backtest_batch)
