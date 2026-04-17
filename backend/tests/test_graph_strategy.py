"""
Tests for GraphStrategy — the per-bar graph interpreter.

These tests are pure-Python and do NOT require the trading engine on sys.path.
Engine types (AddSignal, NullSignal, etc.) are replaced with lightweight stubs.
"""

import sys
import types
import pytest
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

  def test_flat_prices_returns_none_or_100(self):
    """Flat prices → no losses → RSI = 100."""
    g = _make_graph([_node("ob", "OnBar"), _node("rsi", "RSI", {"period": 5})], [])
    gs = GraphStrategy(g)
    gs._price_buffers["rsi"] = deque([100.0] * 6, maxlen=7)
    result = gs._rsi("rsi", 5)
    assert result == 100.0

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
    """With a Sell node present, second Buy is suppressed until Sell fires."""
    # Use IfAbove to control Buy vs Sell separately
    g = _make_graph(
      [_node("ob", "OnBar"), _node("buy", "Buy", amount=5.0), _node("sell", "Sell")],
      [_edge("ob", "buy")],   # Sell has NO connection — never triggers
    )
    # Sell node exists but is unconnected → _has_exit=True, but Sell never fires
    gs = GraphStrategy(g)
    assert gs._has_exit is True

    sig1 = gs.on_event(_event(100.0))
    assert sig1.__class__.__name__ == "AddSignal"   # first buy goes through
    assert gs._in_position is True

    sig2 = gs.on_event(_event(101.0))
    assert sig2.__class__.__name__ == "NullSignal"  # blocked — still in position

    sig3 = gs.on_event(_event(102.0))
    assert sig3.__class__.__name__ == "NullSignal"  # still blocked

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
  # Warm up
  for p in [100.0, 101.0, 102.0]:
    gs.on_event(_event(p))
  assert len(gs._price_buffers) > 0

  gs.reset()
  assert len(gs._price_buffers) == 0
  assert len(gs._ema_values) == 0
