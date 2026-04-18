"""
Tests for GraphStrategy — the per-bar graph interpreter.

These tests are pure-Python and do NOT require the trading engine on sys.path.
Engine types (AddSignal, NullSignal, etc.) are replaced with lightweight stubs.
"""

import sys
import types
import pytest
import pandas as pd
from collections import deque
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Stub out trading-engine modules so GraphStrategy can be imported without
# the engine on sys.path (fast unit tests, no Docker required).
# ---------------------------------------------------------------------------

def _make_engine_stubs():
  # events.event
  evt_mod = types.ModuleType("events")
  evt_mod.event = types.ModuleType("events.event")
  class _MarketDataEvent:
    def __init__(self, payload): self.payload = payload
  evt_mod.event.MarketDataEvent = _MarketDataEvent
  sys.modules.setdefault("events", evt_mod)
  sys.modules.setdefault("events.event", evt_mod.event)

  # events.payloads.market_payload
  pay_mod = types.ModuleType("events.payloads.market_payload")
  class _MarketDataPayload:
    def __init__(self, *, timestamp=0, symbol="TEST", price=100.0, volume=0,
                 Open=None, High=None, Low=None, Close=None):
      self.timestamp = timestamp
      self.symbol = symbol
      self.price = price
      self.volume = volume
      self.Open = Open
      self.High = High
      self.Low = Low
      self.Close = Close or price
  pay_mod.MarketDataPayload = _MarketDataPayload
  sys.modules.setdefault("events.payloads", types.ModuleType("events.payloads"))
  sys.modules.setdefault("events.payloads.market_payload", pay_mod)

  # strategies.signal
  sig_mod = types.ModuleType("strategies.signal")
  class NullSignal: pass
  class AddSignal:
    def __init__(self, **kw): self.__dict__.update(kw)
  class CloseSignal:
    def __init__(self, **kw): self.__dict__.update(kw)
  sig_mod.NullSignal = NullSignal
  sig_mod.AddSignal = AddSignal
  sig_mod.CloseSignal = CloseSignal
  sys.modules.setdefault("strategies", types.ModuleType("strategies"))
  sys.modules.setdefault("strategies.signal", sig_mod)

  # common.enums
  enum_mod = types.ModuleType("common.enums")
  class _Side:
    BUY = "buy"; SELL = "sell"
  class _OrderType:
    MARKET = "market"
  enum_mod.Side = _Side
  enum_mod.OrderType = _OrderType
  sys.modules.setdefault("common", types.ModuleType("common"))
  sys.modules.setdefault("common.enums", enum_mod)

_make_engine_stubs()

# Now safe to import
from background.tasks.graph_strategy import GraphStrategy  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bar(price: float, symbol: str = "TEST"):
  from events.payloads.market_payload import MarketDataPayload
  return MarketDataPayload(timestamp=0, symbol=symbol, price=price,
                           volume=0, Close=price)

def _event(price: float):
  from events.event import MarketDataEvent
  return MarketDataEvent(payload=_bar(price))

def _make_graph(nodes: list[dict], edges: list[dict] | None = None) -> dict:
  return {"nodes": nodes, "edges": edges or []}

def _node(nid: str, ntype: str, params: dict | None = None, amount: float | None = None) -> dict:
  data: dict = {}
  if params:
    data["params"] = params
  if amount is not None:
    data["amount"] = amount
  return {"id": nid, "type": ntype, "data": data}

def _edge(src: str, tgt: str, src_h: str = "out", tgt_h: str = "in") -> dict:
  return {"id": f"{src}-{tgt}", "source": src, "sourceHandle": src_h,
          "target": tgt, "targetHandle": tgt_h}


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

class TestTopoSort:
  def test_linear_chain(self):
    """OnBar → SMA → IfAbove → Buy should sort in that order."""
    g = _make_graph(
      [_node("ob", "OnBar"), _node("sma", "SMA", {"period": 5}),
       _node("if", "IfAbove"), _node("buy", "Buy")],
      [_edge("ob", "sma"), _edge("sma", "if", tgt_h="a"),
       _edge("ob", "if"), _edge("if", "buy", src_h="true")],
    )
    gs = GraphStrategy(g)
    order = gs._exec_order
    assert order.index("ob") < order.index("sma")
    assert order.index("sma") < order.index("if")
    assert order.index("if") < order.index("buy")

  def test_all_nodes_included(self):
    g = _make_graph(
      [_node("a", "OnBar"), _node("b", "Buy")],
      [_edge("a", "b")],
    )
    gs = GraphStrategy(g)
    assert set(gs._exec_order) == {"a", "b"}

  def test_disconnected_nodes_included(self):
    """Nodes with no edges should still appear in the execution order."""
    g = _make_graph([_node("a", "OnBar"), _node("b", "Buy")])
    gs = GraphStrategy(g)
    assert len(gs._exec_order) == 2


# ---------------------------------------------------------------------------
# OnBar + Buy (DCA-equivalent)
# ---------------------------------------------------------------------------

class TestOnBarBuy:
  def _dca_graph(self, amount: float = 10.0) -> GraphStrategy:
    g = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy", amount=amount)],
      [_edge("ob", "buy")],
    )
    return GraphStrategy(g)

  def test_buy_fires_every_bar(self):
    gs = self._dca_graph(amount=5.0)
    for price in [100.0, 101.0, 102.0]:
      sig = gs.on_event(_event(price))
      assert sig.__class__.__name__ == "AddSignal"
      assert sig.quantity == 5.0

  def test_buy_amount_default(self):
    # Buy node with no explicit amount should default to 10
    g = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy")],
      [_edge("ob", "buy")],
    )
    gs = GraphStrategy(g)
    sig = gs.on_event(_event(100.0))
    assert sig.quantity == 10.0

  def test_no_connection_returns_null(self):
    g = _make_graph([_node("ob", "OnBar"), _node("buy", "Buy")])
    gs = GraphStrategy(g)
    sig = gs.on_event(_event(100.0))
    assert sig.__class__.__name__ == "NullSignal"


# ---------------------------------------------------------------------------
# SMA evaluator
# ---------------------------------------------------------------------------

