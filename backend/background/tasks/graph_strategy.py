"""
GraphStrategy — evaluates a visual strategy graph per bar.

Supported nodes: OnBar, Data, SMA, EMA, RSI, IfAbove, IfBelow,
                 IfCrossAbove, IfCrossBelow, Constant, Buy, Sell

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
     buffers (used by tests and any caller that does not supply a DataFrame).
  3. Non-indicator state (crossover prev values, position flag) persists
     across bars regardless of mode.
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


# Indicator node types that support pandas_ta precomputation
_INDICATOR_TYPES = frozenset({"SMA", "EMA", "RSI"})


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
              strategy falls back to incremental rolling buffers (used by tests
              and any caller that does not have a DataFrame handy).
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

    # Rolling-buffer state (fallback path when no df is provided)
    self._price_buffers: dict[str, deque] = {}
    self._ema_values: dict[str, float | None] = {}
    self._rsi_state: dict[str, tuple[float, float] | None] = {}

    # Crossover state and bar counter (always used)
    self._cross_prev: dict[str, tuple[float | None, float | None]] = {}
    self._bar_idx: int = -1  # incremented at the start of each on_event call

    # Precomputed indicator series: node_id → list[float | None]
    # Built once from ohlcv_df; None entries mark warm-up bars (NaN from pandas_ta).
    self._precomputed: dict[str, list[float | None]] = {}
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
    using pandas_ta.  Chained indicators (e.g. EMA of EMA) are supported:
    the upstream node's precomputed series is used as input when available.
    Results stored as list[float | None] with NaN converted to None.
    """
    import pandas as pd
    import pandas_ta as ta

    def _to_list(series) -> list[float | None]:
      return [
        None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v)
        for v in series
      ]

    close = pd.Series(df["close"].values, dtype=float)

    for nid in self._exec_order:
      node = self._nodes[nid]
      ntype = node.get("type", "")

      if ntype not in _INDICATOR_TYPES:
        continue

      period = int(_node_param(node, "period", 14))

      # Resolve input price series — supports chaining (e.g. RSI of EMA)
      upstream = self._input_map.get((nid, "in"))
      if upstream:
        src_id, _ = upstream
        if src_id in self._precomputed:
          price_series = pd.Series(self._precomputed[src_id], dtype=float)
        else:
          price_series = close
      else:
        price_series = close

      if ntype == "SMA":
        result = ta.sma(price_series, length=period)
      elif ntype == "EMA":
        result = ta.ema(price_series, length=period)
      elif ntype == "RSI":
        result = ta.rsi(price_series, length=period)
      else:
        continue

      self._precomputed[nid] = _to_list(result)

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

      # ── SMA / EMA / RSI ────────────────────────────────────────────
      elif ntype in ("SMA", "EMA", "RSI"):
        period = int(_node_param(node, "period", 14))

        if nid in self._precomputed:
          # Fast path: O(1) lookup from precomputed series
          series = self._precomputed[nid]
          val = series[self._bar_idx] if self._bar_idx < len(series) else None
        else:
          # Fallback: incremental rolling buffers (used when no df was provided)
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
  # Rolling-buffer indicator calculations (fallback path)
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
    # _precomputed is intentionally NOT cleared — the series are derived from
    # the DataFrame passed at construction and remain valid across resets.
    # _bar_idx is reset to -1 so the next on_event starts at position 0.
