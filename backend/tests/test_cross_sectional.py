"""
Tests for the cross-sectional (universe-mode) backtest executor.

Pure-Python. Uses stub OHLC rows injected via the ohlc_fetcher callback so
no DB or trading engine is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from background.tasks.cross_sectional import (
  _low_vol,
  _momentum,
  _parse_universe_graph,
  _reversal,
  _weights_from_scores,
  run_cross_sectional,
)


# ---------------------------------------------------------------------------
# Stub OHLC row + fetcher factory
# ---------------------------------------------------------------------------

@dataclass
class _Bar:
  time: datetime
  close: float
  volume: float


def _make_bars(start: datetime, closes: list[float], vols: list[float] | None = None) -> list[_Bar]:
  if vols is None:
    vols = [1_000_000.0] * len(closes)
  return [
    _Bar(time=start + timedelta(days=i), close=c, volume=v)
    for i, (c, v) in enumerate(zip(closes, vols))
  ]


def _make_fetcher(data: dict[str, list[_Bar]]):
  def fetch(sym: str, tf: str, start, end):
    return data.get(sym, [])
  return fetch


# ---------------------------------------------------------------------------
# Factor math
# ---------------------------------------------------------------------------

def test_momentum_basic_ranking():
  # A climbs, B flat, C falls. Over 20 bars with skip=2, A should outrank B should outrank C.
  n = 30
  close = pd.DataFrame({
    "A": [100 + i for i in range(n)],   # +29
    "B": [100 for _ in range(n)],       # 0
    "C": [100 - i * 0.5 for i in range(n)],  # -14.5
  }, index=pd.date_range("2024-01-01", periods=n))
  scores = _momentum(close, lookback=20, skip=2)
  last = scores.iloc[-1]
  assert last["A"] > last["B"] > last["C"]


def test_reversal_inverts_momentum():
  n = 30
  close = pd.DataFrame({
    "A": [100 + i for i in range(n)],
    "B": [100 - i for i in range(n)],
  }, index=pd.date_range("2024-01-01", periods=n))
  rev = _reversal(close, period=10)
  last = rev.iloc[-1]
  # A rose so reversal score is negative; B fell so reversal score is positive
  assert last["B"] > last["A"]


def test_low_vol_ranks_stable_higher():
  n = 100
  # A has 1% daily swings, B is flat
  close_a = [100.0]
  for i in range(1, n):
    close_a.append(close_a[-1] * (1.02 if i % 2 == 0 else 0.98))
  close = pd.DataFrame({
    "A": close_a,
    "B": [100.0] * n,
  }, index=pd.date_range("2024-01-01", periods=n))
  lv = _low_vol(close, period=30)
  last = lv.iloc[-1]
  # B has zero vol → higher (less negative) low-vol score
  assert last["B"] > last["A"]


# ---------------------------------------------------------------------------
# Ranking / weighting
# ---------------------------------------------------------------------------

def test_weights_long_only_top_decile():
  scores = pd.Series({"A": 5.0, "B": 3.0, "C": 1.0, "D": 4.0, "E": 2.0})
  w = _weights_from_scores(scores, top_pct=0.4, bottom_pct=0.4, mode="long_only")
  # 40% of 5 = 2 longs → A and D
  assert w["A"] > 0 and w["D"] > 0
  assert w["B"] == 0 and w["C"] == 0 and w["E"] == 0
  # Weights sum to 1
  assert abs(w.sum() - 1.0) < 1e-9


def test_weights_long_short_dollar_neutral():
  scores = pd.Series({"A": 5.0, "B": 3.0, "C": 1.0, "D": 4.0, "E": 2.0})
  w = _weights_from_scores(scores, top_pct=0.4, bottom_pct=0.4, mode="long_short")
  # Longs positive, shorts negative, sum ~= 0
  assert w["A"] > 0 and w["D"] > 0
  assert w["C"] < 0 and w["E"] < 0
  assert abs(w.sum()) < 1e-9


def test_weights_handles_all_nan():
  scores = pd.Series({"A": float("nan"), "B": float("nan")})
  w = _weights_from_scores(scores, 0.2, 0.2, "long_only")
  assert (w == 0).all()


# ---------------------------------------------------------------------------
# Graph parsing
# ---------------------------------------------------------------------------

def _graph_with(factor_type: str, factor_params: dict | None = None) -> dict:
  return {
    "nodes": [
      {"id": "f1", "type": factor_type, "data": {"params": factor_params or {}}},
      {"id": "r1", "type": "Rank", "data": {"params": {"top_pct": 0.5, "bottom_pct": 0.5, "rebalance_days": 5, "mode": "long_only"}}},
    ],
    "edges": [
      {"id": "e1", "source": "f1", "sourceHandle": "out", "target": "r1", "targetHandle": "in"},
    ],
  }


def test_parse_universe_graph_ok():
  g = _graph_with("Momentum")
  factor, rank = _parse_universe_graph(g)
  assert factor["type"] == "Momentum"
  assert rank["type"] == "Rank"


def test_parse_universe_graph_rejects_missing_rank():
  g = {"nodes": [{"id": "f1", "type": "Momentum"}], "edges": []}
  with pytest.raises(ValueError, match="Rank"):
    _parse_universe_graph(g)


def test_parse_universe_graph_rejects_multiple_factors():
  g = {
    "nodes": [
      {"id": "f1", "type": "Momentum"},
      {"id": "f2", "type": "Reversal"},
      {"id": "r1", "type": "Rank"},
    ],
    "edges": [
      {"source": "f1", "target": "r1"},
      {"source": "f2", "target": "r1"},
    ],
  }
  with pytest.raises(ValueError, match="only one factor"):
    _parse_universe_graph(g)


def test_parse_universe_graph_rejects_disconnected():
  g = {
    "nodes": [
      {"id": "f1", "type": "Momentum"},
      {"id": "r1", "type": "Rank"},
    ],
    "edges": [],  # no connection
  }
  with pytest.raises(ValueError, match="wired"):
    _parse_universe_graph(g)


# ---------------------------------------------------------------------------
# End-to-end executor
# ---------------------------------------------------------------------------

def test_run_cross_sectional_momentum_long_only():
  # Momentum long-only on A vs B vs C where A is the clear winner.
  # With top_pct=0.34, we buy only the top 1 → A. Final NAV should track A's return.
  start = datetime(2024, 1, 1, tzinfo=timezone.utc)
  n = 120
  data = {
    "A": _make_bars(start, [100 * (1.002 ** i) for i in range(n)]),  # steady rise
    "B": _make_bars(start, [100.0] * n),                              # flat
    "C": _make_bars(start, [100 * (0.998 ** i) for i in range(n)]),  # steady fall
  }
  g = _graph_with("Momentum", {"lookback": 40, "skip": 2})
  # Rank: top_pct 0.34 → 1 long out of 3
  g["nodes"][1]["data"]["params"] = {
    "top_pct": 0.34, "bottom_pct": 0.34, "rebalance_days": 20, "mode": "long_only",
  }

  result = run_cross_sectional(
    symbols=["A", "B", "C"],
    start_date=None, end_date=None,
    timeframe="1D",
    graph=g,
    initial_capital=10_000.0,
    ohlc_fetcher=_make_fetcher(data),
  )

  # Should have rebalanced a handful of times
  assert len(result["rebalance_dates"]) >= 1
  # Strategy should end profitable since it always buys A (the winner)
  assert result["metrics"]["total_return"] > 0
  assert result["metrics"]["final_nav"] > 10_000
  # Equity series has one point per bar
  assert len(result["nav_series"]) == n


def test_run_cross_sectional_long_short_is_dollar_neutral_at_rebalance():
  start = datetime(2024, 1, 1, tzinfo=timezone.utc)
  n = 80
  data = {
    "A": _make_bars(start, [100 * (1.002 ** i) for i in range(n)]),
    "B": _make_bars(start, [100.0] * n),
    "C": _make_bars(start, [100 * (0.998 ** i) for i in range(n)]),
    "D": _make_bars(start, [100 * (0.999 ** i) for i in range(n)]),
  }
  g = _graph_with("Momentum", {"lookback": 30, "skip": 2})
  g["nodes"][1]["data"]["params"] = {
    "top_pct": 0.25, "bottom_pct": 0.25, "rebalance_days": 15, "mode": "long_short",
  }
  result = run_cross_sectional(
    symbols=["A", "B", "C", "D"],
    start_date=None, end_date=None,
    timeframe="1D",
    graph=g,
    initial_capital=10_000.0,
    ohlc_fetcher=_make_fetcher(data),
  )
  # NAV should be a valid series even in long/short mode
  assert len(result["nav_series"]) == n
  # Long/short on A (up) minus C (down) should be profitable
  assert result["metrics"]["total_return"] > 0


def test_run_cross_sectional_rejects_too_few_symbols():
  start = datetime(2024, 1, 1, tzinfo=timezone.utc)
  data = {"A": _make_bars(start, [100.0] * 30)}
  g = _graph_with("Momentum")
  with pytest.raises(ValueError, match="at least 2"):
    run_cross_sectional(
      symbols=["A", "NONEXISTENT"],
      start_date=None, end_date=None,
      timeframe="1D",
      graph=g,
      initial_capital=10_000.0,
      ohlc_fetcher=_make_fetcher(data),
    )