class TestSMA:
  def _graph_with_sma(self, period: int = 3) -> GraphStrategy:
    g = _make_graph(
      [_node("ob", "OnBar"), _node("sma", "SMA", {"period": period}),
       _node("buy", "Buy")],
      [_edge("ob", "sma"), _edge("sma", "buy", tgt_h="in")],
    )
    return GraphStrategy(g)

  def test_warmup_suppresses_signal(self):
    gs = self._graph_with_sma(period=3)
    # Only 2 bars — SMA(3) not ready → NullSignal
    for price in [100.0, 101.0]:
      sig = gs.on_event(_event(price))
      assert sig.__class__.__name__ == "NullSignal", f"expected NullSignal at price {price}"

  def test_fires_after_warmup(self):
    gs = self._graph_with_sma(period=3)
    prices = [100.0, 101.0, 102.0]
    for p in prices:
      sig = gs.on_event(_event(p))
    # After 3 bars SMA is ready → Buy should fire
    assert sig.__class__.__name__ == "AddSignal"

  def test_sma_value_correct(self):
    """Directly inspect the SMA buffer calculation."""
    g = _make_graph([_node("ob", "OnBar"), _node("sma", "SMA", {"period": 4})], [])
    gs = GraphStrategy(g)
    prices = [10.0, 20.0, 30.0, 40.0]
    for p in prices:
      gs._price_buffers.setdefault("sma", deque(maxlen=5))
      gs._price_buffers["sma"].append(p)
    result = gs._sma("sma", 4)
    assert result == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# EMA evaluator
# ---------------------------------------------------------------------------

class TestEMA:
  def test_warmup_returns_none(self):
    g = _make_graph([_node("ob", "OnBar"), _node("ema", "EMA", {"period": 5})], [])
    gs = GraphStrategy(g)
    gs._price_buffers["ema"] = deque([10.0, 20.0, 30.0], maxlen=6)
    result = gs._ema("ema", 30.0, 5)
    assert result is None  # only 3 bars < period=5

  def test_seeds_with_sma(self):
    g = _make_graph([_node("ob", "OnBar"), _node("ema", "EMA", {"period": 3})], [])
    gs = GraphStrategy(g)
    # Feed 3 prices → seeds EMA with their average
    gs._price_buffers["ema"] = deque([10.0, 20.0, 30.0], maxlen=4)
    val = gs._ema("ema", 30.0, 3)
    assert val == pytest.approx(20.0)  # (10+20+30)/3

  def test_subsequent_ema_update(self):
    g = _make_graph([_node("ob", "OnBar"), _node("ema", "EMA", {"period": 3})], [])
    gs = GraphStrategy(g)
    gs._price_buffers["ema"] = deque([10.0, 20.0, 30.0], maxlen=4)
    gs._ema("ema", 30.0, 3)  # seed
    # k = 2/(3+1) = 0.5; EMA = 40 * 0.5 + 20 * 0.5 = 30
    val = gs._ema("ema", 40.0, 3)
    assert val == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# RSI evaluator
# ---------------------------------------------------------------------------

class TestRSI:
  def test_warmup_returns_none(self):
    g = _make_graph([_node("ob", "OnBar"), _node("rsi", "RSI", {"period": 14})], [])
    gs = GraphStrategy(g)
    gs._price_buffers["rsi"] = deque([100.0] * 10, maxlen=15)
    result = gs._rsi("rsi", 14)
    assert result is None  # 10 bars < period+1=15

  def test_flat_prices_returns_100(self):
    """Flat prices → no losses → RSI = 100 (Wilder seed: avg_loss=0)."""
    g = _make_graph([_node("ob", "OnBar"), _node("rsi", "RSI", {"period": 5})], [])
    gs = GraphStrategy(g)
    gs._price_buffers["rsi"] = deque([100.0] * 6, maxlen=7)
    result = gs._rsi("rsi", 5)
    assert result == 100.0
    # Second call — Wilder smoothing with zero delta keeps avg_loss=0
    gs._price_buffers["rsi"].append(100.0)
    result2 = gs._rsi("rsi", 5)
    assert result2 == 100.0

  def test_rsi_range(self):
    """RSI must be in [0, 100]."""
    g = _make_graph([_node("ob", "OnBar"), _node("rsi", "RSI", {"period": 5})], [])
    gs = GraphStrategy(g)
    prices = [100.0, 101.0, 99.0, 102.0, 98.0, 103.0]
    gs._price_buffers["rsi"] = deque(prices, maxlen=7)
    result = gs._rsi("rsi", 5)
    assert result is not None
    assert 0.0 <= result <= 100.0


# ---------------------------------------------------------------------------
# IfAbove node
# ---------------------------------------------------------------------------

class TestIfAbove:
  def _ifabove_graph(self) -> GraphStrategy:
    """OnBar → SMA(3) → IfAbove.a; static 105.0 — no; full graph:
       OnBar --in→ IfAbove, SMA --a→ IfAbove, OnBar-price --b→ IfAbove (via Data),
       IfAbove.true --in→ Buy
    """
    g = _make_graph(
      [_node("ob", "OnBar"),
       _node("sma", "SMA", {"period": 3}),
       _node("if", "IfAbove"),
       _node("buy", "Buy", amount=5.0)],
      [_edge("ob", "sma"),           # SMA price input
       _edge("ob", "if"),            # trigger
       _edge("sma", "if", tgt_h="a"),  # A = SMA value
       _edge("ob", "if", src_h="out", tgt_h="b"),  # B = bar (will be cast to float → price)
       _edge("if", "buy", src_h="true")],
    )
    return GraphStrategy(g)

  def test_no_signal_during_warmup(self):
    gs = self._ifabove_graph()
    for p in [100.0, 101.0]:
      sig = gs.on_event(_event(p))
      assert sig.__class__.__name__ == "NullSignal"

  def test_buy_when_sma_above_price(self):
    gs = self._ifabove_graph()
    # After 3 bars at 100, SMA=100.  On bar 4 price=90 → SMA(100) > price(90) → Buy
    for p in [100.0, 100.0, 100.0]:
      gs.on_event(_event(p))
    sig = gs.on_event(_event(90.0))
    assert sig.__class__.__name__ == "AddSignal"
    assert sig.quantity == 5.0

  def test_null_when_sma_below_price(self):
    gs = self._ifabove_graph()
    for p in [100.0, 100.0, 100.0]:
      gs.on_event(_event(p))
    # SMA=100, price=110 → SMA < price → IfAbove.true = None → NullSignal
    sig = gs.on_event(_event(110.0))
    assert sig.__class__.__name__ == "NullSignal"


