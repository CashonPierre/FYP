"""
GraphStrategy — evaluates a visual strategy graph per bar.

Supported nodes:
  Triggers   : OnBar
  Data       : Data, Constant, Volume
  Indicators : SMA, EMA, RSI, MACD, BollingerBands, ATR, Stochastic,
               ROC, WilliamsR, CCI, KDJ, MFI, OBV, KST
  Conditions : IfAbove, IfBelow, IfCrossAbove, IfCrossBelow,
               And, Or, Not, TimeWindow, Position
  Actions    : Buy, Sell, StopLoss, TakeProfit, TrailingStop

Graph JSON format (same as builder export):
  nodes: [{id, type, data: {params: {...}}, ...}]
  edges: [{id, source, sourceHandle, target, targetHandle}]

Execution model:
  1. On __init__: topologically sort nodes once.
     If an ohlcv_df is provided, precompute all indicator series upfront
     using pandas_ta (vectorized, O(n) total).
  2. On on_event(bar): evaluate each node in order, passing values via
     a per-call output dict. Indicator values come from the precomputed
     series (O(1) lookup) when available; otherwise fall back to rolling
     buffers for SMA/EMA/RSI (used when no DataFrame is supplied, e.g. tests).
  3. Non-indicator state (crossover prev values, position flag) persists
     across bars regardless of mode.

Precomputed structure:
  _precomputed: dict[node_id, dict[handle, list[float | None]]]
  Single-output indicators (SMA/EMA/RSI/ATR): {"out": [...]}
  Multi-output indicators:
    MACD          → {"macd": [...], "signal": [...], "histogram": [...]}
    BollingerBands → {"upper": [...], "middle": [...], "lower": [...]}
    Stochastic    → {"k": [...], "d": [...]}
"""

from __future__ import annotations

import logging
import math
from collections import deque
from typing import Any

logger = logging.getLogger("graph_strategy")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_param(node: dict, key: str, default: Any = None) -> Any:
  """Read a parameter from node.data.params, node.data (flat), or node.params.

  The frontend serialises params as ``data: { period: 10 }`` (flat under
  ``data``), while some internal/test callers use ``data: { params: {...} }``
  or a top-level ``params`` dict.  All three layouts are tried in order.
  """
  data = node.get("data", {}) or {}
  data_params = data.get("params", {}) or {}
  flat_params = node.get("params", {}) or {}
  # Priority: data.params > data (flat) > params
  return data_params.get(key, data.get(key, flat_params.get(key, default)))


def _node_data_field(node: dict, key: str, default: Any = None) -> Any:
  """Read a top-level field from node.data (e.g. node.data.amount)."""
  data = node.get("data", {}) or {}
  return data.get(key, default)


# Indicator node types that support pandas_ta precomputation.
# Volume is intentionally excluded — it reads from the live bar, not the df.
_INDICATOR_TYPES = frozenset({
  "SMA", "EMA", "RSI",
  "MACD", "BollingerBands", "ATR", "Stochastic",
  "ROC", "WilliamsR", "CCI",
  "KDJ", "MFI", "OBV", "KST",
})


# ---------------------------------------------------------------------------
# GraphStrategy
# ---------------------------------------------------------------------------

