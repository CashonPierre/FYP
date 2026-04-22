"""
Cross-sectional (universe-mode) backtest executor.

Runs ONE portfolio over N symbols instead of N independent backtests. The
graph must contain exactly one Rank node connected to exactly one factor
node (Momentum / Reversal / LowVol / Liquidity). At each rebalance bar the
universe is ranked by the factor score and portfolio weights are rebuilt:

  long_only   →  +1/k on the top decile, 0 elsewhere
  long_short  →  +1/k on the top decile, -1/k on the bottom decile (dollar-neutral)

Daily NAV evolves with the held weights between rebalances. Results land in
the same RunMetrics + EquityPoint tables the single-symbol path uses, so the
existing /backtests/{id}/results endpoint serves them without changes.
"""

from __future__ import annotations

# STL
import json
import math
import uuid
from datetime import datetime, timezone
from typing import cast

# External
import numpy as np
import pandas as pd
from celery import Task
from sqlalchemy import select, and_

# Custom
from background.celery_app import celery_worker
from configs import get_logger
from database.make_db import SessionLocal
from database.models import BacktestRun, EquityPoint, FundamentalSnapshot, OhlcBar, RunMetrics

logger = get_logger()


# ---------------------------------------------------------------------------
# Factor computations — each returns a DataFrame (dates × symbols) of scores
# ---------------------------------------------------------------------------

def _momentum(close: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
  """Trailing (lookback..skip) return per symbol. Higher = rank higher."""
  # close[t−skip] / close[t−lookback] − 1
  numer = close.shift(skip)
  denom = close.shift(lookback)
  return (numer / denom) - 1.0


def _reversal(close: pd.DataFrame, period: int = 21) -> pd.DataFrame:
  """Negated trailing return — buy losers, short winners (Jegadeesh 1990)."""
  return -((close / close.shift(period)) - 1.0)


def _low_vol(close: pd.DataFrame, period: int = 63) -> pd.DataFrame:
  """Negated realized vol of daily returns. Higher (= less volatile) ranks higher."""
  rets = close.pct_change()
  return -rets.rolling(window=period).std()


def _liquidity(close: pd.DataFrame, volume: pd.DataFrame, period: int = 60) -> pd.DataFrame:
  """Average daily dollar volume. Higher = more liquid = rank higher."""
  dv = close * volume
  return dv.rolling(window=period).mean()


def _value(close: pd.DataFrame, ttm_eps: pd.DataFrame) -> pd.DataFrame:
  """
  Value factor = earnings yield (TTM EPS / price). Higher = cheaper (low P/E)
  = rank higher. Cleaner than 1/PE because it handles zero or negative EPS
  without blowing up — negative earnings simply rank lowest (correctly).
  """
  aligned = ttm_eps.reindex_like(close).ffill()
  return aligned / close.replace({0: np.nan})


def _build_ttm_eps_df(
  fundamentals_fetcher,
  symbols: list[str],
  bar_index: pd.DatetimeIndex,
) -> pd.DataFrame:
  """
  Build a (dates × symbols) DataFrame of TTM EPS, point-in-time using
  available_from (period_end + 45d) so no look-ahead bias. Forward-fills
  onto the bar_index so the most recent known value is used between
  filings. Missing symbols are NaN columns (they'll rank last, correctly).
  """
  tz = bar_index.tz
  bar_idx_naive = bar_index.tz_convert("UTC").tz_localize(None) if tz is not None else bar_index

  per_symbol: dict[str, pd.Series] = {}
  for sym in symbols:
    rows = fundamentals_fetcher(sym)
    if not rows:
      per_symbol[sym] = pd.Series(dtype=float, index=bar_idx_naive)
      continue
    rows = sorted(rows, key=lambda r: r.period_end)
    eps_values: list[float | None] = []
    avail_dates: list[pd.Timestamp] = []
    for r in rows:
      eps = float(r.diluted_eps) if r.diluted_eps is not None else None
      eps_values.append(eps)
      af = r.available_from if r.available_from is not None else r.period_end
      avail_dates.append(pd.Timestamp(af))

    quarterly = pd.Series(eps_values, index=pd.DatetimeIndex(avail_dates))
    # Normalize index tz to naive to match bar_idx_naive
    if quarterly.index.tz is not None:
      quarterly.index = quarterly.index.tz_convert("UTC").tz_localize(None)
    # Dedupe duplicate available_from labels. Restated filings, tz
    # normalization collapsing close timestamps, or two reports for the
    # same period can all produce duplicates. `ttm.reindex(...)` later
    # blows up with "cannot reindex on an axis with duplicate labels"
    # otherwise. Rows were sorted by period_end above, so keep="last"
    # wins the latest restatement (correct point-in-time semantics).
    quarterly = quarterly[~quarterly.index.duplicated(keep="last")].sort_index()
    ttm = quarterly.rolling(window=4, min_periods=1).sum()

    union = quarterly.index.union(bar_idx_naive).sort_values()
    per_symbol[sym] = ttm.reindex(union).ffill().reindex(bar_idx_naive)

  df = pd.DataFrame(per_symbol)
  df.index = bar_index  # restore tz-aware index to match close
  return df


# ---------------------------------------------------------------------------
# Graph parsing
# ---------------------------------------------------------------------------

_FACTOR_TYPES = frozenset({"Momentum", "Reversal", "LowVol", "Liquidity", "Value"})


def _node_param(node: dict, key: str, default):
  data = node.get("data", {}) or {}
  data_params = data.get("params", {}) or {}
  flat_params = node.get("params", {}) or {}
  return data_params.get(key, data.get(key, flat_params.get(key, default)))


def _parse_universe_graph(graph: dict) -> tuple[dict, dict]:
  """
  Validate the graph topology and return (factor_node, rank_node).

  Raises ValueError with a human-readable message on any topology problem.
  """
  nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("id")}
  edges = graph.get("edges", [])

  rank_nodes = [n for n in nodes.values() if n.get("type") == "Rank"]
  factor_nodes = [n for n in nodes.values() if n.get("type") in _FACTOR_TYPES]

  if len(rank_nodes) == 0:
    raise ValueError("Universe mode requires a Rank node")
  if len(rank_nodes) > 1:
    raise ValueError("Universe mode supports only one Rank node")
  if len(factor_nodes) == 0:
    raise ValueError("Universe mode requires a factor node (Momentum, Reversal, LowVol, Liquidity)")
  if len(factor_nodes) > 1:
    raise ValueError("Universe mode supports only one factor node")

  rank_node = rank_nodes[0]
  factor_node = factor_nodes[0]

  # Confirm the factor feeds the rank node
  connected = False
  for e in edges:
    src = e.get("source", "")
    tgt = e.get("target", "")
    if src == factor_node["id"] and tgt == rank_node["id"]:
      connected = True
      break
  if not connected:
    raise ValueError("Factor node output must be wired to the Rank node's input")

  return factor_node, rank_node