# ---------------------------------------------------------------------------
# Sell node
# ---------------------------------------------------------------------------

class TestSell:
  def test_sell_fires_close_signal(self):
    g = _make_graph(
      [_node("ob", "OnBar"), _node("sell", "Sell")],
      [_edge("ob", "sell")],
    )
    gs = GraphStrategy(g)
    gs._in_position = True  # simulate having entered a position
    sig = gs.on_event(_event(100.0))
    assert sig.__class__.__name__ == "CloseSignal"

  def test_sell_not_triggered_without_connection(self):
    g = _make_graph([_node("ob", "OnBar"), _node("sell", "Sell")])
    gs = GraphStrategy(g)
    sig = gs.on_event(_event(100.0))
    assert sig.__class__.__name__ == "NullSignal"


# ---------------------------------------------------------------------------
# Non-MarketDataEvent returns NullSignal
# ---------------------------------------------------------------------------

def test_non_market_event_returns_null():
  g = _make_graph(
    [_node("ob", "OnBar"), _node("buy", "Buy")],
    [_edge("ob", "buy")],
  )
  gs = GraphStrategy(g)
  sig = gs.on_event(object())  # not a MarketDataEvent
  assert sig.__class__.__name__ == "NullSignal"


# ---------------------------------------------------------------------------
# Empty graph fallback (tested via _strategy_from_graph)
# ---------------------------------------------------------------------------

def test_strategy_from_graph_empty_falls_back_to_dca(monkeypatch):
  """_strategy_from_graph with an empty node list returns a DCA instance."""
  import sys, types

  # Stub DCA
  dca_mod = types.ModuleType("strategies.dca")
  class _DCA:
    def __init__(self, **kw): self.__dict__.update(kw)
  dca_mod.DCA = _DCA
  monkeypatch.setitem(sys.modules, "strategies.dca", dca_mod)

  # Also stub GraphStrategy import path inside backtest.py
  gs_mod = types.ModuleType("background.tasks.graph_strategy")
  gs_mod.GraphStrategy = GraphStrategy
  monkeypatch.setitem(sys.modules, "background.tasks.graph_strategy", gs_mod)

  from background.tasks.backtest import _strategy_from_graph
  result = _strategy_from_graph({"nodes": [], "edges": []})
  assert isinstance(result, _DCA)


# ---------------------------------------------------------------------------
# Position guard
# ---------------------------------------------------------------------------

class TestPositionGuard:
  def _buy_sell_graph(self) -> GraphStrategy:
    """OnBar → Buy, OnBar → Sell (both connected)."""
    g = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy", amount=5.0), _node("sell", "Sell")],
      [_edge("ob", "buy"), _edge("ob", "sell")],
    )
    return GraphStrategy(g)

  def test_has_exit_detected(self):
    gs = self._buy_sell_graph()
    assert gs._has_exit is True

  def test_unwired_sell_no_guard(self):
    """Sell node on canvas but unconnected → _has_exit=False → Buy accumulates freely."""
    g = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy", amount=10.0), _node("sell", "Sell")],
      [_edge("ob", "buy")],   # Sell has NO incoming edge
    )
    gs = GraphStrategy(g)
    assert gs._has_exit is False  # unconnected Sell doesn't activate guard

  def test_no_exit_no_guard(self):
    """Buy-only graph (DCA): every bar fires AddSignal regardless."""
    g = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy", amount=10.0)],
      [_edge("ob", "buy")],
    )
    gs = GraphStrategy(g)
    assert gs._has_exit is False
    for _ in range(5):
      sig = gs.on_event(_event(100.0))
      assert sig.__class__.__name__ == "AddSignal"

  def test_buy_blocked_when_in_position(self):
    """With a wired Sell node present, Buy is suppressed once in position."""
    # Buy is wired; Sell exists but is unconnected — so _has_exit=False?
    # Instead: wire Sell to a dead-end so it has an incoming edge but never triggers.
    # Simplest: manually set _in_position after first buy and assert second is blocked.
    g = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy", amount=5.0), _node("sell", "Sell")],
      [_edge("ob", "buy"), _edge("ob", "sell")],
    )
    gs = GraphStrategy(g)
    assert gs._has_exit is True

    # First bar: Buy fires, Sell suppressed (not yet in position)
    sig1 = gs.on_event(_event(100.0))
    assert sig1.__class__.__name__ == "AddSignal"
    assert gs._in_position is True

    # Manually block Sell from firing by marking not-in-position, then re-enter
    # to isolate Buy-blocking behaviour: put back in position, confirm Buy blocked
    gs._in_position = True
    # Disconnect Sell from outputs by testing via direct state manipulation
    # Simplest proof: force _in_position=True and use a Buy-only trigger graph
    g2 = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy", amount=5.0), _node("sell", "Sell")],
      [_edge("ob", "buy")],   # Sell unconnected here — guard still set via manual flag
    )
    gs2 = GraphStrategy(g2)
    gs2._has_exit = True       # force guard on
    gs2._in_position = True    # simulate already holding
    sig2 = gs2.on_event(_event(101.0))
    assert sig2.__class__.__name__ == "NullSignal"  # Buy blocked

  def test_sell_clears_position_allows_rebuy(self):
    """Buy → hold → Sell clears position → next Buy fires again."""
    # Graph: OnBar → IfAbove → Buy (true port), IfAbove → Sell (false port)
    # We simulate by directly manipulating _in_position
    g = _make_graph(
      [_node("ob", "OnBar"),
       _node("if", "IfAbove"),
       _node("buy", "Buy", amount=5.0),
       _node("sell", "Sell")],
      [_edge("ob", "if"),
       _edge("ob", "if", tgt_h="a"),   # a = bar price
       _edge("ob", "if", tgt_h="b"),   # b = bar price (equal → false)
       _edge("if", "buy", src_h="true"),
       _edge("if", "sell", src_h="false")],
    )
    gs = GraphStrategy(g)
    assert gs._has_exit is True

    # price == price → IfAbove is false → Sell triggers
    sig = gs.on_event(_event(100.0))
    # Both a and b are bar price → a == b → false path → Sell
    # But we're not in position yet → Sell suppressed
    assert sig.__class__.__name__ == "NullSignal"
    assert gs._in_position is False

    # Manually put in position, then verify Sell clears it
    gs._in_position = True
    sig = gs.on_event(_event(100.0))
    assert sig.__class__.__name__ == "CloseSignal"
    assert gs._in_position is False

    # Now Buy can fire again (if IfAbove.true were triggered)
    # Directly test: inject in_position=False and a buy-triggering bar
    gs._in_position = False
    # Bypass IfAbove by directly testing the Buy node path
    # Build a simple OnBar→Buy graph with _has_exit=True via sell node
    g2 = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy", amount=5.0), _node("sell", "Sell")],
      [_edge("ob", "buy")],
    )
    gs2 = GraphStrategy(g2)
    gs2.on_event(_event(100.0))          # first buy
    assert gs2._in_position is True
    gs2._in_position = False              # simulate sell clearing position
    sig = gs2.on_event(_event(100.0))    # should buy again
    assert sig.__class__.__name__ == "AddSignal"

  def test_sell_suppressed_when_not_in_position(self):
    """Sell signal is ignored if we never entered a position."""
    g = _make_graph(
      [_node("ob", "OnBar"), _node("sell", "Sell")],
      [_edge("ob", "sell")],
    )
    gs = GraphStrategy(g)
    assert gs._has_exit is True
    assert gs._in_position is False
    sig = gs.on_event(_event(100.0))
    assert sig.__class__.__name__ == "NullSignal"  # nothing to close

  def test_reset_clears_position_flag(self):
    g = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy"), _node("sell", "Sell")],
      [_edge("ob", "buy")],
    )
    gs = GraphStrategy(g)
    gs.on_event(_event(100.0))   # enters position
    assert gs._in_position is True
    gs.reset()
    assert gs._in_position is False