class GraphStrategy:
  """
  Interprets a visual builder graph as a live strategy.

  Implements the same interface as trading_engine.strategies.Strategy so the
  engine can call it without modification.

  Parameters
  ----------
  graph     : Builder export dict (nodes + edges).
  ohlcv_df  : Optional pandas DataFrame with columns open/high/low/close/volume,
              one row per bar in chronological order.  When provided, indicator
              series are precomputed with pandas_ta once at construction time
              and on_event performs O(1) index lookups.  When omitted the
              strategy falls back to incremental rolling buffers for SMA/EMA/RSI
              (used by tests and any caller without a DataFrame).  ATR, MACD,
              BollingerBands and Stochastic require a DataFrame and return None
              on every bar when one is not provided.
  """

  def __init__(
    self, graph: dict, ohlcv_df=None, initial_capital: float = 100000.0,
  ) -> None:
    # initial_capital is used for Buy sizing modes that reference equity
    # ("pct_equity"). We size against initial capital rather than current
    # equity because the engine doesn't plumb live portfolio state into the
    # strategy — and "% of initial" is a well-defined convention (cf.
    # Zipline's `order_target_percent` semantics for the first trade).
    self._initial_capital: float = float(initial_capital)

    self._nodes: dict[str, dict] = {
      n["id"]: n for n in graph.get("nodes", []) if n.get("id")
    }
    self._edges: list[dict] = graph.get("edges", [])

    # (target_node_id, target_handle) → (source_node_id, source_handle)
    self._input_map: dict[tuple[str, str], tuple[str, str]] = {}
    for e in self._edges:
      src = e.get("source", "")
      # Accept both camelCase (internal) and snake_case (frontend serialisation)
      src_h = e.get("sourceHandle") or e.get("source_handle") or "out"
      tgt = e.get("target", "")
      tgt_h = e.get("targetHandle") or e.get("target_handle") or "in"
      if src in self._nodes and tgt in self._nodes:
        self._input_map[(tgt, tgt_h)] = (src, src_h)

    self._exec_order: list[str] = self._topo_sort()

    # Position guard — any exit-producing node counts, not just Sell
    _EXIT_NODE_TYPES = {"Sell", "StopLoss", "TakeProfit", "TrailingStop"}
    wired_exit_ids = {
      tgt for (tgt, _) in self._input_map
      if self._nodes.get(tgt, {}).get("type") in _EXIT_NODE_TYPES
    }
    self._has_exit: bool = bool(wired_exit_ids)
    self._in_position: bool = False
    # Predicted position size. Mirrors the engine's real position group
    # well enough to drive state transitions in the strategy (Buy→Sell
    # guarding, partial-sell handling). Updated optimistically at signal
    # emission time — same pattern as `_in_position`.
    self._position_qty: float = 0.0

    # Risk-management state — tracked per entry, reset on exit
    self._entry_price: float | None = None
    self._trailing_max: float | None = None

    # Rolling-buffer state (fallback for SMA/EMA/RSI when no df provided)
    self._price_buffers: dict[str, deque] = {}
    self._ema_values: dict[str, float | None] = {}
    self._rsi_state: dict[str, tuple[float, float] | None] = {}

    # Crossover state and bar counter (always used)
    self._cross_prev: dict[str, tuple[float | None, float | None]] = {}
    self._bar_idx: int = -1

    # Precomputed indicator series:
    #   node_id → {handle → list[float | None]}
    # Single-output indicators store {"out": [...]}.
    # Multi-output: see module docstring.
    self._precomputed: dict[str, dict[str, list[float | None]]] = {}
    if ohlcv_df is not None:
      self._precompute_indicators(ohlcv_df)

  # ------------------------------------------------------------------
  # Topological sort (Kahn's algorithm)
  # ------------------------------------------------------------------

  def _topo_sort(self) -> list[str]:
    in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
    children: dict[str, list[str]] = {nid: [] for nid in self._nodes}

    for e in self._edges:
      src = e.get("source", "")
      tgt = e.get("target", "")
      if src in self._nodes and tgt in self._nodes:
        children[src].append(tgt)
        in_degree[tgt] += 1

    queue: list[str] = [nid for nid, deg in in_degree.items() if deg == 0]
    result: list[str] = []
    while queue:
      nid = queue.pop(0)
      result.append(nid)
      for child in children[nid]:
        in_degree[child] -= 1
        if in_degree[child] == 0:
          queue.append(child)

    if len(result) != len(self._nodes):
      logger.warning("GraphStrategy: graph contains a cycle; %d nodes unreachable",
                     len(self._nodes) - len(result))
    return result

  # ------------------------------------------------------------------
  # pandas_ta precomputation (fast path)
  # ------------------------------------------------------------------

  def _precompute_indicators(self, df) -> None:
    """
    Walk the execution order and precompute every indicator node's series
    using pandas_ta.  Results stored as dict[handle, list[float | None]]
    with NaN converted to None.
    """
    import pandas as pd
    import pandas_ta as ta

    def _to_list(series) -> list[float | None]:
      return [
        None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v)
        for v in series
      ]

    close = pd.Series(df["close"].values, dtype=float)
    high = pd.Series(df["high"].values, dtype=float) if "high" in df.columns else close
    low = pd.Series(df["low"].values, dtype=float) if "low" in df.columns else close
    volume = pd.Series(df["volume"].values, dtype=float) if "volume" in df.columns else None

    def _resolve_price(nid: str) -> pd.Series:
      """Return the input price series for a node, following upstream chain."""
      upstream = self._input_map.get((nid, "in"))
      if upstream:
        src_id, src_h = upstream
        if src_id in self._precomputed:
          src_data = self._precomputed[src_id]
          series_list = src_data.get(src_h) or src_data.get("out") or []
          return pd.Series(series_list, dtype=float)
      return close

    for nid in self._exec_order:
      node = self._nodes[nid]
      ntype = node.get("type", "")

      if ntype not in _INDICATOR_TYPES:
        continue

      if ntype in ("SMA", "EMA", "RSI"):
        period = int(_node_param(node, "period", 14))
        price_series = _resolve_price(nid)
        if ntype == "SMA":
          result = ta.sma(price_series, length=period)
        elif ntype == "EMA":
          result = ta.ema(price_series, length=period)
        else:
          result = ta.rsi(price_series, length=period)
        self._precomputed[nid] = {"out": _to_list(result)}

      elif ntype == "MACD":
        fast = int(_node_param(node, "fast", 12))
        slow = int(_node_param(node, "slow", 26))
        signal_p = int(_node_param(node, "signal", 9))
        price_series = _resolve_price(nid)
        result = ta.macd(price_series, fast=fast, slow=slow, signal=signal_p)
        n_bars = len(close)
        if result is None or result.empty:
          self._precomputed[nid] = {
            "macd": [None] * n_bars,
            "histogram": [None] * n_bars,
            "signal": [None] * n_bars,
          }
        else:
          cols = result.columns.tolist()
          # Prefix matching — stable across pandas_ta versions that encode
          # parameters in column names.  Raise on mismatch rather than
          # silently falling back to a positionally-wrong column.
          try:
            macd_col   = next(c for c in cols if c.startswith("MACD_"))
            hist_col   = next(c for c in cols if c.startswith("MACDh_"))
            signal_col = next(c for c in cols if c.startswith("MACDs_"))
          except StopIteration:
            raise ValueError(f"GraphStrategy: unexpected MACD column names from pandas_ta: {cols}")
          self._precomputed[nid] = {
            "macd":      _to_list(result[macd_col]),
            "histogram": _to_list(result[hist_col]),
            "signal":    _to_list(result[signal_col]),
          }

      elif ntype == "BollingerBands":
        period = int(_node_param(node, "period", 20))
        std = float(_node_param(node, "std", 2.0))
        price_series = _resolve_price(nid)
        result = ta.bbands(price_series, length=period, std=std)
        n_bars = len(close)
        if result is None or result.empty:
          self._precomputed[nid] = {
            "upper": [None] * n_bars, "middle": [None] * n_bars, "lower": [None] * n_bars,
          }
        else:
          cols = result.columns.tolist()
          # BBL_* = lower, BBM_* = middle, BBU_* = upper
          try:
            lower_col  = next(c for c in cols if c.startswith("BBL_"))
            middle_col = next(c for c in cols if c.startswith("BBM_"))
            upper_col  = next(c for c in cols if c.startswith("BBU_"))
          except StopIteration:
            raise ValueError(f"GraphStrategy: unexpected BollingerBands column names from pandas_ta: {cols}")
          self._precomputed[nid] = {
            "lower":  _to_list(result[lower_col]),
            "middle": _to_list(result[middle_col]),
            "upper":  _to_list(result[upper_col]),
          }

      elif ntype == "ATR":
        period = int(_node_param(node, "period", 14))
        result = ta.atr(high, low, close, length=period)
        self._precomputed[nid] = {
          "out": _to_list(result) if result is not None else [None] * len(close)
        }

      elif ntype == "Stochastic":
        k = int(_node_param(node, "k", 14))
        d = int(_node_param(node, "d", 3))
        result = ta.stoch(high, low, close, k=k, d=d)
        n_bars = len(close)
        if result is None or result.empty:
          self._precomputed[nid] = {"k": [None] * n_bars, "d": [None] * n_bars}
        else:
          cols = result.columns.tolist()
          # STOCHk_* = %K, STOCHd_* = %D
          try:
            k_col = next(c for c in cols if c.startswith("STOCHk_"))
            d_col = next(c for c in cols if c.startswith("STOCHd_"))
          except StopIteration:
            raise ValueError(f"GraphStrategy: unexpected Stochastic column names from pandas_ta: {cols}")
          self._precomputed[nid] = {
            "k": _to_list(result[k_col]),
            "d": _to_list(result[d_col]),
          }

      elif ntype == "ROC":
        period = int(_node_param(node, "period", 10))
        price_series = _resolve_price(nid)
        result = ta.roc(price_series, length=period)
        self._precomputed[nid] = {
          "out": _to_list(result) if result is not None else [None] * len(close)
        }

      elif ntype == "WilliamsR":
        period = int(_node_param(node, "period", 14))
        result = ta.willr(high, low, close, length=period)
        self._precomputed[nid] = {
          "out": _to_list(result) if result is not None else [None] * len(close)
        }

      elif ntype == "CCI":
        period = int(_node_param(node, "period", 20))
        result = ta.cci(high, low, close, length=period)
        self._precomputed[nid] = {
          "out": _to_list(result) if result is not None else [None] * len(close)
        }

      elif ntype == "KDJ":
        length = int(_node_param(node, "length", 9))
        signal_p = int(_node_param(node, "signal", 3))
        result = ta.kdj(high, low, close, length=length, signal=signal_p)
        n_bars = len(close)
        if result is None or result.empty:
          self._precomputed[nid] = {
            "k": [None] * n_bars, "d": [None] * n_bars, "j": [None] * n_bars,
          }
        else:
          cols = result.columns.tolist()
          # K_*, D_*, J_* — prefix match stable across pandas_ta versions
          try:
            k_col = next(c for c in cols if c.startswith("K_"))
            d_col = next(c for c in cols if c.startswith("D_"))
            j_col = next(c for c in cols if c.startswith("J_"))
          except StopIteration:
            raise ValueError(f"GraphStrategy: unexpected KDJ column names from pandas_ta: {cols}")
          self._precomputed[nid] = {
            "k": _to_list(result[k_col]),
            "d": _to_list(result[d_col]),
            "j": _to_list(result[j_col]),
          }

      elif ntype == "MFI":
        period = int(_node_param(node, "period", 14))
        if volume is None:
          self._precomputed[nid] = {"out": [None] * len(close)}
        else:
          result = ta.mfi(high, low, close, volume, length=period)
          self._precomputed[nid] = {
            "out": _to_list(result) if result is not None else [None] * len(close)
          }

      elif ntype == "OBV":
        if volume is None:
          self._precomputed[nid] = {"out": [None] * len(close)}
        else:
          result = ta.obv(close, volume)
          self._precomputed[nid] = {
            "out": _to_list(result) if result is not None else [None] * len(close)
          }

      elif ntype == "KST":
        # pandas_ta.kst defaults: roc1=10, roc2=15, roc3=20, roc4=30,
        # sma1=10, sma2=10, sma3=10, sma4=15, signal=9
        result = ta.kst(close)
        n_bars = len(close)
        if result is None or result.empty:
          self._precomputed[nid] = {"kst": [None] * n_bars, "signal": [None] * n_bars}
        else:
          cols = result.columns.tolist()
          # KST_* = KST line, KSTs_* = signal line.  Order matters: "KSTs_"
          # also starts with "KST", so match signal first or use explicit
          # suffix check on the KST line.
          try:
            signal_col = next(c for c in cols if c.startswith("KSTs_"))
            kst_col    = next(c for c in cols if c.startswith("KST_"))
          except StopIteration:
            raise ValueError(f"GraphStrategy: unexpected KST column names from pandas_ta: {cols}")
          self._precomputed[nid] = {
            "kst":    _to_list(result[kst_col]),
            "signal": _to_list(result[signal_col]),
          }

    logger.debug("GraphStrategy: precomputed %d indicator series (%d bars each)",
                 len(self._precomputed), len(close))

  # ------------------------------------------------------------------
  # Per-bar evaluation
  # ------------------------------------------------------------------

  def _upstream(self, outputs: dict[str, dict[str, Any]], node_id: str, handle: str) -> Any:
    src = self._input_map.get((node_id, handle))
    if src is None:
      return None
    src_id, src_h = src
    return outputs.get(src_id, {}).get(src_h)

  def _precomp_val(self, nid: str, handle: str) -> float | None:
    """Return the precomputed value for (nid, handle) at the current bar index."""
    node_data = self._precomputed.get(nid)
    if node_data is None:
      return None
    series = node_data.get(handle)
    if series is None:
      return None
    return series[self._bar_idx] if self._bar_idx < len(series) else None

  def on_event(self, event: Any) -> Any:
    from events.event import MarketDataEvent
    from events.payloads.market_payload import MarketDataPayload
    from strategies.signal import AddSignal, NullSignal, CloseSignal
    from common.enums import OrderType, Side

    if not isinstance(event, MarketDataEvent):
      return NullSignal()

    self._bar_idx += 1
    bar: MarketDataPayload = event.payload
    outputs: dict[str, dict[str, Any]] = {}

    # Track running max close since entry for TrailingStop.  Updated every
    # bar while in position, cleared on exit.  Using close (not high) keeps
    # behaviour deterministic across backfills where high may be missing.
    if self._in_position and self._trailing_max is not None:
      bar_close = float(bar.Close if bar.Close is not None else bar.price)
      if bar_close > self._trailing_max:
        self._trailing_max = bar_close

    for nid in self._exec_order:
      node = self._nodes[nid]
      ntype = node.get("type", "")

      # ── OnBar ──────────────────────────────────────────────────────
      if ntype == "OnBar":
        outputs[nid] = {"out": bar}

      # ── Data ───────────────────────────────────────────────────────
      elif ntype == "Data":
        outputs[nid] = {"out": float(bar.Close if bar.Close is not None else bar.price)}

      # ── Volume ─────────────────────────────────────────────────────
      elif ntype == "Volume":
        outputs[nid] = {"out": float(bar.volume if bar.volume is not None else 0)}

      # ── SMA / EMA / RSI ────────────────────────────────────────────
      elif ntype in ("SMA", "EMA", "RSI"):
        period = int(_node_param(node, "period", 14))

        if nid in self._precomputed:
          # Fast path: O(1) lookup
          val = self._precomp_val(nid, "out")
        else:
          # Fallback: incremental rolling buffers
          raw = self._upstream(outputs, nid, "in")
          if isinstance(raw, MarketDataPayload):
            price = float(raw.Close or raw.price)
          elif isinstance(raw, (int, float)):
            price = float(raw)
          else:
            price = float(bar.Close if bar.Close is not None else bar.price)

          if nid not in self._price_buffers:
            self._price_buffers[nid] = deque(maxlen=max(period + 1, 2))
          self._price_buffers[nid].append(price)

          if ntype == "SMA":
            val = self._sma(nid, period)
          elif ntype == "EMA":
            val = self._ema(nid, price, period)
          else:
            val = self._rsi(nid, period)

        outputs[nid] = {"out": val}

      # ── MACD ───────────────────────────────────────────────────────
      elif ntype == "MACD":
        if nid in self._precomputed:
          outputs[nid] = {
            "macd":      self._precomp_val(nid, "macd"),
            "signal":    self._precomp_val(nid, "signal"),
            "histogram": self._precomp_val(nid, "histogram"),
          }
        else:
          outputs[nid] = {"macd": None, "signal": None, "histogram": None}

      # ── BollingerBands ─────────────────────────────────────────────
      elif ntype == "BollingerBands":
        if nid in self._precomputed:
          outputs[nid] = {
            "upper":  self._precomp_val(nid, "upper"),
            "middle": self._precomp_val(nid, "middle"),
            "lower":  self._precomp_val(nid, "lower"),
          }
        else:
          outputs[nid] = {"upper": None, "middle": None, "lower": None}

      # ── ATR ────────────────────────────────────────────────────────
      elif ntype == "ATR":
        val = self._precomp_val(nid, "out") if nid in self._precomputed else None
        outputs[nid] = {"out": val}

      # ── Stochastic ─────────────────────────────────────────────────
      elif ntype == "Stochastic":
        if nid in self._precomputed:
          outputs[nid] = {
            "k": self._precomp_val(nid, "k"),
            "d": self._precomp_val(nid, "d"),
          }
        else:
          outputs[nid] = {"k": None, "d": None}

      # ── ROC / Williams %R / CCI / MFI / OBV ────────────────────────
      elif ntype in ("ROC", "WilliamsR", "CCI", "MFI", "OBV"):
        val = self._precomp_val(nid, "out") if nid in self._precomputed else None
        outputs[nid] = {"out": val}

      # ── KDJ ────────────────────────────────────────────────────────
      elif ntype == "KDJ":
        if nid in self._precomputed:
          outputs[nid] = {
            "k": self._precomp_val(nid, "k"),
            "d": self._precomp_val(nid, "d"),
            "j": self._precomp_val(nid, "j"),
          }
        else:
          outputs[nid] = {"k": None, "d": None, "j": None}

      # ── KST ────────────────────────────────────────────────────────
      elif ntype == "KST":
        if nid in self._precomputed:
          outputs[nid] = {
            "kst":    self._precomp_val(nid, "kst"),
            "signal": self._precomp_val(nid, "signal"),
          }
        else:
          outputs[nid] = {"kst": None, "signal": None}

      # ── IfAbove ────────────────────────────────────────────────────
      elif ntype == "IfAbove":
        trigger = self._upstream(outputs, nid, "in")
        a_val = self._to_float(self._upstream(outputs, nid, "a"), bar)
        b_val = self._to_float(self._upstream(outputs, nid, "b"), bar)

        if trigger is None or a_val is None or b_val is None:
          outputs[nid] = {"true": None, "false": None}
        elif a_val > b_val:
          outputs[nid] = {"true": True, "false": None}
        else:
          outputs[nid] = {"true": None, "false": True}

      # ── IfBelow ────────────────────────────────────────────────────
      elif ntype == "IfBelow":
        trigger = self._upstream(outputs, nid, "in")
        a_val = self._to_float(self._upstream(outputs, nid, "a"), bar)
        b_val = self._to_float(self._upstream(outputs, nid, "b"), bar)

        if trigger is None or a_val is None or b_val is None:
          outputs[nid] = {"true": None, "false": None}
        elif a_val < b_val:
          outputs[nid] = {"true": True, "false": None}
        else:
          outputs[nid] = {"true": None, "false": True}

      # ── IfCrossAbove / IfCrossBelow ────────────────────────────────
      elif ntype in ("IfCrossAbove", "IfCrossBelow"):
        trigger = self._upstream(outputs, nid, "in")
        a_val = self._to_float(self._upstream(outputs, nid, "a"), bar)
        b_val = self._to_float(self._upstream(outputs, nid, "b"), bar)

        prev_a, prev_b = self._cross_prev.get(nid, (None, None))
        self._cross_prev[nid] = (a_val, b_val)

        if trigger is None or a_val is None or b_val is None or prev_a is None or prev_b is None:
          outputs[nid] = {"true": None, "false": None}
        else:
          if ntype == "IfCrossAbove":
            crossed = prev_a <= prev_b and a_val > b_val
          else:
            crossed = prev_a >= prev_b and a_val < b_val
          outputs[nid] = {"true": True if crossed else None, "false": None if crossed else True}

      # ── And / Or / Not (logical combinators on event signals) ─────
      elif ntype == "And":
        a = self._upstream(outputs, nid, "a")
        b = self._upstream(outputs, nid, "b")
        fires = bool(a) and bool(b)
        outputs[nid] = {
          "true":  True if fires else None,
          "false": None if fires else True,
        }

      elif ntype == "Or":
        a = self._upstream(outputs, nid, "a")
        b = self._upstream(outputs, nid, "b")
        fires = bool(a) or bool(b)
        outputs[nid] = {
          "true":  True if fires else None,
          "false": None if fires else True,
        }

      elif ntype == "Not":
        inp = self._upstream(outputs, nid, "in")
        fires = not bool(inp)
        outputs[nid] = {
          "true":  True if fires else None,
          "false": None if fires else True,
        }

      # ── TimeWindow (bar-date within [start, end]) ─────────────────
      elif ntype == "TimeWindow":
        trigger = self._upstream(outputs, nid, "in")
        # bar.timestamp is yyyymmdd int (see backend/background/tasks/backtest.py)
        ts = int(getattr(bar, "timestamp", 0) or 0)
        start_raw = str(_node_param(node, "start", "") or "").replace("-", "")
        end_raw   = str(_node_param(node, "end",   "") or "").replace("-", "")
        try:
          start_i = int(start_raw) if start_raw else 0
          end_i   = int(end_raw)   if end_raw   else 99999999
        except ValueError:
          start_i, end_i = 0, 99999999
        if trigger is None or ts == 0:
          outputs[nid] = {"true": None, "false": None}
        elif start_i <= ts <= end_i:
          outputs[nid] = {"true": True, "false": None}
        else:
          outputs[nid] = {"true": None, "false": True}

      # ── Position (flat/holding state check) ───────────────────────
      elif ntype == "Position":
        trigger = self._upstream(outputs, nid, "in")
        if trigger is None:
          outputs[nid] = {"flat": None, "holding": None}
        else:
          outputs[nid] = {
            "flat":    True if not self._in_position else None,
            "holding": True if self._in_position else None,
          }

      # ── StopLoss (exit when close ≤ entry × (1 − pct/100)) ────────
      elif ntype == "StopLoss":
        trigger = self._upstream(outputs, nid, "in")
        pct = float(_node_param(node, "pct", 2.0))
        if trigger and self._in_position and self._entry_price:
          close = float(bar.Close if bar.Close is not None else bar.price)
          threshold = self._entry_price * (1.0 - pct / 100.0)
          if close <= threshold:
            outputs[nid] = {"signal": CloseSignal(order_id=None)}
          else:
            outputs[nid] = {"signal": None}
        else:
          outputs[nid] = {"signal": None}

      # ── TakeProfit (exit when close ≥ entry × (1 + pct/100)) ──────
      elif ntype == "TakeProfit":
        trigger = self._upstream(outputs, nid, "in")
        pct = float(_node_param(node, "pct", 5.0))
        if trigger and self._in_position and self._entry_price:
          close = float(bar.Close if bar.Close is not None else bar.price)
          threshold = self._entry_price * (1.0 + pct / 100.0)
          if close >= threshold:
            outputs[nid] = {"signal": CloseSignal(order_id=None)}
          else:
            outputs[nid] = {"signal": None}
        else:
          outputs[nid] = {"signal": None}

      # ── TrailingStop (exit when close ≤ max_since_entry × (1 − pct/100)) ──
      elif ntype == "TrailingStop":
        trigger = self._upstream(outputs, nid, "in")
        pct = float(_node_param(node, "pct", 3.0))
        if trigger and self._in_position and self._trailing_max:
          close = float(bar.Close if bar.Close is not None else bar.price)
          threshold = self._trailing_max * (1.0 - pct / 100.0)
          if close <= threshold:
            outputs[nid] = {"signal": CloseSignal(order_id=None)}
          else:
            outputs[nid] = {"signal": None}
        else:
          outputs[nid] = {"signal": None}

      # ── Constant ───────────────────────────────────────────────────
      elif ntype == "Constant":
        value = float(_node_param(node, "value", 0))
        outputs[nid] = {"out": value}

      # ── Buy ────────────────────────────────────────────────────────
      elif ntype == "Buy":
        trigger = self._upstream(outputs, nid, "in")
        if trigger:
          amount = float(
            _node_data_field(node, "amount") or _node_param(node, "amount", 10)
          )
          # Sizing modes:
          #   units       → quantity = amount (legacy, default for old graphs)
          #   pct_equity  → quantity = floor((initial_capital × pct/100) / price)
          #   dollar      → quantity = floor(amount / price)
          size_type = str(
            _node_param(node, "size_type")
            or _node_data_field(node, "size_type")
            or "units"
          )
          price = float(bar.price) if bar.price else 0.0
          if size_type == "pct_equity" and price > 0:
            dollars = self._initial_capital * (amount / 100.0)
            quantity = max(0.0, math.floor(dollars / price))
          elif size_type == "dollar" and price > 0:
            quantity = max(0.0, math.floor(amount / price))
          else:
            quantity = amount

          if quantity <= 0:
            outputs[nid] = {"signal": None}
          else:
            outputs[nid] = {"signal": AddSignal(
              side=Side.BUY,
              type=OrderType.MARKET,
              price=float(bar.price),
              symbol=bar.symbol,
              quantity=quantity,
              take_profit=None,
              stop_loss=None,
            )}
        else:
          outputs[nid] = {"signal": None}

      # ── Sell ───────────────────────────────────────────────────────
      elif ntype == "Sell":
        trigger = self._upstream(outputs, nid, "in")
        if trigger:
          # Sizing modes:
          #   all         → close full position (default, legacy)
          #   pct_position → close <amount>% of current symbol group
          #   units       → close exactly <amount> shares (capped to group)
          size_type = str(
            _node_param(node, "size_type")
            or _node_data_field(node, "size_type")
            or "all"
          )
          amount = float(
            _node_data_field(node, "amount") or _node_param(node, "amount", 0)
          )
          if size_type == "pct_position" and amount > 0:
            outputs[nid] = {"signal": CloseSignal(
              order_id=None, fraction=min(1.0, amount / 100.0),
            )}
          elif size_type == "units" and amount > 0:
            outputs[nid] = {"signal": CloseSignal(
              order_id=None, quantity=amount,
            )}
          else:
            outputs[nid] = {"signal": CloseSignal(order_id=None)}
        else:
          outputs[nid] = {"signal": None}

    # Collect signals — exits checked first so a stop-out on entry bar wins.
    _exit_types = ("Sell", "StopLoss", "TakeProfit", "TrailingStop")
    for nid in self._exec_order:
      ntype = self._nodes[nid].get("type")
      sig = outputs.get(nid, {}).get("signal")
      if sig is None:
        continue

      if ntype in _exit_types:
        if self._in_position:
          # Predict how many shares this exit will close so we can decide
          # whether the position is fully flat after dispatch. The engine
          # caps actual close qty at the real position size; we mirror
          # that with max(0, ...) here. Attributes are read via getattr
          # because test stubs use a minimal CloseSignal surface.
          qty_closed = self._position_qty
          if isinstance(sig, CloseSignal):
            sig_qty = getattr(sig, "quantity", None)
            sig_frac = getattr(sig, "fraction", None)
            if sig_qty is not None:
              qty_closed = min(self._position_qty, float(sig_qty))
            elif sig_frac is not None:
              qty_closed = self._position_qty * float(sig_frac)
          self._position_qty = max(0.0, self._position_qty - qty_closed)

          if self._position_qty <= 1e-9:
            self._in_position = False
            self._position_qty = 0.0
            self._entry_price = None
            self._trailing_max = None
          return sig

      elif ntype == "Buy":
        if self._has_exit and self._in_position:
          pass
        else:
          # Track predicted share count to drive partial-sell semantics.
          # AddSignal.quantity is the resolved share count (sizing modes
          # already resolved upstream in the Buy node handler).
          added_qty = float(getattr(sig, "quantity", 0) or 0)
          if not self._in_position:
            entry = float(bar.Close if bar.Close is not None else bar.price)
            self._entry_price = entry
            self._trailing_max = entry
          self._in_position = True
          self._position_qty += added_qty
          return sig

    return NullSignal()

  # ------------------------------------------------------------------
  # Rolling-buffer indicator calculations (SMA/EMA/RSI fallback path)
  # ------------------------------------------------------------------

  def _to_float(self, val: Any, bar: Any) -> float | None:
    if val is None:
      return None
    if isinstance(val, (int, float)):
      return float(val)
    close = getattr(val, "Close", None) or getattr(val, "price", None)
    if close is not None:
      return float(close)
    return None

  def _sma(self, nid: str, period: int) -> float | None:
    buf = list(self._price_buffers[nid])
    if len(buf) < period:
      return None
    return sum(buf[-period:]) / period

  def _ema(self, nid: str, price: float, period: int) -> float | None:
    k = 2.0 / (period + 1)
    if nid not in self._ema_values:
      self._ema_values[nid] = None

    if self._ema_values[nid] is None:
      buf = list(self._price_buffers[nid])
      if len(buf) < period:
        return None
      self._ema_values[nid] = sum(buf[:period]) / period
    else:
      self._ema_values[nid] = price * k + self._ema_values[nid] * (1 - k)

    return self._ema_values[nid]

  def _rsi(self, nid: str, period: int) -> float | None:
    """Wilder's smoothed RSI."""
    buf = list(self._price_buffers[nid])
    if len(buf) < period + 1:
      return None

    deltas = [buf[i] - buf[i - 1] for i in range(1, len(buf))]

    if self._rsi_state.get(nid) is None:
      seed = deltas[:period]
      avg_gain = sum(d for d in seed if d > 0) / period
      avg_loss = sum(-d for d in seed if d < 0) / period
      self._rsi_state[nid] = (avg_gain, avg_loss)
    else:
      prev_gain, prev_loss = self._rsi_state[nid]
      last = deltas[-1]
      gain = max(last, 0.0)
      loss = max(-last, 0.0)
      avg_gain = (prev_gain * (period - 1) + gain) / period
      avg_loss = (prev_loss * (period - 1) + loss) / period
      self._rsi_state[nid] = (avg_gain, avg_loss)

    avg_gain, avg_loss = self._rsi_state[nid]
    if avg_loss == 0:
      return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))

  # ------------------------------------------------------------------
  # Strategy ABC requirements
  # ------------------------------------------------------------------

  def get_hash_key(self) -> tuple[object, ...]:
    return ("GraphStrategy", id(self))

  def reset(self) -> None:
    self._price_buffers.clear()
    self._ema_values.clear()
    self._rsi_state.clear()
    self._cross_prev.clear()
    self._in_position = False
    self._entry_price = None
    self._trailing_max = None
    self._bar_idx = -1
    # _precomputed intentionally NOT cleared — derived from the DataFrame
    # passed at construction; _bar_idx reset so replay starts at position 0.
