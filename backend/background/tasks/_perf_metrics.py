"""Performance metrics computed from an equity curve.

Kept deliberately decoupled from `trading_engine` — the engine exposes
`TradingMetrics` with several fields unpopulated, so we recompute the
portfolio-level stats here using the bar-by-bar NAV series that
backtest.py already captures.

None is returned for any ratio when the denominator is zero or there
aren't enough data points; the helper never raises.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class PerformanceMetrics:
  total_return: float              # fraction, e.g. 0.25 = +25%
  annualized_return: float | None  # CAGR, fraction/year
  volatility: float | None         # annualised stdev of bar returns
  sharpe: float | None             # annualised, rf-adjusted
  sortino: float | None            # annualised, downside deviation
  max_drawdown: float | None       # negative fraction, e.g. -0.18 = -18%
  calmar: float | None             # annualised_return / |max_drawdown|


def _step_returns(equity: list[tuple[datetime, float]]) -> list[float]:
  """Return list of bar-to-bar returns: (nav[i] / nav[i-1]) - 1.

  Skips any step where the prior NAV is zero or negative — those can't
  produce a meaningful return and propagating inf/NaN into downstream
  stats is worse than dropping the step.
  """
  out: list[float] = []
  for i in range(1, len(equity)):
    prev = equity[i - 1][1]
    curr = equity[i][1]
    if prev <= 0:
      continue
    out.append(curr / prev - 1.0)
  return out


def _max_drawdown(equity: list[tuple[datetime, float]]) -> float | None:
  """Max peak-to-trough decline, as a negative fraction.

  Returns 0.0 for a monotone-rising curve, None for <2 points, and the
  most negative (nav / running_max - 1) otherwise.
  """
  if len(equity) < 2:
    return None
  peak = equity[0][1]
  worst = 0.0
  for _, nav in equity:
    if nav > peak:
      peak = nav
    if peak > 0:
      dd = nav / peak - 1.0
      if dd < worst:
        worst = dd
  return worst


def _stdev(xs: list[float], *, sample: bool = True) -> float | None:
  """Population or sample stdev; returns None for < 2 points (sample) or
  < 1 point (population)."""
  n = len(xs)
  if sample:
    if n < 2:
      return None
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return math.sqrt(var)
  if n < 1:
    return None
  mean = sum(xs) / n
  var = sum((x - mean) ** 2 for x in xs) / n
  return math.sqrt(var)


def compute(
  equity: list[tuple[datetime, float]],
  initial_capital: float,
  bars_per_year: int = 252,
  rf: float = 0.0,
) -> PerformanceMetrics:
  """Derive all portfolio-level perf metrics from an NAV series.

  Arguments
  ---------
  equity : list of (timestamp, NAV). NAV is expected to already
    include mark-to-market of open positions; this function treats
    `equity[-1][1]` as the final NAV and ignores `initial_capital`
    except to compute `total_return` (which mirrors how the run task
    already stores it).
  initial_capital : starting capital in NAV units.
  bars_per_year : used to annualise CAGR / vol / Sharpe / Sortino.
    Default 252 for daily bars. Weekly = 52, monthly = 12.
  rf : annualised risk-free rate (not per-bar). Default 0.

  None is returned for any ratio whose denominator can't be computed.
  """
  # Empty / single-point curves → nothing to compute beyond total_return.
  if not equity:
    return PerformanceMetrics(
      total_return=0.0,
      annualized_return=None, volatility=None,
      sharpe=None, sortino=None,
      max_drawdown=None, calmar=None,
    )

  final_nav = equity[-1][1]
  total_return = (
    (final_nav - initial_capital) / initial_capital
    if initial_capital > 0 else 0.0
  )

  if len(equity) < 2:
    return PerformanceMetrics(
      total_return=total_return,
      annualized_return=None, volatility=None,
      sharpe=None, sortino=None,
      max_drawdown=None, calmar=None,
    )

  returns = _step_returns(equity)
  n_steps = len(returns)
  max_dd = _max_drawdown(equity)

  # CAGR — ((final/initial) ** (bars_per_year / N_bars)) - 1.
  # N_bars = number of step-intervals, i.e. len(returns). Fall back to
  # None if initial_capital is zero or the geometric base is non-positive.
  annualized_return: float | None
  if initial_capital > 0 and final_nav > 0 and n_steps >= 1:
    annualized_return = (final_nav / initial_capital) ** (
      bars_per_year / n_steps
    ) - 1.0
  else:
    annualized_return = None

  # Volatility — annualised stdev of bar returns.
  sd = _stdev(returns, sample=True)
  volatility = sd * math.sqrt(bars_per_year) if sd is not None else None

  # Sharpe — ((mean(returns) * bars_per_year) - rf) / volatility.
  # Using arithmetic mean of bar returns × bars_per_year (standard convention).
  sharpe: float | None
  if volatility and volatility > 0 and returns:
    mean_r = sum(returns) / n_steps
    sharpe = (mean_r * bars_per_year - rf) / volatility
  else:
    sharpe = None

  # Sortino — same numerator, denominator is annualised downside deviation.
  # Downside deviation uses only negative returns; population formula with
  # N (not N-1) matches the standard Sortino definition.
  sortino: float | None = None
  neg = [r for r in returns if r < 0]
  if neg and returns:
    ds = _stdev(neg, sample=False)
    if ds is not None and ds > 0:
      ds_ann = ds * math.sqrt(bars_per_year)
      mean_r = sum(returns) / n_steps
      sortino = (mean_r * bars_per_year - rf) / ds_ann
  # If there are no negative returns the strategy never went down on any
  # step; Sortino is undefined rather than "infinitely good".

  # Calmar — annualised_return / |max_drawdown|.
  calmar: float | None = None
  if (
    annualized_return is not None
    and max_dd is not None
    and max_dd < 0.0
  ):
    calmar = annualized_return / abs(max_dd)

  return PerformanceMetrics(
    total_return=total_return,
    annualized_return=annualized_return,
    volatility=volatility,
    sharpe=sharpe,
    sortino=sortino,
    max_drawdown=max_dd,
    calmar=calmar,
  )