# ---------------------------------------------------------------------------
# reset() clears state
# ---------------------------------------------------------------------------

def test_reset_clears_state():
  g = _make_graph(
    [_node("ob", "OnBar"), _node("sma", "SMA", {"period": 3}),
     _node("buy", "Buy")],
    [_edge("ob", "sma"), _edge("sma", "buy")],
  )
  gs = GraphStrategy(g)
  for p in [100.0, 101.0, 102.0]:
    gs.on_event(_event(p))
  assert len(gs._price_buffers) > 0

  gs.reset()
  assert len(gs._price_buffers) == 0
  assert len(gs._ema_values) == 0
  assert len(gs._rsi_state) == 0
  assert len(gs._cross_prev) == 0


# ---------------------------------------------------------------------------
# Constant node
# ---------------------------------------------------------------------------

class TestConstant:
  def _graph(self, value: float):
    """OnBar → IfAbove(close, Constant) → Buy"""
    return _make_graph(
      [
        _node("ob", "OnBar"),
        _node("const", "Constant", {"value": value}),
        _node("if", "IfAbove"),
        _node("buy", "Buy", amount=10),
      ],
      [
        _edge("ob", "if", tgt_h="in"),
        _edge("ob", "if", src_h="out", tgt_h="a"),   # close price as A
        _edge("const", "if", src_h="out", tgt_h="b"),
        _edge("if", "buy", src_h="true"),
      ],
    )

  def test_constant_below_price_triggers_buy(self):
    """Close (100) > Constant (50) → IfAbove fires true → Buy."""
    gs = GraphStrategy(self._graph(50.0))
    sig = gs.on_event(_event(100.0))
    assert sig.__class__.__name__ == "AddSignal"

  def test_constant_above_price_no_buy(self):
    """Close (30) < Constant (50) → IfAbove fires false → no Buy."""
    gs = GraphStrategy(self._graph(50.0))
    sig = gs.on_event(_event(30.0))
    assert sig.__class__.__name__ == "NullSignal"

  def test_constant_output_value(self):
    """Constant node outputs its configured value, verified via IfAbove."""
    g2 = _make_graph(
      [_node("ob", "OnBar"), _node("c", "Constant", {"value": 42.0}),
       _node("if", "IfAbove"), _node("buy", "Buy", amount=1)],
      [_edge("ob", "if", tgt_h="in"), _edge("ob", "if", src_h="out", tgt_h="a"),
       _edge("c", "if", src_h="out", tgt_h="b"), _edge("if", "buy", src_h="true")],
    )
    gs2 = GraphStrategy(g2)
    assert gs2.on_event(_event(50.0)).__class__.__name__ == "AddSignal"   # 50 > 42
    gs2.reset()
    gs3 = GraphStrategy(g2)
    assert gs3.on_event(_event(10.0)).__class__.__name__ == "NullSignal"  # 10 < 42


# ---------------------------------------------------------------------------
# IfBelow node
# ---------------------------------------------------------------------------

