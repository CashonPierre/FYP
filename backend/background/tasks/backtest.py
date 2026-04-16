# STL
import sys
import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import cast

# External
from celery import Task
from sqlalchemy import select, and_

# Custom
from background.celery_app import celery_worker
from database.make_db import SessionLocal
from database.models import BacktestRun, RunMetrics, Trade, OhlcBar
from configs import get_logger

ENGINE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'trading_engine')

logger = get_logger()


def _strategy_from_graph(graph: dict):
  """
  Parse a builder graph JSON and return an engine strategy instance.

  Graph format:
    nodes: [{id, type, position, data: {param: value, ...}}]
    edges: [{id, source, target, source_handle, target_handle}]

  Supported patterns (MVP):
    OnBar → Buy   →  DCA(buyframe=1, buy_amount=<Buy.data.amount>)

  Falls back to DCA(buyframe=1, buy_amount=10) for any unrecognised graph.
  """
  # Import here — ENGINE_PATH must already be on sys.path when called from run_backtest
  from strategies.dca import DCA

  nodes = {n["id"]: n for n in graph.get("nodes", [])}
  edges = graph.get("edges", [])

  # Build adjacency: source_id → list of target node dicts
  adjacency: dict[str, list[dict]] = {}
  for edge in edges:
    src = edge.get("source")
    tgt = edge.get("target")
    if src and tgt and tgt in nodes:
      adjacency.setdefault(src, []).append(nodes[tgt])

  # Find OnBar → Buy path
  for node in nodes.values():
    if node.get("type") != "OnBar":
      continue
    for target in adjacency.get(node["id"], []):
      if target.get("type") == "Buy":
        buy_amount = float(target.get("data", {}).get("amount", 10))
        logger.info("graph parser: OnBar→Buy detected, buy_amount=%s", buy_amount)
        return DCA(buyframe=1, buy_amount=buy_amount)

  # Fallback
  logger.warning("graph parser: no recognised pattern, falling back to DCA(buyframe=1, buy_amount=10)")
  return DCA(buyframe=1, buy_amount=10)


@celery_worker.task(bind=True, max_retries=0)
def run_backtest(self: Task, run_id: str) -> None:
  # Import engine here so the path insert happens before any engine module loads
  if ENGINE_PATH not in sys.path:
    sys.path.insert(0, ENGINE_PATH)

  from core.engine import Engine
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

    if not symbol:
      raise ValueError("No symbol provided in backtest settings")

    # --- 3. Fetch OHLC data from DB ---
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

    bars: list[OhlcBar] = list(session.execute(stmt).scalars().all())

    if not bars:
      raise ValueError(f"No market data found for {symbol} ({timeframe})")

    # --- 4. Set up engine ---
    engine = Engine(initial_cash=initial_capital)

    graph = settings.get("graph", {})
    strategy = _strategy_from_graph(graph)
    engine.add_strategy(strategy)

    # Push market data events
    for bar in bars:
      # Engine uses YYYYMMDD int timestamps
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

    # --- 5. Run the engine ---
    engine.run()

    # --- 6. Extract results ---
    portfolio = engine._portfolio
    metrics = portfolio.get_trading_metrics()
    engine_trades = portfolio._trades
    final_capital = portfolio.current_capital
    total_return = portfolio.total_return / 100  # convert % to decimal

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

    # --- 9. Mark completed ---
    run.status = "completed"
    run.ended_at = datetime.now(timezone.utc)
    session.commit()
    logger.info(f"Backtest {run_id} completed successfully")

  except Exception as e:
    logger.error(f"Backtest {run_id} failed: {e}")
    try:
      run.status = "failed"
      run.error_message = str(e)
      run.ended_at = datetime.now(timezone.utc)
      session.commit()
    except Exception:
      session.rollback()
    raise

  finally:
    session.close()


run_backtest_task: Task = cast(Task, run_backtest)
