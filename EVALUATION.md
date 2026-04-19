# Evaluation

How the system was validated and what it can't do. Written for the FYP
examiner — not every paragraph is a demo item, but every claim here
matches something in the repo that can be pointed at.

---

## 1. What "works" means

The project is a web-based backtester. A correct system must:

1. Accept a user-authored strategy (visual graph → JSON) and a market-data
   selection, then return deterministic backtest results.
2. Ship the same numbers end-to-end: what the engine computes must match
   what is stored in the DB and what the UI renders.
3. Survive the messy parts of the real world: missing OHLC windows,
   quarterly fundamentals that lag price by ~45 days, divide-by-zero in
   ratios, empty trade logs, and malformed user input.

The remainder of this doc maps each of those to the evidence in the repo.

---

## 2. Automated test coverage

**257 tests** collected across 16 files under [backend/tests/](backend/tests/).
A single `pytest -q --ignore=tests/test_e2e.py` run stays green on main.
`test_e2e.py` is excluded from CI because it requires a live Celery
worker; it is run manually before deployments.

| Suite | Focus | Count |
|---|---|---|
| `test_auth.py` | register / login / verify / JWT dependency | |
| `test_backtests.py` | POST/GET routes, batch fan-out, compare, status polling | |
| `test_datasets.py` | BYO OHLC CSV upload — header detection, bad rows, quotas | |
| `test_graph_strategy.py` | Every node evaluator — indicators, fundamentals, conditions, math, orders, risk | |
| `test_template_integration.py` | **10 built-in templates run end-to-end** against synthetic OHLC | 10 |
| `test_cross_sectional.py` | Momentum / Value factor ranking (cross-sectional) | |
| `test_market_refresh*.py` | yfinance + FMP fetchers, gap-fill, retry/backoff | |
| `test_fundamentals_refresh*.py` | Quarterly point-in-time availability guarantees | |
| `test_perf_metrics.py` | Sharpe, Sortino, Calmar, max-DD — edge cases (all-zero returns, single trade) | 10 |
| `test_auto_refresh.py` | Auto-fetch when a backtest window is uncovered | |

The graph-strategy suite is the load-bearing test — it pins evaluator
behaviour per node, so changes to one node can't silently regress another.

---

## 3. Node coverage

**46 node types** are currently exposed in the palette
([`frontend/src/routes/app/backtests/new/+page.svelte`](frontend/src/routes/app/backtests/new/+page.svelte))
and every one has a corresponding evaluator in
[`backend/background/tasks/graph_strategy.py`](backend/background/tasks/graph_strategy.py).

| Category | Nodes |
|---|---|
| Triggers / data | OnBar, Data, Constant |
| Indicators | SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Volume, Stochastic, ROC, Williams %R, CCI, KDJ, MFI, OBV, KST |
| Fundamentals | PE, EPS, ROE, DividendYield |
| Math | Add, Subtract, Multiply, Divide |
| Conditions | IfAbove, IfBelow, IfCrossAbove, IfCrossBelow, And, Or, Not, TimeWindow, Position |
| Orders | Buy, Sell |
| Risk exits | StopLoss, TakeProfit, TrailingStop |
| Universe factors | Momentum, Reversal, LowVol, Liquidity, Value, Rank |

Fundamentals are point-in-time — a quarter with period-end 2024-03-31
only becomes visible to a backtest on 2024-05-15 (`period_end + 45 d`)
to avoid look-ahead bias. This is verified in
`test_graph_strategy.py::TestFundamentalIndicators`.

---

## 4. Built-in strategy templates as validation fixtures

The app ships **25 ready-to-run templates**
([`frontend/src/lib/strategies/templates.ts`](frontend/src/lib/strategies/templates.ts)).
Ten of them — chosen to span every node family — double as integration
tests in [`backend/tests/test_template_integration.py`](backend/tests/test_template_integration.py).
Each test asserts that the template:

1. Loads without raising.
2. Runs the engine end-to-end on synthetic OHLC.
3. Emits at least one `AddSignal` under the synthetic conditions it was
   designed to trigger on (e.g. the MACD cross template is tested on a
   price series engineered to produce a cross).