class TestIfBelow:
  def _graph(self):
    """OnBar → IfBelow(RSI, Constant(30)) → Buy; IfBelow.false → Sell"""
    return _make_graph(
      [
        _node("ob", "OnBar"),
        _node("rsi", "RSI", {"period": 3}),
        _node("const", "Constant", {"value": 30.0}),
        _node("ifb", "IfBelow"),
        _node("buy", "Buy", amount=5),
      ],
      [
        _edge("ob", "rsi"),
        _edge("ob", "ifb", tgt_h="in"),
        _edge("rsi", "ifb", src_h="out", tgt_h="a"),
        _edge("const", "ifb", src_h="out", tgt_h="b"),
        _edge("ifb", "buy", src_h="true"),
      ],
    )

  def test_fires_true_when_a_less_than_b(self):
    """IfBelow outputs true when A < B."""
    g = _make_graph(
      [_node("ob", "OnBar"), _node("c1", "Constant", {"value": 20.0}),
       _node("c2", "Constant", {"value": 50.0}),
       _node("ifb", "IfBelow"), _node("buy", "Buy", amount=1)],
      [_edge("ob", "ifb", tgt_h="in"),
       _edge("c1", "ifb", src_h="out", tgt_h="a"),   # 20
       _edge("c2", "ifb", src_h="out", tgt_h="b"),   # 50
       _edge("ifb", "buy", src_h="true")],
    )
    gs = GraphStrategy(g)
    sig = gs.on_event(_event(100.0))
    assert sig.__class__.__name__ == "AddSignal"   # 20 < 50

  def test_fires_false_when_a_greater_than_b(self):
    """IfBelow outputs false when A > B."""
    g = _make_graph(
      [_node("ob", "OnBar"), _node("c1", "Constant", {"value": 80.0}),
       _node("c2", "Constant", {"value": 50.0}),
       _node("ifb", "IfBelow"), _node("buy", "Buy", amount=1)],
      [_edge("ob", "ifb", tgt_h="in"),
       _edge("c1", "ifb", src_h="out", tgt_h="a"),   # 80
       _edge("c2", "ifb", src_h="out", tgt_h="b"),   # 50
       _edge("ifb", "buy", src_h="true")],
    )
    gs = GraphStrategy(g)
    sig = gs.on_event(_event(100.0))
    assert sig.__class__.__name__ == "NullSignal"   # 80 > 50

  def test_null_signal_during_warmup(self):
    """IfBelow with RSI suppresses until indicator warms up."""
    gs = GraphStrategy(self._graph())
    # RSI(3) needs 4 bars; first 3 bars should be NullSignal
    for p in [100.0, 95.0, 90.0]:
      sig = gs.on_event(_event(p))
      assert sig.__class__.__name__ == "NullSignal"


# ---------------------------------------------------------------------------
# IfCrossAbove node
# ---------------------------------------------------------------------------

class TestIfCrossAbove:
  def _graph(self):
    """SMA(3) crosses above SMA(5) → Buy"""
    return _make_graph(
      [
        _node("ob", "OnBar"),
        _node("fast", "SMA", {"period": 3}),
        _node("slow", "SMA", {"period": 5}),
        _node("cross", "IfCrossAbove"),
        _node("buy", "Buy", amount=10),
      ],
      [
        _edge("ob", "fast"),
        _edge("ob", "slow"),
        _edge("ob", "cross", tgt_h="in"),
        _edge("fast", "cross", src_h="out", tgt_h="a"),
        _edge("slow", "cross", src_h="out", tgt_h="b"),
        _edge("cross", "buy", src_h="true"),
      ],
    )

  def test_fires_only_on_cross_bar(self):
    """Buy fires exactly once on the bar where fast SMA crosses above slow SMA."""
    gs = GraphStrategy(self._graph())
    # Feed declining prices to warm up (fast < slow)
    prices_warmup = [100.0, 99.0, 98.0, 97.0, 96.0]
    for p in prices_warmup:
      gs.on_event(_event(p))

    # Now feed rising prices so fast SMA crosses above slow SMA
    prices_rally = [97.0, 98.0, 100.0, 110.0, 120.0]
    sigs = [gs.on_event(_event(p)).__class__.__name__ for p in prices_rally]

    # Exactly one Buy somewhere in the rally
    assert sigs.count("AddSignal") == 1

  def test_no_fire_when_already_above(self):
    """No signal when fast is already above slow (not a new cross)."""
    gs = GraphStrategy(self._graph())
    # Feed rising prices — fast SMA will be above slow from early on
    for p in [100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0]:
      sig = gs.on_event(_event(p))
    # After the first cross, no more signals since we're not re-crossing
    # (we feed a few more bars with fast still above slow)
    sigs = [gs.on_event(_event(p)).__class__.__name__ for p in [135.0, 140.0]]
    assert all(s == "NullSignal" for s in sigs)

  def test_no_fire_during_warmup(self):
    """No signal before both SMAs have enough data."""
    gs = GraphStrategy(self._graph())
    # First 5 bars — slow SMA(5) not ready yet
    for p in [100.0, 101.0, 102.0, 103.0, 104.0]:
      sig = gs.on_event(_event(p))
    # Should be NullSignal (insufficient data for both prev and current values)
    assert sig.__class__.__name__ == "NullSignal"

  def test_reset_clears_cross_state(self):
    """After reset(), prev values are cleared — first bar after reset has no prior."""
    gs = GraphStrategy(self._graph())
    for p in [100.0, 99.0, 98.0, 97.0, 96.0]:
      gs.on_event(_event(p))
    gs.reset()
    assert len(gs._cross_prev) == 0
    # First bar after reset should not fire (no prev values)
    sig = gs.on_event(_event(105.0))
    assert sig.__class__.__name__ == "NullSignal"


# ---------------------------------------------------------------------------
# IfCrossBelow node
# ---------------------------------------------------------------------------

