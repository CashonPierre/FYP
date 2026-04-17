"""
GraphStrategy — evaluates a visual strategy graph per bar.

Supported nodes: OnBar, Data, SMA, EMA, RSI, IfAbove, Buy, Sell

Graph JSON format (same as builder export):
  nodes: [{id, type, data: {params: {...}}, ...}]
  edges: [{id, source, sourceHandle, target, targetHandle}]

Execution model:
  1. On __init__: topologically sort nodes once.
  2. On on_event(bar): evaluate each node in order, passing values via
     a per-call output dict. Return the first triggered signal.
  3. Indicator state (rolling buffers, EMA values) persists across bars.
"""

from __future__ import annotations

import logging
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
  val = data_params.get(key, flat_params.get(key, default))
  return val


def _node_data_field(node: dict, key: str, default: Any = None) -> Any:
  """Read a top-level field from node.data (e.g. node.data.amount)."""
  data = node.get("data", {}) or {}
  return data.get(key, default)


# ---------------------------------------------------------------------------
# GraphStrategy
# ---------------------------------------------------------------------------

class GraphStrategy:
  """
  Interprets a visual builder graph as a live strategy.

  Implements the same interface as trading_engine.strategies.Strategy so the
  engine can call it without modification.
  """

  def __init__(self, graph: dict) -> None:
    self._nodes: dict[str, dict] = {
      n["id"]: n for n in graph.get("nodes", []) if n.get("id")
    }
    self._edges: list[dict] = graph.get("edges", [])

    # (target_node_id, target_handle) → (source_node_id, source_handle)
    # Enables O(1) upstream lookup per input port.
    self._input_map: dict[tuple[str, str], tuple[str, str]] = {}
    for e in self._edges:
      src = e.get("source", "")
      src_h = e.get("sourceHandle") or "out"
      tgt = e.get("target", "")
      tgt_h = e.get("targetHandle") or "in"
      if src in self._nodes and tgt in self._nodes:
        self._input_map[(tgt, tgt_h)] = (src, src_h)

    self._exec_order: list[str] = self._topo_sort()

    # Position guard: if the graph has a Sell node the strategy has an explicit
    # exit, so we enforce one-position-at-a-time.  Graphs with only a Buy node
    # (DCA-style) accumulate freely — no guard applied.
    self._has_exit: bool = any(
      n.get("type") == "Sell" for n in self._nodes.values()
    )
    self._in_position: bool = False

    # Indicator state — persists across bars within one run
    self._price_buffers: dict[str, deque] = {}   # node_id → price history
    self._ema_values: dict[str, float | None] = {}  # node_id → current EMA

  # ------------------------------------------------------------------
  # Topological sort (Kahn's algorithm)
  # ------------------------------------------------------------------

  def _topo_sort(self) -> list[str]:
    """Return node IDs in a valid evaluation order (upstream before downstream)."""
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
  # Per-bar evaluation
  # ------------------------------------------------------------------

  def _upstream(self, outputs: dict[str, dict[str, Any]], node_id: str, handle: str) -> Any:
    """Resolve one input port → upstream node's output value."""
    src = self._input_map.get((node_id, handle))
    if src is None:
      return None
    src_id, src_h = src
    return outputs.get(src_id, {}).get(src_h)

  def on_event(self, event: Any) -> Any:
    # Lazy engine imports — ENGINE_PATH is on sys.path when called from Celery task
    from events.event import MarketDataEvent
    from events.payloads.market_payload import MarketDataPayload
    from strategies.signal import AddSignal, NullSignal, CloseSignal
    from common.enums import OrderType, Side

    if not isinstance(event, MarketDataEvent):
      return NullSignal()

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
        # Data is a visual reference; output the close price
        outputs[nid] = {"out": float(bar.Close or bar.price)}

      # ── SMA / EMA / RSI ────────────────────────────────────────────
      elif ntype in ("SMA", "EMA", "RSI"):
        period = int(_node_param(node, "period", 14))

        # Price input: accept a MarketDataPayload (from OnBar) or a float (from Data/indicator)
        raw = self._upstream(outputs, nid, "in")
        if isinstance(raw, MarketDataPayload):
          price = float(raw.Close or raw.price)
        elif isinstance(raw, (int, float)):
          price = float(raw)
        else:
          price = float(bar.Close or bar.price)  # default to close

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
        a_raw = self._upstream(outputs, nid, "a")
        b_raw = self._upstream(outputs, nid, "b")

        a_val = self._to_float(a_raw, bar)
        b_val = self._to_float(b_raw, bar)

        if trigger is None or a_val is None or b_val is None:
          outputs[nid] = {"true": None, "false": None}
        elif a_val > b_val:
          outputs[nid] = {"true": True, "false": None}
        else:
          outputs[nid] = {"true": None, "false": True}

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
          # order_id=None means close the most-recent open position for this symbol
          outputs[nid] = {"signal": CloseSignal(order_id=None)}
        else:
          outputs[nid] = {"signal": None}

    # Collect signals, applying position guard where appropriate.
    # Sell is checked first so an exit on the same bar as an entry takes priority.
    for nid in self._exec_order:
      ntype = self._nodes[nid].get("type")
      sig = outputs.get(nid, {}).get("signal")
      if sig is None:
        continue

      if ntype == "Sell":
        if self._in_position:
          self._in_position = False
          return sig
        # Not in a position — nothing to close, suppress

      elif ntype == "Buy":
        if self._has_exit and self._in_position:
          pass  # already holding; wait for Sell signal
        else:
          self._in_position = True
          return sig

    return NullSignal()

  # ------------------------------------------------------------------
  # Indicator calculations
  # ------------------------------------------------------------------

  def _to_float(self, val: Any, bar: Any) -> float | None:
    """Coerce a node output value to float. Extracts price from MarketDataPayload."""
    if val is None:
      return None
    if isinstance(val, (int, float)):
      return float(val)
    # MarketDataPayload — use close price
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
      # Seed EMA with SMA once we have enough bars
      buf = list(self._price_buffers[nid])
      if len(buf) < period:
        return None
      self._ema_values[nid] = sum(buf[:period]) / period
    else:
      self._ema_values[nid] = price * k + self._ema_values[nid] * (1 - k)

    return self._ema_values[nid]

  def _rsi(self, nid: str, period: int) -> float | None:
    buf = list(self._price_buffers[nid])
    if len(buf) < period + 1:
      return None

    deltas = [buf[i] - buf[i - 1] for i in range(1, len(buf))]
    recent = deltas[-period:]
    avg_gain = sum(d for d in recent if d > 0) / period
    avg_loss = sum(-d for d in recent if d < 0) / period

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
    self._in_position = False
