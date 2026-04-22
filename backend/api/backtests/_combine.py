"""Pure helpers for combining independent backtest equity curves into one
equal-weight portfolio series. Kept separate from the route module so the
combination logic can be unit-tested without a DB.
"""

from __future__ import annotations

from datetime import datetime


def combine_equity_curves(
  curves: list[list[tuple[datetime, float]]],
  initial_capital: float,
) -> list[tuple[datetime, float]]:
  """Merge N independent equity curves into one equal-weight portfolio.

  Each input curve is a list of `(time, nav)` pairs that starts from
  `initial_capital` (the same capital every run was executed with — fan-out
  batches always share a single `initial_capital` setting).

  The combined portfolio allocates `initial_capital / N` to each symbol.
  Each symbol's contribution at time `t` is its per-curve NAV scaled by
  `1 / N`. Before a curve's first point we treat the position as cash at
  `initial_capital` (same as its starting value, so it contributes
  `initial_capital / N`). After a curve's last point the last-known NAV is
  forward-filled.

  Empty input → empty result. Empty curves are dropped from N.
  """
  non_empty = [c for c in curves if c]
  if not non_empty:
    return []

  sorted_curves = [sorted(c, key=lambda p: p[0]) for c in non_empty]
  all_times = sorted({t for curve in sorted_curves for t, _ in curve})
  n = len(sorted_curves)

  pointers = [0] * n
  # Before the first point of a curve we hold cash at initial_capital.
  last_nav = [initial_capital] * n

  combined: list[tuple[datetime, float]] = []
  for t in all_times:
    for i, curve in enumerate(sorted_curves):
      while pointers[i] < len(curve) and curve[pointers[i]][0] <= t:
        last_nav[i] = curve[pointers[i]][1]
        pointers[i] += 1
    combined_nav = sum(nav / n for nav in last_nav)
    combined.append((t, combined_nav))

  return combined