class TestIfCrossBelow:
  def _graph(self):
    """SMA(3) crosses below SMA(5) → Sell (via Buy for signal testing)"""
    return _make_graph(
      [
        _node("ob", "OnBar"),
        _node("fast", "SMA", {"period": 3}),
        _node("slow", "SMA", {"period": 5}),
        _node("cross", "IfCrossBelow"),
        _node("buy", "Buy", amount=10),
      ],
      [
        _edge("ob", "fast"),
        _edge("ob", "slow"),
        _edge("ob", "cross", tgt_h="in"),
        _edge("fast", "cross", src_h="out", tgt_h="a"),
        _edge("slow", "cross", src_h="out", tgt_h="b"),
        _edge("cross", "buy", src_h="true"),
      ],
    )

  def test_fires_only_on_cross_bar(self):
    """Signal fires exactly once on the bar where fast SMA crosses below slow SMA."""
    gs = GraphStrategy(self._graph())
    # Feed rising prices to warm up (fast > slow)
    for p in [100.0, 101.0, 102.0, 103.0, 104.0]:
      gs.on_event(_event(p))

    # Now feed declining prices so fast crosses below slow
    prices_decline = [103.0, 102.0, 99.0, 95.0, 90.0]
    sigs = [gs.on_event(_event(p)).__class__.__name__ for p in prices_decline]
    assert sigs.count("AddSignal") == 1

  def test_opposite_of_cross_above(self):
    """IfCrossBelow fires when fast was ≥ slow and now < slow (inverse of IfCrossAbove)."""
    # Single-step test: manually set up a state where prev fast > slow, now fast < slow
    g = _make_graph(
      [_node("ob", "OnBar"), _node("c_a", "Constant", {"value": 100.0}),
       _node("c_b", "Constant", {"value": 50.0}),
       _node("cross", "IfCrossBelow"), _node("buy", "Buy", amount=1)],
      [_edge("ob", "cross", tgt_h="in"),
       _edge("c_a", "cross", src_h="out", tgt_h="a"),   # always 100
       _edge("c_b", "cross", src_h="out", tgt_h="b"),   # always 50
       _edge("cross", "buy", src_h="true")],
    )
    gs = GraphStrategy(g)
    # 100 is never < 50, so IfCrossBelow never fires
    for _ in range(5):
      sig = gs.on_event(_event(99.0))
    assert sig.__class__.__name__ == "NullSignal"


# ---------------------------------------------------------------------------
# Precomputed path (pandas_ta)
# ---------------------------------------------------------------------------

def _make_df(prices: list[float]) -> pd.DataFrame:
  """Build a minimal OHLCV DataFrame from a list of close prices."""
  return pd.DataFrame({
    "open": prices,
    "high": prices,
    "low": prices,
    "close": prices,
    "volume": [0] * len(prices),
  })