# ---------------------------------------------------------------------------
# Ranking → weights
# ---------------------------------------------------------------------------

def _weights_from_scores(
  scores: pd.Series,
  top_pct: float,
  bottom_pct: float,
  mode: str,
) -> pd.Series:
  """
  scores: index = symbols, values = factor score (NaN allowed)
  returns: weights Series aligned to the same index, summing to 1 (long_only)
           or 0 (long_short, dollar-neutral).
  """
  valid = scores.dropna()
  if valid.empty:
    return pd.Series(0.0, index=scores.index)

  n = len(valid)
  top_k = max(1, int(round(n * top_pct)))
  bot_k = max(1, int(round(n * bottom_pct)))

  sorted_desc = valid.sort_values(ascending=False)
  long_symbols = sorted_desc.head(top_k).index
  short_symbols = sorted_desc.tail(bot_k).index

  w = pd.Series(0.0, index=scores.index)
  if mode == "long_only":
    w[long_symbols] = 1.0 / top_k
  elif mode == "long_short":
    w[long_symbols] = 0.5 / top_k
    w[short_symbols] = -0.5 / bot_k
  else:
    raise ValueError(f"Unknown rank mode: {mode}")
  return w


# ---------------------------------------------------------------------------
# Metrics from NAV series
# ---------------------------------------------------------------------------

def _compute_metrics(
  nav_series: pd.Series,
  initial_capital: float,
) -> dict:
  """Compute summary metrics from a dated NAV Series."""
  if nav_series.empty:
    return {
      "final_nav": initial_capital,
      "total_return": 0.0,
      "annualized_return": None,
      "max_drawdown": None,
      "volatility": None,
      "sharpe": None,
    }

  final_nav = float(nav_series.iloc[-1])
  total_return = final_nav / initial_capital - 1.0

  # Annualize using 252 trading days
  n_days = len(nav_series)
  if n_days > 1:
    years = n_days / 252.0
    annualized_return = (final_nav / initial_capital) ** (1.0 / years) - 1.0 if years > 0 else None
  else:
    annualized_return = None

  # Daily returns
  rets = nav_series.pct_change().dropna()
  if len(rets) > 1:
    volatility = float(rets.std() * math.sqrt(252))
    mean_daily = float(rets.mean())
    sharpe = float((mean_daily * 252) / (rets.std() * math.sqrt(252))) if rets.std() > 0 else None
  else:
    volatility = None
    sharpe = None

  # Max drawdown from running peak
  running_max = nav_series.cummax()
  dd = (nav_series / running_max) - 1.0
  max_drawdown = float(dd.min())

  return {
    "final_nav": final_nav,
    "total_return": float(total_return),
    "annualized_return": float(annualized_return) if annualized_return is not None else None,
    "max_drawdown": max_drawdown,
    "volatility": volatility,
    "sharpe": sharpe,
  }


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

