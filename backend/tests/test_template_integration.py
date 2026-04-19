"""
Integration tests for strategy templates.

These tests mirror each frontend template's graph payload in Python and run
it end-to-end through GraphStrategy (single-asset) or run_cross_sectional
(universe). They're the safety net: if a refactor breaks a template, these
tests fail before the user tries to load it on the builder.

Scope: one test per pattern (DCA, cross, mean reversion, breakout, combined
indicator, fundamentals, universe). Not every template is covered here —
the unit tests in test_graph_strategy.py and test_cross_sectional.py verify
individual node behaviour; this file checks that the *full template graph*
survives the full pipeline without exceptions.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Engine-stub trick (same pattern as test_graph_strategy.py) so GraphStrategy
# can be imported without the trading_engine submodule on sys.path.
# ---------------------------------------------------------------------------

def _make_engine_stubs():
  evt_mod = types.ModuleType("events")
  evt_mod.event = types.ModuleType("events.event")
  class _MarketDataEvent:
    def __init__(self, payload): self.payload = payload
  evt_mod.event.MarketDataEvent = _MarketDataEvent
  sys.modules.setdefault("events", evt_mod)
  sys.modules.setdefault("events.event", evt_mod.event)

  pay_mod = types.ModuleType("events.payloads.market_payload")
  class _MarketDataPayload:
    def __init__(self, *, timestamp=0, symbol="TEST", price=100.0, volume=0,
                 Open=None, High=None, Low=None, Close=None):
      self.timestamp = timestamp
      self.symbol = symbol
      self.price = price
      self.volume = volume
      self.Open = Open or price
      self.High = High or price
      self.Low = Low or price
      self.Close = Close or price
  pay_mod.MarketDataPayload = _MarketDataPayload
  sys.modules.setdefault("events.payloads", types.ModuleType("events.payloads"))
  sys.modules.setdefault("events.payloads.market_payload", pay_mod)

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

  enum_mod = types.ModuleType("common.enums")
  class _Side: BUY = "buy"; SELL = "sell"
  class _OrderType: MARKET = "market"
  enum_mod.Side = _Side
  enum_mod.OrderType = _OrderType
  sys.modules.setdefault("common", types.ModuleType("common"))
  sys.modules.setdefault("common.enums", enum_mod)

_make_engine_stubs()

from background.tasks.graph_strategy import GraphStrategy  # noqa: E402
from background.tasks.cross_sectional import run_cross_sectional  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(price: float, volume: float = 1_000_000):
  from events.event import MarketDataEvent
  from events.payloads.market_payload import MarketDataPayload
  return MarketDataEvent(payload=MarketDataPayload(
    timestamp=0, symbol="TEST", price=price, volume=volume, Close=price,
  ))


def _run(graph: dict, prices: list[float], *,
         initial_capital: float = 10_000.0,
         fundamentals_df=None,
         ohlcv_df=None) -> dict:
  """
  Feed a price series through the strategy. Returns counts + the last signal.
  """
  gs = GraphStrategy(
    graph,
    initial_capital=initial_capital,
    fundamentals_df=fundamentals_df,
    ohlcv_df=ohlcv_df,
  )
  adds = 0
  closes = 0
  for p in prices:
    sig = gs.on_event(_event(p))
    name = sig.__class__.__name__
    if name == "AddSignal":
      adds += 1
    elif name == "CloseSignal":
      closes += 1
  return {"adds": adds, "closes": closes, "bars": len(prices)}


def _ohlcv(prices: list[float], volume: float = 1_000_000) -> pd.DataFrame:
  """Build an OHLCV DataFrame that precompute paths can consume."""
  idx = pd.date_range("2024-01-01", periods=len(prices), freq="D", tz="UTC")
  return pd.DataFrame({
    "open": prices, "high": prices, "low": prices, "close": prices,
    "volume": [volume] * len(prices),
  }, index=idx)


# ---------------------------------------------------------------------------
# Regular (single-asset) template patterns
# ---------------------------------------------------------------------------

class TestDcaTemplate:
  def test_dca_buys_every_bar(self):
    """Simple DCA — OnBar → Buy. Every bar should emit an AddSignal."""
    graph = {
      "nodes": [
        {"id": "trig", "type": "OnBar", "data": {}},
        {"id": "buy",  "type": "Buy",   "data": {"amount": 1}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "sourceHandle": "out",
         "target": "buy", "targetHandle": "in"},
      ],
    }
    result = _run(graph, [100.0, 101.0, 102.0, 103.0, 104.0])
    assert result["adds"] == 5
    assert result["closes"] == 0


class TestGoldenCross:
  def test_sma_cross_produces_signal(self):
    """Golden Cross — SMA(3) crosses above SMA(6) on a rising series."""
    graph = {
      "nodes": [
        {"id": "trig", "type": "OnBar", "data": {}},
        {"id": "fast", "type": "SMA", "data": {"params": {"period": 3}}},
        {"id": "slow", "type": "SMA", "data": {"params": {"period": 6}}},
        {"id": "cross", "type": "IfCrossAbove", "data": {}},
        {"id": "buy", "type": "Buy", "data": {"amount": 1}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "fast", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e2", "source": "trig", "target": "slow", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e3", "source": "trig", "target": "cross", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e4", "source": "fast", "target": "cross", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e5", "source": "slow", "target": "cross", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e6", "source": "cross", "target": "buy", "sourceHandle": "true", "targetHandle": "in"},
      ],
    }
    # Flat then rising — fast SMA eventually crosses above slow.
    prices = [100.0] * 8 + [101, 102, 104, 107, 111, 116, 122]
    result = _run(graph, prices)
    assert result["adds"] >= 1


class TestRsiMeanReversion:
  def test_rsi_oversold_buy_overbought_sell(self):
    graph = {
      "nodes": [
        {"id": "trig", "type": "OnBar", "data": {}},
        {"id": "rsi",  "type": "RSI",   "data": {"params": {"period": 5}}},
        {"id": "lo",   "type": "Constant", "data": {"params": {"value": 30}}},
        {"id": "hi",   "type": "Constant", "data": {"params": {"value": 70}}},
        {"id": "ifB",  "type": "IfBelow", "data": {}},
        {"id": "ifA",  "type": "IfAbove", "data": {}},
        {"id": "buy",  "type": "Buy",  "data": {"amount": 1}},
        {"id": "sell", "type": "Sell", "data": {"size_type": "all"}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "rsi", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e2", "source": "trig", "target": "ifB", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e3", "source": "rsi",  "target": "ifB", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e4", "source": "lo",   "target": "ifB", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e5", "source": "ifB",  "target": "buy", "sourceHandle": "true", "targetHandle": "in"},
        {"id": "e6", "source": "trig", "target": "ifA", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e7", "source": "rsi",  "target": "ifA", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e8", "source": "hi",   "target": "ifA", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e9", "source": "ifA",  "target": "sell", "sourceHandle": "true", "targetHandle": "in"},
      ],
    }
    # Sharp selloff then rally — RSI should dip below 30 then rise above 70.
    prices = [100, 95, 90, 85, 80, 75, 70] + [75, 85, 95, 105, 115, 125, 135]
    result = _run(graph, prices, ohlcv_df=_ohlcv(prices))
    # At least one entry and one exit
    assert result["adds"] >= 1
    assert result["closes"] >= 1


class TestAndCombinator:
  def test_and_requires_both_inputs(self):
    """Gate a Buy behind both RSI oversold AND close > SMA."""
    graph = {
      "nodes": [
        {"id": "trig", "type": "OnBar", "data": {}},
        {"id": "rsi",  "type": "RSI",   "data": {"params": {"period": 5}}},
        {"id": "lo",   "type": "Constant", "data": {"params": {"value": 30}}},
        {"id": "sma",  "type": "SMA",   "data": {"params": {"period": 3}}},
        {"id": "data", "type": "Data",  "data": {}},
        {"id": "ifRsi", "type": "IfBelow", "data": {}},
        {"id": "ifPri", "type": "IfAbove", "data": {}},
        {"id": "and",   "type": "And",     "data": {}},
        {"id": "buy",   "type": "Buy",     "data": {"amount": 1}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "rsi",   "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e2", "source": "trig", "target": "ifRsi", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e3", "source": "rsi",  "target": "ifRsi", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e4", "source": "lo",   "target": "ifRsi", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e5", "source": "trig", "target": "ifPri", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e6", "source": "data", "target": "ifPri", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e7", "source": "sma",  "target": "ifPri", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e8", "source": "ifRsi", "target": "and",  "sourceHandle": "true", "targetHandle": "a"},
        {"id": "e9", "source": "ifPri", "target": "and",  "sourceHandle": "true", "targetHandle": "b"},
        {"id": "e10", "source": "and", "target": "buy",   "sourceHandle": "true", "targetHandle": "in"},
      ],
    }
    # Price never goes down → RSI oversold never triggers → no buy at all
    rising = [100 + i for i in range(20)]
    result = _run(graph, rising, ohlcv_df=_ohlcv(rising))
    assert result["adds"] == 0


class TestRiskStack:
  def test_stop_loss_exits_position(self):
    graph = {
      "nodes": [
        {"id": "trig", "type": "OnBar", "data": {}},
        {"id": "buy",  "type": "Buy",   "data": {"amount": 1}},
        {"id": "sl",   "type": "StopLoss", "data": {"params": {"pct": 5.0}}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "buy", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e2", "source": "trig", "target": "sl",  "sourceHandle": "out", "targetHandle": "in"},
      ],
    }
    # Buy at 100, then slow drop past the -5% stop.
    result = _run(graph, [100.0, 98.0, 95.0, 92.0])
    assert result["adds"] >= 1
    assert result["closes"] >= 1


# ---------------------------------------------------------------------------
# Fundamental templates
# ---------------------------------------------------------------------------

class TestFundamentalTemplates:
  def _fund_df(self, rows: list[dict]):
    return pd.DataFrame(rows)

  def test_pe_screen_buys_cheap_sells_rich(self):
    graph = {
      "nodes": [
        {"id": "trig", "type": "OnBar", "data": {}},
        {"id": "pe",   "type": "PE",    "data": {}},
        {"id": "lo",   "type": "Constant", "data": {"params": {"value": 15}}},
        {"id": "hi",   "type": "Constant", "data": {"params": {"value": 25}}},
        {"id": "ifB",  "type": "IfBelow", "data": {}},
        {"id": "ifA",  "type": "IfAbove", "data": {}},
        {"id": "buy",  "type": "Buy",  "data": {"size_type": "pct_equity", "amount": 10}},
        {"id": "sell", "type": "Sell", "data": {"size_type": "all"}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "ifB", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e2", "source": "pe",   "target": "ifB", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e3", "source": "lo",   "target": "ifB", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e4", "source": "ifB",  "target": "buy", "sourceHandle": "true", "targetHandle": "in"},
        {"id": "e5", "source": "trig", "target": "ifA", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e6", "source": "pe",   "target": "ifA", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e7", "source": "hi",   "target": "ifA", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e8", "source": "ifA",  "target": "sell", "sourceHandle": "true", "targetHandle": "in"},
      ],
    }
    # Price 100 constant. TTM EPS starts at 10 (PE=10, cheap→buy) then falls to 3 (PE≈33, rich→sell).
    fund = self._fund_df([
      {"ttm_eps": 10.0, "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": 10.0, "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": 3.0,  "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": 3.0,  "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
    ])
    result = _run(graph, [100.0] * 4, fundamentals_df=fund)
    assert result["adds"] >= 1
    assert result["closes"] >= 1

  def test_dividend_screen_triggers_on_yield(self):
    graph = {
      "nodes": [
        {"id": "trig", "type": "OnBar", "data": {}},
        {"id": "dy",   "type": "DividendYield", "data": {}},
        {"id": "hi",   "type": "Constant", "data": {"params": {"value": 4}}},
        {"id": "ifA",  "type": "IfAbove", "data": {}},
        {"id": "buy",  "type": "Buy",  "data": {"size_type": "pct_equity", "amount": 10}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "ifA", "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e2", "source": "dy",   "target": "ifA", "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e3", "source": "hi",   "target": "ifA", "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e4", "source": "ifA",  "target": "buy", "sourceHandle": "true", "targetHandle": "in"},
      ],
    }
    # $5 TTM dividend on $100 price → 5% yield, above 4% threshold.
    fund = self._fund_df([
      {"ttm_eps": None, "ttm_div_per_share": 5.0, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": None, "ttm_div_per_share": 5.0, "roe": None, "profit_margin": None, "debt_to_equity": None},
    ])
    result = _run(graph, [100.0, 100.0], fundamentals_df=fund, initial_capital=10_000)
    assert result["adds"] >= 1

  def test_eps_growth_cross(self):
    """EPS crossing above a baseline → buy; back below → sell."""
    graph = {
      "nodes": [
        {"id": "trig", "type": "OnBar", "data": {}},
        {"id": "eps",  "type": "EPS",   "data": {}},
        {"id": "base", "type": "Constant", "data": {"params": {"value": 6}}},
        {"id": "up",   "type": "IfCrossAbove", "data": {}},
        {"id": "dn",   "type": "IfCrossBelow", "data": {}},
        {"id": "buy",  "type": "Buy",  "data": {"size_type": "pct_equity", "amount": 10}},
        {"id": "sell", "type": "Sell", "data": {"size_type": "all"}},
      ],
      "edges": [
        {"id": "e1", "source": "trig", "target": "up",   "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e2", "source": "eps",  "target": "up",   "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e3", "source": "base", "target": "up",   "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e4", "source": "up",   "target": "buy",  "sourceHandle": "true", "targetHandle": "in"},
        {"id": "e5", "source": "trig", "target": "dn",   "sourceHandle": "out", "targetHandle": "in"},
        {"id": "e6", "source": "eps",  "target": "dn",   "sourceHandle": "out", "targetHandle": "a"},
        {"id": "e7", "source": "base", "target": "dn",   "sourceHandle": "out", "targetHandle": "b"},
        {"id": "e8", "source": "dn",   "target": "sell", "sourceHandle": "true", "targetHandle": "in"},
      ],
    }
    # EPS 5, 5, 7 (cross up), 8, 5 (cross down), 5
    fund = pd.DataFrame([
      {"ttm_eps": 5.0, "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": 5.0, "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": 7.0, "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": 8.0, "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": 5.0, "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
      {"ttm_eps": 5.0, "ttm_div_per_share": None, "roe": None, "profit_margin": None, "debt_to_equity": None},
    ])
    result = _run(graph, [100.0] * 6, fundamentals_df=fund, initial_capital=10_000)
    assert result["adds"] >= 1
    assert result["closes"] >= 1


# ---------------------------------------------------------------------------
# Universe (factor) templates
# ---------------------------------------------------------------------------

@dataclass
class _Bar:
  time: datetime
  close: float
  volume: float


def _bars(start: datetime, closes: list[float], vol: float = 1e6) -> list[_Bar]:
  return [_Bar(time=start + timedelta(days=i), close=c, volume=vol)
          for i, c in enumerate(closes)]


class TestUniverseTemplates:
  def test_momentum_template_runs(self):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    n = 80
    data = {
      "UP":   _bars(start, [100 * (1.002 ** i) for i in range(n)]),
      "FLAT": _bars(start, [100.0] * n),
      "DOWN": _bars(start, [100 * (0.998 ** i) for i in range(n)]),
    }
    graph = {
      "nodes": [
        {"id": "f", "type": "Momentum", "data": {"params": {"lookback": 30, "skip": 2}}},
        {"id": "r", "type": "Rank", "data": {"params": {
          "top_pct": 0.34, "bottom_pct": 0.34, "rebalance_days": 10, "mode": "long_only"}}},
      ],
      "edges": [{"id": "e1", "source": "f", "sourceHandle": "out",
                 "target": "r", "targetHandle": "in"}],
    }
    result = run_cross_sectional(
      symbols=["UP", "FLAT", "DOWN"],
      start_date=None, end_date=None, timeframe="1D",
      graph=graph, initial_capital=10_000.0,
      ohlc_fetcher=lambda s, tf, a, b: data.get(s, []),
    )
    assert result["factor_label"].startswith("Momentum")
    assert len(result["nav_series"]) == n
    assert result["metrics"]["total_return"] > 0  # buying UP should be profitable

  def test_value_template_runs(self):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    n = 40
    data = {
      "CHEAP": _bars(start, [100.0] * n),
      "MID":   _bars(start, [100.0] * n),
      "RICH":  _bars(start, [100.0] * n),
    }
    eps = {"CHEAP": 10.0, "MID": 4.0, "RICH": 1.0}
    def fetch_fund(sym):
      period_end = datetime(2023, 12, 31, tzinfo=timezone.utc)
      available = period_end + timedelta(days=15)
      class _R:
        def __init__(self, eps):
          self.period_end = period_end
          self.available_from = available
          self.diluted_eps = eps
      return [_R(eps[sym])]
    graph = {
      "nodes": [
        {"id": "f", "type": "Value", "data": {}},
        {"id": "r", "type": "Rank", "data": {"params": {
          "top_pct": 0.34, "bottom_pct": 0.34, "rebalance_days": 10, "mode": "long_only"}}},
      ],
      "edges": [{"id": "e1", "source": "f", "sourceHandle": "out",
                 "target": "r", "targetHandle": "in"}],
    }
    result = run_cross_sectional(
      symbols=["CHEAP", "MID", "RICH"],
      start_date=None, end_date=None, timeframe="1D",
      graph=graph, initial_capital=10_000.0,
      ohlc_fetcher=lambda s, tf, a, b: data.get(s, []),
      fundamentals_fetcher=fetch_fund,
    )
    assert result["factor_label"] == "Value (earnings yield)"
    assert len(result["nav_series"]) == n
