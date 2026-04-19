"""
Unit tests for the portfolio perf-metrics helper.

All inputs are small deterministic NAV series; values are either
hand-computed or obviously correct for edge cases (empty, single-point,
monotone-rising, all-flat).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from background.tasks._perf_metrics import compute


def _mk(navs: list[float]) -> list[tuple[datetime, float]]:
  """Build a list of (daily timestamps, nav) starting 2024-01-02."""
  t0 = datetime(2024, 1, 2, tzinfo=timezone.utc)
  return [(t0 + timedelta(days=i), v) for i, v in enumerate(navs)]


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------

def test_empty_equity_returns_zero_total_and_nones():
  m = compute(equity=[], initial_capital=10_000.0)
  assert m.total_return == 0.0
  assert m.annualized_return is None
  assert m.volatility is None
  assert m.sharpe is None
  assert m.sortino is None
  assert m.max_drawdown is None
  assert m.calmar is None


def test_single_point_returns_none_ratios():
  m = compute(equity=_mk([10_000]), initial_capital=10_000.0)
  assert m.total_return == 0.0
  assert m.annualized_return is None
  assert m.volatility is None
  assert m.sharpe is None
  assert m.sortino is None
  # One-point curve has no prior peak to measure drawdown against.
  assert m.max_drawdown is None


def test_all_flat_curve_has_zero_return_nan_free_stats():
  m = compute(equity=_mk([10_000] * 10), initial_capital=10_000.0)
  assert m.total_return == 0.0
  # Flat ⇒ CAGR = 0, vol = 0, sharpe undefined (vol = 0)
  assert m.annualized_return == 0.0
  assert m.volatility == 0.0
  assert m.sharpe is None
  # No negative returns → Sortino undefined
  assert m.sortino is None
  assert m.max_drawdown == 0.0
  # max_dd == 0 ⇒ calmar undefined (division by zero avoided)
  assert m.calmar is None


def test_monotone_rising_has_no_drawdown_and_positive_stats():
  navs = [10_000 * (1.001 ** i) for i in range(50)]  # +0.1% per bar
  m = compute(equity=_mk(navs), initial_capital=10_000.0)
  assert m.max_drawdown == 0.0
  assert m.total_return > 0
  assert m.annualized_return is not None and m.annualized_return > 0
  assert m.volatility is not None and m.volatility >= 0
  # All positive returns → Sortino undefined (no negative samples)
  assert m.sortino is None
  # Calmar needs negative drawdown
  assert m.calmar is None


# ---------------------------------------------------------------------------
# Hand-computed case: simple +10%, -5% two-step path
# ---------------------------------------------------------------------------

def test_hand_computed_two_step_path():
  """NAV: 100 → 110 → 104.5 (ratios: +0.10, -0.05).

  Using bars_per_year=252 for annualisation:

    mean(r)   = (0.10 + -0.05) / 2 = 0.025
    sample σ = sqrt(((0.10-0.025)² + (-0.05-0.025)²) / 1)
             = sqrt((0.075² + 0.075²))
             = sqrt(2) * 0.075  ≈ 0.1060660171779821
    vol_ann   = σ * sqrt(252)   ≈ 1.683...
    sharpe    = (0.025 * 252) / 1.6833...  ≈ 3.7443...
    total_return = 104.5 / 100 - 1 = 0.045
    ann_return   = (104.5 / 100) ** (252 / 2) - 1  (huge because of short series)
    max_dd = 104.5/110 - 1 = -0.05
  """
  equity = _mk([100, 110, 104.5])
  m = compute(equity=equity, initial_capital=100.0)

  assert abs(m.total_return - 0.045) < 1e-9

  # Max drawdown: single drawdown from 110 to 104.5
  assert m.max_drawdown is not None
  assert abs(m.max_drawdown - (-0.05)) < 1e-9

  # Vol (annualised)
  expected_sigma = math.sqrt(2) * 0.075
  expected_vol_ann = expected_sigma * math.sqrt(252)
  assert m.volatility is not None
  assert abs(m.volatility - expected_vol_ann) < 1e-9

  # Sharpe
  mean_r = 0.025
  expected_sharpe = (mean_r * 252) / expected_vol_ann
  assert m.sharpe is not None
  assert abs(m.sharpe - expected_sharpe) < 1e-9

  # Annualised return
  expected_ann = (104.5 / 100) ** (252 / 2) - 1
  assert m.annualized_return is not None
  assert abs(m.annualized_return - expected_ann) < 1e-9

  # Calmar: ann_return / |max_dd|
  expected_calmar = expected_ann / 0.05
  assert m.calmar is not None
  assert abs(m.calmar - expected_calmar) < 1e-6


# ---------------------------------------------------------------------------
# Drawdown through a deeper trough than the final-bar drawdown
# ---------------------------------------------------------------------------

def test_max_drawdown_tracks_peak_not_final_bar():
  # NAV peaks at 120 then dips to 90 before recovering to 110.
  equity = _mk([100, 120, 90, 110])
  m = compute(equity=equity, initial_capital=100.0)
  # Drawdown = 90/120 - 1 = -0.25, not 110/120 - 1 = -0.0833
  assert m.max_drawdown is not None
  assert abs(m.max_drawdown - (-0.25)) < 1e-9


def test_max_drawdown_clamped_when_nav_goes_negative(caplog):
  # Defensive clamp: if an upstream accounting bug lets NAV go below zero
  # (as happened before the engine cash-clamp fix), the raw math would
  # produce drawdowns worse than -100%. Cap at -1.0 so the UI never
  # displays nonsense like "-199%", and log a warning so the real bug
  # is still visible in server logs.
  equity = _mk([100, 80, -50, 20])
  m = compute(equity=equity, initial_capital=100.0)
  assert m.max_drawdown == -1.0
  assert any("below -100%" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Profitable run with mixed returns must produce a positive Sortino
# ---------------------------------------------------------------------------

def test_sortino_positive_on_profitable_mixed_path():
  # Up 2%, down 1%, up 3%, down 0.5% — net positive with some downside.
  ratios = [1.02, 0.99, 1.03, 0.995]
  nav = 100.0
  series = [100.0]
  for r in ratios:
    nav *= r
    series.append(nav)

  m = compute(equity=_mk(series), initial_capital=100.0)
  assert m.sortino is not None
  assert m.sortino > 0
  # Sanity: sharpe should also be positive on this clearly-profitable run
  assert m.sharpe is not None and m.sharpe > 0


# ---------------------------------------------------------------------------
# Losing run produces negative Sharpe (regression guard for sign bugs)
# ---------------------------------------------------------------------------

def test_sharpe_negative_on_losing_run():
  # Down 1%, down 2%, down 1.5% over three bars.
  ratios = [0.99, 0.98, 0.985]
  nav = 100.0
  series = [nav]
  for r in ratios:
    nav *= r
    series.append(nav)

  m = compute(equity=_mk(series), initial_capital=100.0)
  assert m.sharpe is not None
  assert m.sharpe < 0


# ---------------------------------------------------------------------------
# Zero initial capital should not divide by zero
# ---------------------------------------------------------------------------

def test_zero_initial_capital_safe():
  m = compute(equity=_mk([0.0, 50, 80]), initial_capital=0.0)
  assert m.total_return == 0.0  # clamped
  # CAGR base is 0 → None
  assert m.annualized_return is None
  assert m.calmar is None


# ---------------------------------------------------------------------------
# Weekly timeframe — bars_per_year=52 flows through to annualisation
# ---------------------------------------------------------------------------

def test_bars_per_year_affects_annualisation():
  navs = [100, 105, 103, 108]
  daily = compute(_mk(navs), initial_capital=100.0, bars_per_year=252)
  weekly = compute(_mk(navs), initial_capital=100.0, bars_per_year=52)

  # Same returns → same relative shape but different annualised scales.
  assert daily.volatility is not None and weekly.volatility is not None
  assert daily.volatility > weekly.volatility

  assert daily.annualized_return is not None
  assert weekly.annualized_return is not None
  # Short series + huge annualisation factor pushes daily CAGR above weekly
  assert daily.annualized_return > weekly.annualized_return