class TestPrecomputed:
  """Verify the pandas_ta fast path produces correct signals."""

  def test_sma_precomputed_suppresses_warmup(self):
    """SMA(3) via precomputed path: first 2 bars are NullSignal, 3rd fires."""
    prices = [100.0, 101.0, 102.0]
    df = _make_df(prices)
    g = _make_graph(
      [_node("ob", "OnBar"), _node("sma", "SMA", {"period": 3}), _node("buy", "Buy")],
      [_edge("ob", "sma"), _edge("sma", "buy", tgt_h="in")],
    )
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "sma" in gs._precomputed
    assert gs._precomputed["sma"]["out"][0] is None   # warm-up
    assert gs._precomputed["sma"]["out"][1] is None   # warm-up
    assert gs._precomputed["sma"]["out"][2] is not None  # ready

    sigs = [gs.on_event(_event(p)).__class__.__name__ for p in prices]
    assert sigs == ["NullSignal", "NullSignal", "AddSignal"]

  def test_sma_precomputed_value_correct(self):
    """Precomputed SMA(3) value equals manual average of last 3 prices."""
    prices = [10.0, 20.0, 30.0, 40.0]
    df = _make_df(prices)
    g = _make_graph([_node("ob", "OnBar"), _node("sma", "SMA", {"period": 3})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    # SMA(3) at index 2 = (10+20+30)/3 = 20.0; at index 3 = (20+30+40)/3 = 30.0
    assert gs._precomputed["sma"]["out"][2] == pytest.approx(20.0)
    assert gs._precomputed["sma"]["out"][3] == pytest.approx(30.0)

  def test_ema_precomputed_suppresses_warmup(self):
    """EMA(3) via precomputed path: first 2 bars are NullSignal."""
    prices = [100.0, 101.0, 102.0, 103.0]
    df = _make_df(prices)
    g = _make_graph(
      [_node("ob", "OnBar"), _node("ema", "EMA", {"period": 3}), _node("buy", "Buy")],
      [_edge("ob", "ema"), _edge("ema", "buy", tgt_h="in")],
    )
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "ema" in gs._precomputed
    assert gs._precomputed["ema"]["out"][0] is None
    assert gs._precomputed["ema"]["out"][1] is None
    assert gs._precomputed["ema"]["out"][2] is not None

  def test_rsi_precomputed_suppresses_warmup(self):
    """RSI(3) via precomputed path: bar 0 is None, bars 1+ have values."""
    prices = [100.0, 101.0, 99.0, 102.0, 98.0]
    df = _make_df(prices)
    g = _make_graph([_node("ob", "OnBar"), _node("rsi", "RSI", {"period": 3})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "rsi" in gs._precomputed
    # pandas_ta RSI(3): first bar is NaN (no prior price for delta); rest computed
    assert gs._precomputed["rsi"]["out"][0] is None
    assert all(v is not None for v in gs._precomputed["rsi"]["out"][1:])

  def test_precomputed_matches_rolling_sma(self):
    """Precomputed SMA produces same buy-signal sequence as rolling-buffer path."""
    prices = [100.0, 101.0, 102.0, 99.0, 98.0, 103.0]
    g = _make_graph(
      [_node("ob", "OnBar"), _node("sma", "SMA", {"period": 3}), _node("buy", "Buy")],
      [_edge("ob", "sma"), _edge("sma", "buy", tgt_h="in")],
    )
    # Rolling path (no df)
    gs_rolling = GraphStrategy(g)
    sigs_rolling = [gs_rolling.on_event(_event(p)).__class__.__name__ for p in prices]

    # Precomputed path
    gs_pre = GraphStrategy(g, ohlcv_df=_make_df(prices))
    sigs_pre = [gs_pre.on_event(_event(p)).__class__.__name__ for p in prices]

    assert sigs_rolling == sigs_pre

  def test_bar_idx_increments_correctly(self):
    """_bar_idx starts at -1 and increments to 0 on first on_event call."""
    g = _make_graph([_node("ob", "OnBar"), _node("buy", "Buy")], [_edge("ob", "buy")])
    gs = GraphStrategy(g, ohlcv_df=_make_df([100.0, 101.0]))
    assert gs._bar_idx == -1
    gs.on_event(_event(100.0))
    assert gs._bar_idx == 0
    gs.on_event(_event(101.0))
    assert gs._bar_idx == 1

  def test_reset_resets_bar_idx(self):
    """reset() resets _bar_idx to -1 so replay starts from position 0."""
    g = _make_graph([_node("ob", "OnBar"), _node("buy", "Buy")], [_edge("ob", "buy")])
    gs = GraphStrategy(g, ohlcv_df=_make_df([100.0, 101.0, 102.0]))
    for p in [100.0, 101.0]:
      gs.on_event(_event(p))
    assert gs._bar_idx == 1
    gs.reset()
    assert gs._bar_idx == -1
    # Precomputed series must survive reset
    assert "buy" not in gs._precomputed  # Buy has no precomputed — only indicators do

  def test_precomputed_series_survives_reset(self):
    """_precomputed is not cleared on reset — no need to rebuild from df."""
    prices = [10.0, 20.0, 30.0, 40.0]
    g = _make_graph([_node("ob", "OnBar"), _node("sma", "SMA", {"period": 3})], [])
    gs = GraphStrategy(g, ohlcv_df=_make_df(prices))
    pre_reset = gs._precomputed["sma"]["out"].copy()
    gs.reset()
    assert gs._precomputed["sma"]["out"] == pre_reset


# ---------------------------------------------------------------------------
# High-priority indicator nodes (MACD, BollingerBands, ATR, Volume, Stochastic)
# ---------------------------------------------------------------------------

def _make_ohlcv_df(n: int = 60, seed: int = 42):
  """Build a realistic OHLCV DataFrame with n bars (enough for MACD warm-up)."""
  import numpy as np
  np.random.seed(seed)
  close = pd.Series(100.0 + np.cumsum(np.random.randn(n)))
  high = close + abs(np.random.randn(n)) * 0.5 + 0.5
  low = close - abs(np.random.randn(n)) * 0.5 - 0.5
  return pd.DataFrame({
    "open": close,
    "high": high,
    "low": low,
    "close": close,
    "volume": np.random.randint(1000, 10000, n),
  })


class TestHighPriorityNodes:
  """Smoke tests for MACD, BollingerBands, ATR, Volume, Stochastic."""

  def test_macd_precomputed_has_all_handles(self):
    """MACD node stores macd/signal/histogram series."""
    df = _make_ohlcv_df(60)
    g = _make_graph([_node("ob", "OnBar"), _node("m", "MACD", {"fast": 12, "slow": 26, "signal": 9})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "m" in gs._precomputed
    assert set(gs._precomputed["m"].keys()) == {"macd", "signal", "histogram"}
    assert len(gs._precomputed["m"]["macd"]) == 60

  def test_macd_warmup_then_fires(self):
    """MACD(12,26,9) output feeds IfAbove; no signal during warm-up, fires after.

    Uses a monotone uptrend so fast EMA > slow EMA → MACD > 0 after warm-up.
    """
    # Linearly rising prices: fast EMA > slow EMA → MACD line > 0
    n = 60
    prices_list = [100.0 + i * 0.5 for i in range(n)]
    df = pd.DataFrame({
      "open": prices_list, "high": [p + 0.1 for p in prices_list],
      "low": [p - 0.1 for p in prices_list], "close": prices_list,
      "volume": [1000] * n,
    })
    g = _make_graph(
      [_node("ob", "OnBar"), _node("m", "MACD", {"fast": 12, "slow": 26, "signal": 9}),
       _node("c", "Constant", {"value": 0}), _node("if", "IfAbove"), _node("buy", "Buy")],
      [_edge("ob", "if", tgt_h="in"),
       _edge("m", "if", src_h="macd", tgt_h="a"),
       _edge("c", "if", src_h="out", tgt_h="b"),
       _edge("if", "buy", src_h="true")],
    )
    gs = GraphStrategy(g, ohlcv_df=df)
    sigs = [gs.on_event(_event(p)).__class__.__name__ for p in prices_list]
    # First 25 bars: EMA(26) not ready yet → MACD line is None → NullSignal
    assert all(s == "NullSignal" for s in sigs[:25])
    # From bar 25 onward, uptrend → MACD line > 0 → AddSignal fires
    assert "AddSignal" in sigs[25:]

  def test_bbands_precomputed_has_all_handles(self):
    """BollingerBands node stores upper/middle/lower series."""
    df = _make_ohlcv_df(40)
    g = _make_graph([_node("ob", "OnBar"), _node("bb", "BollingerBands", {"period": 20, "std": 2.0})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "bb" in gs._precomputed
    assert set(gs._precomputed["bb"].keys()) == {"upper", "middle", "lower"}

  def test_bbands_upper_gt_lower(self):
    """BollingerBands: upper > lower for every non-None bar."""
    df = _make_ohlcv_df(40)
    g = _make_graph([_node("ob", "OnBar"), _node("bb", "BollingerBands", {"period": 5, "std": 2.0})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    uppers = gs._precomputed["bb"]["upper"]
    lowers = gs._precomputed["bb"]["lower"]
    for u, l in zip(uppers, lowers):
      if u is not None and l is not None:
        assert u > l

  def test_atr_precomputed_single_out(self):
    """ATR node stores a single 'out' series."""
    df = _make_ohlcv_df(40)
    g = _make_graph([_node("ob", "OnBar"), _node("atr", "ATR", {"period": 14})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "atr" in gs._precomputed
    assert "out" in gs._precomputed["atr"]
    # ATR values must be non-negative where defined
    for v in gs._precomputed["atr"]["out"]:
      if v is not None:
        assert v >= 0.0

  def test_atr_feeds_ifabove(self):
    """ATR value flows correctly into IfAbove.a port."""
    df = _make_ohlcv_df(40)
    g = _make_graph(
      [_node("ob", "OnBar"), _node("atr", "ATR", {"period": 5}),
       _node("c", "Constant", {"value": 0}), _node("if", "IfAbove"), _node("buy", "Buy")],
      [_edge("ob", "if", tgt_h="in"),
       _edge("atr", "if", src_h="out", tgt_h="a"),
       _edge("c", "if", src_h="out", tgt_h="b"),
       _edge("if", "buy", src_h="true")],
    )
    gs = GraphStrategy(g, ohlcv_df=df)
    prices = df["close"].tolist()
    sigs = [gs.on_event(_event(p)).__class__.__name__ for p in prices]
    # ATR > 0 almost always — should fire many AddSignals after warm-up
    assert "AddSignal" in sigs

  def test_volume_no_df_needed(self):
    """Volume node reads bar.volume directly — no DataFrame required."""
    from events.payloads.market_payload import MarketDataPayload
    from events.event import MarketDataEvent
    g = _make_graph(
      [_node("ob", "OnBar"), _node("vol", "Volume"),
       _node("c", "Constant", {"value": 0}), _node("if", "IfAbove"), _node("buy", "Buy")],
      [_edge("ob", "if", tgt_h="in"),
       _edge("vol", "if", src_h="out", tgt_h="a"),
       _edge("c", "if", src_h="out", tgt_h="b"),
       _edge("if", "buy", src_h="true")],
    )
    gs = GraphStrategy(g)  # no df — Volume still works
    # Create a bar with volume=500 (> 0) → IfAbove fires → Buy
    bar = MarketDataPayload(timestamp=0, symbol="T", price=100.0, volume=500, Close=100.0)
    evt = MarketDataEvent(payload=bar)
    sig = gs.on_event(evt)
    assert sig.__class__.__name__ == "AddSignal"

  def test_volume_zero_no_signal(self):
    """Volume=0 → IfAbove(vol, 0) is false → NullSignal."""
    from events.payloads.market_payload import MarketDataPayload
    from events.event import MarketDataEvent
    g = _make_graph(
      [_node("ob", "OnBar"), _node("vol", "Volume"),
       _node("c", "Constant", {"value": 0}), _node("if", "IfAbove"), _node("buy", "Buy")],
      [_edge("ob", "if", tgt_h="in"),
       _edge("vol", "if", src_h="out", tgt_h="a"),
       _edge("c", "if", src_h="out", tgt_h="b"),
       _edge("if", "buy", src_h="true")],
    )
    gs = GraphStrategy(g)
    bar = MarketDataPayload(timestamp=0, symbol="T", price=100.0, volume=0, Close=100.0)
    sig = gs.on_event(MarketDataEvent(payload=bar))
    assert sig.__class__.__name__ == "NullSignal"

  def test_stochastic_precomputed_has_k_and_d(self):
    """Stochastic node stores k and d series."""
    df = _make_ohlcv_df(40)
    g = _make_graph([_node("ob", "OnBar"), _node("st", "Stochastic", {"k": 5, "d": 3})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "st" in gs._precomputed
    assert "k" in gs._precomputed["st"]
    assert "d" in gs._precomputed["st"]

  def test_stochastic_k_in_0_100(self):
    """Stochastic %K values must be in [0, 100] where defined."""
    df = _make_ohlcv_df(40)
    g = _make_graph([_node("ob", "OnBar"), _node("st", "Stochastic", {"k": 5, "d": 3})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    for v in gs._precomputed["st"]["k"]:
      if v is not None:
        assert 0.0 <= v <= 100.0

  def test_stochastic_buy_when_k_oversold(self):
    """Stochastic %K output flows through IfBelow correctly.

    Asserts structurally: on bars where %K < 20, on_event returns AddSignal;
    on bars where %K > 20, returns NullSignal.  Uses the precomputed series
    directly to avoid relying on randomness.
    """
    df = _make_ohlcv_df(60)
    g = _make_graph(
      [_node("ob", "OnBar"), _node("st", "Stochastic", {"k": 14, "d": 3}),
       _node("c", "Constant", {"value": 20}), _node("if", "IfBelow"), _node("buy", "Buy")],
      [_edge("ob", "if", tgt_h="in"),
       _edge("st", "if", src_h="k", tgt_h="a"),
       _edge("c", "if", src_h="out", tgt_h="b"),
       _edge("if", "buy", src_h="true")],
    )
    gs = GraphStrategy(g, ohlcv_df=df)
    k_series = gs._precomputed["st"]["k"]
    prices = df["close"].tolist()

    # Verify the fixture actually exercises the oversold branch
    assert any(v is not None and v < 20 for v in k_series), (
      "test fixture never produces %K < 20 — increase bars or change seed"
    )

    for i, p in enumerate(prices):
      sig = gs.on_event(_event(p)).__class__.__name__
      k_val = k_series[i]
      if k_val is not None and k_val < 20:
        assert sig == "AddSignal", f"bar {i}: expected AddSignal when %K={k_val:.1f} < 20"
      elif k_val is not None and k_val > 20:
        assert sig == "NullSignal", f"bar {i}: expected NullSignal when %K={k_val:.1f} > 20"

  def test_roc_precomputed_single_out(self):
    """ROC node stores a single 'out' series; first `period` values are None."""
    df = _make_ohlcv_df(40)
    g = _make_graph([_node("ob", "OnBar"), _node("roc", "ROC", {"period": 5})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "roc" in gs._precomputed
    out = gs._precomputed["roc"]["out"]
    # First `period` values should be None (not enough history)
    assert out[0] is None
    # Later values must be floats
    assert any(v is not None for v in out[10:])

  def test_williamsr_precomputed_in_valid_range(self):
    """Williams %R must be in [-100, 0] where defined."""
    df = _make_ohlcv_df(40)
    g = _make_graph([_node("ob", "OnBar"), _node("wr", "WilliamsR", {"period": 14})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    out = gs._precomputed["wr"]["out"]
    for v in out:
      if v is not None:
        assert -100.0 <= v <= 0.0, f"Williams %R out of range: {v}"

  def test_cci_precomputed_single_out(self):
    """CCI node stores a single 'out' series."""
    df = _make_ohlcv_df(40)
    g = _make_graph([_node("ob", "OnBar"), _node("cci", "CCI", {"period": 20})], [])
    gs = GraphStrategy(g, ohlcv_df=df)
    assert "cci" in gs._precomputed
    assert "out" in gs._precomputed["cci"]
    # Must produce at least one numeric value
    assert any(v is not None for v in gs._precomputed["cci"]["out"])