def run_cross_sectional(
  symbols: list[str],
  start_date: str | None,
  end_date: str | None,
  timeframe: str,
  graph: dict,
  initial_capital: float,
  ohlc_fetcher,
  fundamentals_fetcher=None,
) -> dict:
  """
  Pure-function executor — callable from the Celery task AND from unit tests
  (which inject a fake ohlc_fetcher).

  ohlc_fetcher(symbol, timeframe, start, end) must return a list of objects
  with .time, .close, .volume attributes (OhlcBar rows from the DB or stubs).

  Returns dict with keys:
    nav_series    : pd.Series (date → NAV)
    rebalance_dates: list[pd.Timestamp]
    metrics       : dict (see _compute_metrics)
    factor_label  : str (e.g. "Momentum(252,21)")
  """
  factor_node, rank_node = _parse_universe_graph(graph)

  # --- Load OHLC for all symbols into aligned DataFrames ---
  close_dict: dict[str, pd.Series] = {}
  volume_dict: dict[str, pd.Series] = {}
  for sym in symbols:
    bars = ohlc_fetcher(sym, timeframe, start_date, end_date)
    if not bars:
      continue
    idx = pd.DatetimeIndex([b.time for b in bars])
    close_dict[sym] = pd.Series([float(b.close) for b in bars], index=idx)
    volume_dict[sym] = pd.Series([float(b.volume or 0) for b in bars], index=idx)

  if len(close_dict) < 2:
    raise ValueError(
      f"Universe mode requires market data for at least 2 symbols "
      f"(got {len(close_dict)} of {len(symbols)}). "
      f"Run the data refresh pipeline for missing symbols."
    )

  close = pd.DataFrame(close_dict).sort_index()
  volume = pd.DataFrame(volume_dict).sort_index()

  # Drop any date that has no data at all; forward-fill within-symbol gaps so
  # a missing bar for one stock doesn't kill the rebalance.
  close = close.dropna(how="all").ffill()
  volume = volume.dropna(how="all").ffill()

  # --- Compute factor scores ---
  ftype = factor_node.get("type")
  if ftype == "Momentum":
    lookback = int(_node_param(factor_node, "lookback", 252))
    skip = int(_node_param(factor_node, "skip", 21))
    scores = _momentum(close, lookback=lookback, skip=skip)
    factor_label = f"Momentum({lookback},{skip})"
  elif ftype == "Reversal":
    period = int(_node_param(factor_node, "period", 21))
    scores = _reversal(close, period=period)
    factor_label = f"Reversal({period})"
  elif ftype == "LowVol":
    period = int(_node_param(factor_node, "period", 63))
    scores = _low_vol(close, period=period)
    factor_label = f"LowVol({period})"
  elif ftype == "Liquidity":
    period = int(_node_param(factor_node, "period", 60))
    scores = _liquidity(close, volume, period=period)
    factor_label = f"Liquidity({period})"
  elif ftype == "Value":
    if fundamentals_fetcher is None:
      raise ValueError("Value factor requires a fundamentals_fetcher")
    ttm_eps = _build_ttm_eps_df(fundamentals_fetcher, list(close.columns), close.index)
    scores = _value(close, ttm_eps)
    factor_label = "Value (earnings yield)"
  else:
    raise ValueError(f"Unsupported factor type: {ftype}")

  # --- Rank node config ---
  top_pct = float(_node_param(rank_node, "top_pct", 0.2))
  bottom_pct = float(_node_param(rank_node, "bottom_pct", 0.2))
  rebalance_days = int(_node_param(rank_node, "rebalance_days", 21))
  mode = str(_node_param(rank_node, "mode", "long_only"))

  if top_pct <= 0 or top_pct > 1 or bottom_pct <= 0 or bottom_pct > 1:
    raise ValueError("top_pct / bottom_pct must be in (0, 1]")
  if rebalance_days < 1:
    raise ValueError("rebalance_days must be >= 1")
  if mode not in ("long_only", "long_short"):
    raise ValueError(f"mode must be 'long_only' or 'long_short' (got {mode})")

  # --- NAV loop ---
  dates = close.index
  daily_rets = close.pct_change().fillna(0.0)

  weights = pd.Series(0.0, index=close.columns)
  nav = initial_capital
  nav_values: list[float] = []
  rebalance_dates: list[pd.Timestamp] = []

  for i, date in enumerate(dates):
    # Rebalance BEFORE computing the day's return (weights apply to today's move)
    if i % rebalance_days == 0:
      if date in scores.index:
        row = scores.loc[date]
        # Only use symbols that had a valid score today
        weights = _weights_from_scores(row, top_pct, bottom_pct, mode)
        if weights.abs().sum() > 0:
          rebalance_dates.append(date)

    # Apply today's return under current weights
    if i > 0:
      port_ret = float((weights * daily_rets.loc[date]).sum())
      nav = nav * (1.0 + port_ret)
    nav_values.append(nav)

  nav_series = pd.Series(nav_values, index=dates)
  metrics = _compute_metrics(nav_series, initial_capital)

  return {
    "nav_series": nav_series,
    "rebalance_dates": rebalance_dates,
    "metrics": metrics,
    "factor_label": factor_label,
  }


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_worker.task(bind=True, max_retries=0)
def run_universe_backtest(self: Task, run_id: str) -> None:
  session = SessionLocal()
  try:
    run: BacktestRun | None = session.execute(
      select(BacktestRun).where(BacktestRun.id == uuid.UUID(run_id))
    ).scalar_one_or_none()

    if not run:
      logger.error(f"BacktestRun {run_id} not found")
      return

    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    session.commit()

    settings = json.loads(run.settings_json)
    run_settings = settings.get("settings", {})
    symbols: list[str] = run_settings.get("symbols") or []
    timeframe: str = run_settings.get("timeframe", "1D")
    start_date = run_settings.get("start_date")
    end_date = run_settings.get("end_date")
    initial_capital: float = float(run_settings.get("initial_capital", 10000.0))
    graph: dict = settings.get("graph", {})

    if not symbols:
      raise ValueError("No symbols provided for universe backtest")

    def ohlc_fetcher(sym: str, tf: str, start, end):
      stmt = select(OhlcBar).where(
        and_(OhlcBar.symbol == sym, OhlcBar.timeframe == tf)
      )
      if start:
        stmt = stmt.where(OhlcBar.time >= start)
      if end:
        stmt = stmt.where(OhlcBar.time <= end)
      stmt = stmt.order_by(OhlcBar.time)
      return list(session.execute(stmt).scalars().all())

    def fundamentals_fetcher(sym: str):
      stmt = select(FundamentalSnapshot).where(
        FundamentalSnapshot.symbol == sym
      ).order_by(FundamentalSnapshot.period_end)
      return list(session.execute(stmt).scalars().all())

    result = run_cross_sectional(
      symbols=symbols,
      start_date=start_date,
      end_date=end_date,
      timeframe=timeframe,
      graph=graph,
      initial_capital=initial_capital,
      ohlc_fetcher=ohlc_fetcher,
      fundamentals_fetcher=fundamentals_fetcher,
    )

    nav_series: pd.Series = result["nav_series"]
    rebalance_dates: list = result["rebalance_dates"]
    m = result["metrics"]

    session.add(RunMetrics(
      run_id=run.id,
      initial_capital=initial_capital,
      final_nav=m["final_nav"],
      total_return=m["total_return"],
      annualized_return=m["annualized_return"],
      max_drawdown=m["max_drawdown"],
      volatility=m["volatility"],
      sharpe=m["sharpe"],
      total_trades=len(rebalance_dates),
      win_rate=None,
      fees=0.0,
      slippage=0.0,
    ))

    session.bulk_save_objects([
      EquityPoint(run_id=run.id, time=ts.to_pydatetime(), equity=float(nav))
      for ts, nav in nav_series.items()
    ])

    run.status = "completed"
    run.ended_at = datetime.now(timezone.utc)
    session.commit()
    logger.info(f"Universe backtest {run_id} completed ({len(symbols)} symbols)")

    if run.batch_id:
      from api.backtests.repositories import update_batch_status_from_runs
      update_batch_status_from_runs(session, run.batch_id)
      session.commit()

  except Exception as e:
    logger.error(f"Universe backtest {run_id} failed: {e}")
    try:
      run.status = "failed"
      run.error_message = str(e)
      run.ended_at = datetime.now(timezone.utc)
      session.commit()
      if run.batch_id:
        from api.backtests.repositories import update_batch_status_from_runs
        update_batch_status_from_runs(session, run.batch_id)
        session.commit()
    except Exception:
      session.rollback()
    raise

  finally:
    session.close()


run_universe_backtest_task: Task = cast(Task, run_universe_backtest)
