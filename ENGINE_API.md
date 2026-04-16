# Trading Engine API Reference

Read this before modifying `backend/background/tasks/backtest.py` or adding strategy support.
All information is verified against the actual engine source code.

---

## Import pattern

The engine lives at `trading_engine/` (git submodule).
Import it inside the Celery task function — **never at module level** — to avoid a `common/` namespace collision with the backend's `app_common/`:

```python
ENGINE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'trading_engine')
if ENGINE_PATH not in sys.path:
    sys.path.insert(0, ENGINE_PATH)

from core.engine import Engine
from strategies.dca import DCA
from events.event import MarketDataEvent
from events.payloads.market_payload import MarketDataPayload
```

---

## What the engine takes as input

### 1. `Engine(initial_cash: float)`
```python
engine = Engine(initial_cash=10000.0)
```

### 2. `engine.add_strategy(strategy)`
Currently available strategies:
- `DCA(buyframe: int, buy_amount: float)` — buys `buy_amount` units every time ≥ `buyframe` calendar days have passed since the last buy. `buyframe` is compared as a YYYYMMDD integer difference (e.g. `20130115 - 20130108 = 7`).
- `EDCA(...)` — enhanced variant

### 3. `engine.push_event(MarketDataEvent(timestamp, payload))`

```python
# timestamp: int in YYYYMMDD format (e.g. 20130115)
# All timestamps throughout the engine are YYYYMMDD ints — never datetime objects

ts = int(bar.time.strftime("%Y%m%d"))

payload = MarketDataPayload(
    timestamp=ts,       # int (YYYYMMDD)
    symbol=str,         # e.g. "AAPL"
    price=float,        # used for order matching — set to bar.close
    volume=int,         # set to 0 if unknown
    Open=float|None,
    High=float|None,
    Low=float|None,
    Close=float|None,
)

engine.push_event(MarketDataEvent(timestamp=ts, payload=payload))
```

### 4. `engine.run()`
Processes all queued events. Call once after all `push_event()` calls.

---

## What the engine gives as output

### `portfolio = engine._portfolio`

#### Financial summary
```python
portfolio.current_capital   # float — final portfolio value
portfolio.total_return      # float — percentage, e.g. 168.15 means 168.15%
                            # ⚠️ divide by 100 before storing in DB (DB expects decimal)
```

#### `portfolio.get_trading_metrics()` → `TradingMetrics`
```python
metrics.total_trades        # int
metrics.winning_trades      # int — count of winning trades
metrics.losing_trades       # int — count of losing trades
metrics.win_rate            # float — percentage, e.g. 64.61 means 64.61%
                            # ⚠️ divide by 100 before storing in DB
metrics.profit_factor       # float
metrics.avg_win             # float — average profit of winning trades
metrics.avg_loss            # float — average loss of losing trades
metrics.win_loss_ratio      # float
metrics.avg_holding_period  # int — average YYYYMMDD int difference
metrics.total_profit        # float
metrics.total_loss          # float
metrics.net_profit          # float
metrics.largest_win         # float
metrics.largest_loss        # float
metrics.max_consecutive_wins    # int
metrics.max_consecutive_losses  # int
metrics.expectancy          # float
metrics.sharpe_ratio        # float | None  ← always None (not implemented yet)
metrics.max_drawdown        # float | None  ← always None (not implemented yet)
```

#### `portfolio._trades` → `list[dict]`
Each dict is a **closed round-trip** (one entry + one exit). There is no record of still-open positions.

```python
{
    "order_id":       int,
    "symbol":         str,
    "side":           Side enum   # Side.BUY or Side.SELL — the entry side
                                  # convert with: side.value.lower() → "buy" / "sell"
    "entry_price":    float,
    "exit_price":     float,
    "quantity":       float,
    "entry_time":     int,        # YYYYMMDD — when position was opened
    "exit_time":      int,        # YYYYMMDD — when position was closed (overwritten by add_trade)
    "holding_period": int,        # exit_time - entry_time as YYYYMMDD int difference
    "commission":     float,      # always 0.0 currently
    "profit_loss":    float,      # positive = win, negative = loss
    "is_winning":     bool,
    "exit_type":      str,        # "take_profit" | "stop_loss" | "manual"
    "take_profit":    float|None,
    "stop_loss":      float|None,
}
```

> **Chart markers:** To show `{B}` on entry bars and `{S}` on exit bars, store two `Trade` DB rows per dict — one `side=buy` at `entry_time`/`entry_price`, one `side=sell` at `exit_time`/`exit_price`. Only add the sell row if `exit_time != entry_time`.

---

## Signals (Strategy → Engine communication)

A strategy's `on_event(event)` returns a `Signal`:

```python
from strategies.signal import AddSignal, NullSignal, CancelSignal, ModifySignal, CloseSignal

AddSignal(
    symbol=str,
    side=Side.BUY | Side.SELL,
    type=OrderType.MARKET | OrderType.LIMIT,
    price=float,            # entry price
    quantity=float,         # units to trade
    take_profit=float|None, # auto-close when price hits this level (above entry for BUY)
    stop_loss=float|None,   # auto-close when price hits this level (below entry for BUY)
)

NullSignal()  # do nothing this bar
```

> ⚠️ `CancelSignal`, `ModifySignal`, `CloseSignal` are **silently ignored** in `OrderManager.handle_signal()` — not implemented yet.

---

## How order filling works (per bar)

Each `MarketDataEvent` triggers this sequence:

```
1. _fill_submitted_orders()
   → pending orders that match price get filled (MARKET always fills, LIMIT fills if price crosses)
   → filled orders become open positions in PositionManager

2. _close_trades()
   → every open position checks its take_profit / stop_loss against current bar price
   → triggered positions close → round-trip recorded in portfolio._trades

3. _run_strategies()
   → strategy.on_event() called → signal returned → new order queued for next bar
```

> ⚠️ TP/SL are checked on the **same bar** the position opened, not the next one.
> A `take_profit = price * 1.05` may trigger immediately if the bar's price is already above it.
> Use percentage-based values and account for this (current setting: +5% TP, -3% SL).

---

## What is NOT yet implemented

| Feature | Location | Notes |
|---------|----------|-------|
| Sharpe ratio | `portfolio.get_trading_metrics()` | Always returns `None` |
| Max drawdown | `portfolio.get_trading_metrics()` | Always returns `None` |
| Annualized return / Volatility | Not in engine | Must compute externally |
| Equity curve (per-bar NAV) | Not emitted | No hook exists yet |
| CancelSignal / ModifySignal / CloseSignal | `OrderManager.handle_signal()` | Silently ignored |
| Realized P&L | `PositionManager._realized_pnl` | Never updated on close |
| JSON/graph-driven strategy | `backtest.py` | Hardcoded DCA for MVP |
| Multiple strategy support | `Engine.add_strategy()` | ✅ Works, can call multiple times |
