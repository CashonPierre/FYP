"""
GraphStrategy — evaluates a visual strategy graph per bar.

Supported nodes:
  Triggers  : OnBar
  Data      : Data, Constant, Volume
  Indicators: SMA, EMA, RSI, MACD, BollingerBands, ATR, Stochastic
  Conditions: IfAbove, IfBelow, IfCrossAbove, IfCrossBelow
  Actions   : Buy, Sell

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
  """Read a parameter from node.data.params or node.params (both layouts used)."""
  data_params = node.get("data", {}).get("params", {}) or {}
  flat_params = node.get("params", {}) or {}
  return data_params.get(key, flat_params.get(key, default))


def _node_data_field(node: dict, key: str, default: Any = None) -> Any:
  """Read a top-level field from node.data (e.g. node.data.amount)."""
  data = node.get("data", {}) or {}
  return data.get(key, default)


# Indicator node types that support pandas_ta precomputation.
# Volume is intentionally excluded — it reads from the live bar, not the df.
_INDICATOR_TYPES = frozenset({
  "SMA", "EMA", "RSI",
  "MACD", "BollingerBands", "ATR", "Stochastic",
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

  def __init__(self, graph: dict, ohlcv_df=None) -> None:
    self._nodes: dict[str, dict] = {
      n["id"]: n for n in graph.get("nodes", []) if n.get("id")
    }
    self._edges: list[dict] = graph.get("edges", [])

    # (target_node_id, target_handle) → (source_node_id, source_handle)
    self._input_map: dict[tuple[str, str], tuple[str, str]] = {}
    for e in self._edges:
      src = e.get("source", "")
      src_h = e.get("sourceHandle") or "out"
      tgt = e.get("target", "")
      tgt_h = e.get("targetHandle") or "in"
      if src in self._nodes and tgt in self._nodes:
        self._input_map[(tgt, tgt_h)] = (src, src_h)

    self._exec_order: list[str] = self._topo_sort()

    # Position guard
    wired_sell_ids = {
      tgt for (tgt, _) in self._input_map
      if self._nodes.get(tgt, {}).get("type") == "Sell"
    }
    self._has_exit: bool = bool(wired_sell_ids)
    self._in_position: bool = False

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
          # Use prefix matching — column names encode parameters and could
          # differ across pandas_ta versions; prefix is stable.
          macd_col   = next((c for c in cols if c.startswith("MACD_")), cols[0])
          hist_col   = next((c for c in cols if c.startswith("MACDh_")), cols[1])
          signal_col = next((c for c in cols if c.startswith("MACDs_")), cols[2])
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
          lower_col  = next((c for c in cols if c.startswith("BBL_")), cols[0])
          middle_col = next((c for c in cols if c.startswith("BBM_")), cols[1])
          upper_col  = next((c for c in cols if c.startswith("BBU_")), cols[2])
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
          k_col = next((c for c in cols if c.startswith("STOCHk_")), cols[0])
          d_col = next((c for c in cols if c.startswith("STOCHd_")), cols[1])
          self._precomputed[nid] = {
            "k": _to_list(result[k_col]),
            "d": _to_list(result[d_col]),
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
          outputs[nid] = {"signal": AddSignal(
            side=Side.BUY,
            type=OrderType.MARKET,
            price=float(bar.price),
            symbol=bar.symbol,
            quantity=amount,
            take_profit=None,
            stop_loss=None,
          )}
        else:
          outputs[nid] = {"signal": None}

      # ── Sell ───────────────────────────────────────────────────────
      elif ntype == "Sell":
        trigger = self._upstream(outputs, nid, "in")
        if trigger:
          outputs[nid] = {"signal": CloseSignal(order_id=None)}
        else:
          outputs[nid] = {"signal": None}

    # Collect signals — Sell checked first so exit on same bar as entry wins.
    for nid in self._exec_order:
      ntype = self._nodes[nid].get("type")
      sig = outputs.get(nid, {}).get("signal")
      if sig is None:
        continue

      if ntype == "Sell":
        if self._in_position:
          self._in_position = False
          return sig

      elif ntype == "Buy":
        if self._has_exit and self._in_position:
          pass
        else:
          self._in_position = True
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
    self._bar_idx = -1
    # _precomputed intentionally NOT cleared — derived from the DataFrame
    # passed at construction; _bar_idx reset so replay starts at position 0.