Templates covered: DCA, SMA cross, RSI mean-reversion, And combinator,
StopLoss risk exit, PE value screen, Dividend screen, EPS growth cross,
Momentum universe, Value universe.

---

## 5. End-to-end numeric consistency

The same equity curve appears in three places — they must agree:

1. `RunMetrics.total_return` / `final_nav` (scalar, computed by the engine)
2. `EquityPoint` rows per bar (persisted each simulated step)
3. Frontend `EquityCurveChart` (re-computes total return from the last point)

`test_backtests.py` asserts `EquityPoint[-1].equity == RunMetrics.final_nav`
after every backtest. The benchmark line on the equity chart is rebased
to the initial NAV so it visually cohabits with the strategy curve
(fix in commit `5dd53c2`).

---

## 6. Performance metrics

Risk/return metrics are pure functions in
[`backend/background/tasks/_perf_metrics.py`](backend/background/tasks/_perf_metrics.py)
so they are tested independently of any engine state. `test_perf_metrics.py`
covers the boundary cases:

- All-zero returns → Sharpe = 0, not NaN
- Single return point → Sharpe = 0, not unbounded
- All-negative returns → Sortino defined, Sharpe negative
- Flat equity → max drawdown = 0
- Calmar with zero max-DD → None (not ∞)

---

## 7. Data-pipeline robustness

Two fetchers (yfinance primary, FMP fallback) sit behind a shared
dispatcher ([`ohlc_dispatch.py`](backend/background/tasks/ohlc_dispatch.py)).
When a backtest requests a date window not fully covered by `ohlc_bars`,
the Celery task triggers a gap-fill refresh before running. This path is
tested by `test_auto_refresh.py`.

Known data-source trade-off: yfinance gives only ~5 recent quarters of
fundamentals. FMP gives 30+ years but is rate-limited to ~250 calls/day
on the free tier. The dispatcher routes based on both freshness and
depth requirements (see
[`backend/tests/test_fundamentals_refresh_fmp.py`](backend/tests/test_fundamentals_refresh_fmp.py)).

---

## 8. Divide-by-zero and None propagation

Every numeric node can return `None` when inputs are missing (e.g. a
company with no fundamentals, a window shorter than an SMA period).
`None` propagates through math and condition nodes — a comparison
against `None` is treated as false, so a strategy never trades on
partial data.

Specifically tested:

- `TestMathNodes::test_divide_by_zero_returns_none` — `|b| < 1e-12` → None
- `TestMathNodes::test_math_none_propagates` — a single None kills the whole downstream branch
- `TestFundamentalIndicators::test_pe_with_negative_eps_returns_none` — no silent negative PE

---

## 9. What this system does not do

Honest scope boundaries — listed so the examiner doesn't expect them:

- **Intraday data.** The engine supports arbitrary timeframes in principle,
  but only daily OHLC is ingested. Tick data / order-book simulation is
  out of scope for an FYP.
- **Live trading.** No broker integration. Simulation only.
- **Short selling in the single-asset path.** Universe runs can go
  long/short via Rank; the single-symbol path is long-flat.
- **Slippage model.** A flat bps figure, not a queue-position model.
- **Strategy optimisation.** `sweep` fans out a grid of parameters and
  reports winner by Sharpe — no Bayesian / CMA-ES / walk-forward.
- **Portfolio-level risk management.** Risk exits are per-position.
  No portfolio VaR, correlation-aware stops, or vol targeting.
- **Survivorship bias correction.** The universe registry is a static
  snapshot; delisted tickers are not re-included.

Each of these would be a natural follow-on project.

---

## 10. How to reproduce

```bash
# Backend tests
cd backend
python -m pytest --ignore=tests/test_e2e.py -q
# → 254 passed in ~13 s

# Frontend type check
cd ../frontend
pnpm check
# → 2 pre-existing +layout.ts moduleResolution warnings, nothing else

# Manual end-to-end smoke test (needs Docker + Celery worker running)
# 1. docker start timescaledb
# 2. cd backend && celery -A background.celery_app worker --loglevel=info
# 3. cd backend && python server.py
# 4. cd frontend && pnpm dev  → open http://localhost:5173
# 5. Log in, pick any template from the builder, click "Run backtest"
```

See [QUICKSTART.md](QUICKSTART.md) for full dev setup.
