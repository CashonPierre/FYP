"""Unit tests for the pure equity-curve combiner used by the batch-combined
endpoint."""
from datetime import datetime

from api.backtests._combine import combine_equity_curves


T = lambda d: datetime(2024, 1, d)  # noqa: E731 — tiny helper for readability


def test_empty_input_returns_empty():
  assert combine_equity_curves([], 10_000.0) == []
  assert combine_equity_curves([[]], 10_000.0) == []


def test_single_curve_passthrough():
  """One curve → combined curve equals the input (scaling by 1/1 = 1)."""
  curve = [(T(1), 10_000.0), (T(2), 12_000.0), (T(3), 9_000.0)]
  result = combine_equity_curves([curve], 10_000.0)
  assert result == curve


def test_two_curves_equal_weight_sum_averaged():
  """Symmetric case: one curve +50%, one flat. Combined = +25%."""
  cap = 10_000.0
  up = [(T(1), cap), (T(2), 15_000.0)]
  flat = [(T(1), cap), (T(2), cap)]
  result = combine_equity_curves([up, flat], cap)
  assert result[0] == (T(1), cap)                   # (cap + cap) / 2
  assert result[1] == (T(2), 12_500.0)              # (15000 + 10000) / 2


def test_misaligned_timestamps_forward_fill():
  """Curve B lags curve A — before B's first point, B contributes initial cap.
  After A's last point, A is forward-filled at its last value.
  """
  cap = 100.0
  a = [(T(1), 100.0), (T(3), 200.0)]                # doubles by t3
  b = [(T(2), 100.0), (T(4), 50.0)]                 # halves by t4
  result = combine_equity_curves([a, b], cap)
  assert result == [
    (T(1), 100.0),   # a at 100 (fresh start), b held cash at 100
    (T(2), 100.0),   # a still 100 (before t3), b at 100 (fresh start)
    (T(3), 150.0),   # a at 200, b still 100
    (T(4), 125.0),   # a forward-filled at 200, b at 50
  ]


def test_drops_empty_curves_from_n():
  """An empty curve should not dilute N — failed runs are effectively skipped."""
  cap = 10_000.0
  real = [(T(1), cap), (T(2), 20_000.0)]
  result = combine_equity_curves([real, []], cap)
  # N = 1 (empty dropped), so combined == real curve
  assert result == real
