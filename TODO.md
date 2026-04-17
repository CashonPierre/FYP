# Project To-Do Checklist

Track what's done and what's left. Update this file as you go.

---

## MVP Status

**MVP = DCA strategy working end-to-end: build → run → results.**
Everything below marked `[x]` is shipped. Remaining MVP items are flagged ⚠️ MVP.

---

## Auth

- [x] `POST /auth/register` — register new user
- [x] `POST /auth/login` — login, returns JWT
- [x] `GET /auth/me` — get current user
- [x] `GET /auth/verify-email` — verify email with token
- [x] `POST /auth/send-again` — resend verification email
- [x] Frontend `/login` wired to backend
- [x] Frontend `/signup` wired to backend
- [x] Signup → login redirect with "verify email" reminder
- [x] Auth guard for `/app/*` routes (redirect to `/login` if no token)
- [x] **Email delivery via Resend** — uses Resend SDK when `RESEND_API_KEY` is set; console-log fallback in dev. Set `RESEND_API_KEY` + `RESEND_FROM_EMAIL` in `.env` for production.
- [x] **Forget password** — `POST /auth/forgot-password` + `POST /auth/reset-password` + frontend `/reset-password` page.

---

## Market Data — OHLCV Pipeline

- [x] `OhlcBar` DB model (TimescaleDB hypertable)
- [x] `GET /market/ohlc` endpoint (symbol, timeframe, date range)
- [x] S&P500 OHLC data in DB (619k rows, 2013–2018 daily)
- [x] v1 — `scripts/refresh_ohlc.py` — fetch via yfinance for a symbol list or universe name, upsert into `ohlc_bars` incrementally
- [x] v1 — `POST /market/refresh` — authenticated endpoint to trigger on-demand refresh (enqueues Celery tasks, returns 202)
- [x] v1 — Celery Beat scheduled task — daily auto-refresh at 06:00 UTC for all tracked symbols + all universe symbols
- [ ] v1 — On backtest run: if symbol missing or data stale (> 1 day old), auto-fetch before task runs
- [x] v1 — `GET /market/universes` — returns all universe definitions with symbol lists

---

## Market Data — Fundamental Pipeline

> Fundamental data is quarterly/annual (P/E, EPS, ROE, etc.). Required for fundamental strategy nodes.
> Source: yfinance `ticker.financials`, `ticker.balance_sheet`, `ticker.quarterly_earnings`.
> Point-in-time approximation: use period end date + 45 days (typical SEC 10-Q filing window) to avoid look-ahead bias.

- [ ] v2 — `FundamentalSnapshot` DB model — one row per symbol per reporting period
  - Fields: `symbol`, `period_end`, `available_from` (= period_end + 45d), `pe_ratio`, `pb_ratio`, `eps`, `eps_growth_yoy`, `revenue_growth_yoy`, `dividend_yield`, `roe`, `debt_equity`, `profit_margin`, `peg_ratio`
- [ ] v2 — Alembic migration for `fundamental_snapshots` table
- [ ] v2 — `scripts/refresh_fundamentals.py` — fetch via yfinance for symbol list, upsert by (symbol, period_end)
- [ ] v2 — `GET /market/fundamentals` endpoint (symbol, date range) — returns snapshots available up to requested date
- [ ] v2 — Celery Beat: quarterly refresh of fundamental data

---

## Cloud Infrastructure

- [ ] v1 — Migrate DB to **Timescale Cloud** (managed TimescaleDB). Zero schema changes — swap `DATABASE_URL` env var only. Free trial; required for cloud server deployment.
- [ ] v1 — Deploy backend to cloud server (Railway / Fly.io / VPS). Update `FRONTEND_URL`, `DATABASE_URL`, `RESEND_API_KEY` in env.
- [ ] v1 — Docker Compose file for full local stack (one `docker compose up`)

---

## Database / Migrations

- [x] SQLAlchemy + PostgreSQL configured
- [x] Alembic scaffold set up
- [x] `Strategy` model
- [x] `BacktestRun` model
- [x] `RunMetrics` model
- [x] `Trade` model
- [x] Write + apply Alembic migration for all models (baseline + new tables migration; fresh setup: `uv run python -m alembic upgrade head`)
- [ ] v1 — Add `EquityCurve` hypertable (one row per bar per run; needed for equity curve chart)
- [ ] v1 — Add `BacktestBatch` model — groups multiple `BacktestRun`s for multi-asset runs
  - Fields: `id`, `user_id`, `created_at`, `graph_json`, `settings_json`, `universe` (nullable)

---

## Backtest API

- [x] `POST /backtests` — enqueue job, return `{ id, status }`
- [x] `GET /backtests/{id}/status` — return job status
- [x] `GET /backtests/{id}/results` — return summary + OHLC series + trades
- [x] `GET /backtests` — list user's backtest history
- [x] Registered in `server.py`
- [ ] v1 — `DELETE /backtests/{id}` — delete a run and its results
- [ ] v1 — Update `POST /backtests` to accept `symbols: list[str]` or `universe: str` → creates `BacktestBatch` + fans out to N parallel Celery tasks
- [ ] v1 — `GET /backtests/batch/{batch_id}` — aggregate results table (symbol / return / drawdown / sharpe / trades), sorted by return
- [ ] v1 — `GET /backtests/batch` — list user's batch runs

---

## Strategy API

- [x] `POST /strategies` — save a strategy graph
- [x] `GET /strategies` — list user's saved strategies
- [x] `GET /strategies/{id}` — get a single strategy
- [x] `PUT /strategies/{id}` — overwrite existing strategy

---

## Celery / Background Tasks

- [x] Valkey (Redis-compatible) broker configured and running in Docker
- [x] Celery worker connects and picks up jobs
- [x] Email send task (`background/tasks/email.py`)
- [x] Backtest execution task — loads OHLC from DB, runs engine, stores RunMetrics + Trade results
- [ ] v1 — Equity curve capture — store per-bar NAV snapshots; requires engine changes (see Engine Integration below)
- [ ] v1 — Batch backtest fan-out task — spawns one `run_backtest` per symbol in parallel

---

## Engine Integration

- [x] Engine added as git submodule at `trading_engine/`
- [x] Backend renamed `common/` → `app_common/` to avoid namespace collision with engine's `common/`
- [x] Fix `trading_engine/strategies/strategy.py` inconsistent import
- [x] Celery task feeds OHLC bars to engine as `MarketDataEvent`s and stores results
- [x] Graph JSON parsed: `OnBar → Buy` pattern → `DCA(buyframe=1, buy_amount=<amount>)`
- [x] Engine PR `Quant-Backtester/trading_engine#1` merged — fixes JsonMarketDataSource, _realized_pnl, CancelSignal, CloseSignal
- [ ] v1 — `DBMarketDataSource` fully implemented — **teammate**
- [ ] v1 — Take profit / stop loss configurable per Buy/Sell node in builder UI

---

## v1 — Graph Interpreter

**Goal:** Every node in the visual builder executes real logic, not just `OnBar → Buy`.
**Approach:** A `GraphStrategy` class that topologically sorts the graph and evaluates each node per bar.
Replaces the current `_strategy_from_graph` DCA-only fallback in `background/tasks/backtest.py`.

### Step 1 — Topological sort
- [x] Parse graph nodes + edges into a dependency map
- [x] Kahn's algorithm produces stable evaluation order
- [x] Cycle detection — unreachable nodes logged as warning

### Step 2 — Node evaluators (current)
- [x] `OnBar` — emits `MarketDataPayload`
- [x] `Data` — outputs close price from bar
- [x] `SMA(period)` — rolling mean; suppressed during warm-up
- [x] `EMA(period)` — seeded with SMA, then exponential update; suppressed during warm-up
- [x] `RSI(period)` — Wilder RSI 0–100; suppressed during warm-up
- [x] `IfAbove(A, B)` — routes `true`/`false` based on A > B; coerces payload inputs to float
- [x] `Buy(amount)` — emits `AddSignal` when triggered
- [x] `Sell` — emits `CloseSignal` when triggered

### Step 3 — State management
- [x] Per-node rolling price buffer (deque)
- [x] EMA value persists across bars
- [x] `reset()` clears all state between runs

### Step 4 — Multi-input nodes
- [x] `IfAbove` resolves `a`/`b` inputs by `targetHandle` on edges
- [x] `_to_float` coerces MarketDataPayload inputs to price float

### Step 5 — Wire into backtest task
- [x] `_strategy_from_graph` now returns `GraphStrategy` (falls back to DCA for empty graph)

### Step 6 — Frontend validation
- [x] `IfAbove` `a`/`b` ports: already required by node spec — existing loop catches missing connections
- [x] RSI period validation added (was only SMA/EMA before)
- [x] Warm-up period estimate shown below date inputs when indicator nodes are present

### Step 7 — Tests
- [x] 46 unit tests: topo-sort, SMA/EMA/RSI evaluators, IfAbove, Buy, Sell, position guard, reset, fallback
- [ ] Integration test: full run with SMA crossover graph produces trades at correct bars

---

## v1 — Node Library Expansion (Technical Indicators)

**Goal:** Cover all common technical analysis strategies traders use in practice.

### Critical — unlocks most standard strategies
- [ ] `IfBelow(A, B)` — routes `true`/`false` based on A < B (mirror of IfAbove). Required for RSI oversold, price below BB lower band, etc.
- [ ] `IfCrossAbove(A, B)` — fires `true` on the bar where A crosses above B (was below previous bar). Required for all MA crossover and MACD crossover strategies.
- [ ] `IfCrossBelow(A, B)` — fires `true` on the bar where A crosses below B. Required for death cross, overbought exits.
- [ ] `Constant(value)` — outputs a user-defined fixed number. Required for comparisons like RSI < 30, price > 200.

### High — most commonly used indicators
- [ ] `MACD(fast, slow, signal)` — outputs `macd` line, `signal` line, `histogram`. Most popular trend-following indicator.
- [ ] `BollingerBands(period, std)` — outputs `upper`, `middle`, `lower` bands. Used for mean reversion and breakout strategies.
- [ ] `ATR(period)` — Average True Range; outputs volatility scalar. Used for position sizing and stop-loss placement.
- [ ] `Volume` — outputs raw bar volume. Required for volume confirmation strategies.

### Medium — broader coverage
- [ ] `Stochastic(k_period, d_period)` — outputs `%K` and `%D`. Used for overbought/oversold in trending markets.
- [ ] `VWAP` — Volume Weighted Average Price; outputs intraday mean price. Common institutional benchmark.
- [ ] `VWAP(period)` — Rolling Volume-Weighted Average Price over N daily bars. Institutional benchmark for entry/exit levels.
- [ ] `MFI(period)` — Money Flow Index; combines price + volume into 0–100 oscillator. Volume-aware overbought/oversold.
- [ ] `ADX(period)` — Average Directional Index; outputs trend strength 0–100. Used to filter ranging vs trending markets.
- [ ] `OBV` — On-Balance Volume; cumulative volume flow. Used to confirm price trend with volume.
- [ ] `CCI(period)` — Commodity Channel Index; outputs oscillator. Used for overbought/oversold and divergence.
- [ ] `WilliamsR(period)` — Williams %R; outputs −100–0 oscillator. Similar use to Stochastic.

### Logic / utility nodes
- [ ] `And(A, B)` — outputs `true` only if both A and B are true. Required to combine multiple conditions.
- [ ] `Or(A, B)` — outputs `true` if either A or B is true.
- [ ] `Not(A)` — inverts a boolean signal.

### For each new node
- [ ] Backend: add evaluator branch in `GraphStrategy.on_event`
- [ ] Backend: add unit tests in `test_graph_strategy.py`
- [ ] Frontend: add node spec to palette (type, ports, params, inspector fields)
- [ ] Frontend: add warm-up period to estimate where applicable (MACD = slow period, BB = period, ATR = period)

**Strategies unlocked by this expansion:**
| Strategy | Nodes required |
|---|---|
| MA crossover (golden/death cross) | SMA × 2 + IfCrossAbove/Below → Buy/Sell |
| RSI oversold/overbought | RSI + Constant(30) + IfBelow → Buy; Constant(70) + IfAbove → Sell |
| MACD crossover | MACD + IfCrossAbove(macd, signal) → Buy |
| Bollinger Band mean reversion | BollingerBands + IfBelow(price, lower) → Buy; IfAbove(price, upper) → Sell |
| Bollinger Band breakout | BollingerBands + IfCrossAbove(price, upper) → Buy |
| RSI + MA trend filter | SMA + IfAbove(price, SMA) + RSI + IfBelow(RSI, 50) + And → Buy |
| Volume surge breakout | Volume + SMA(volume) + IfCrossAbove(vol, vol_sma) + IfAbove(price, SMA) + And → Buy |
| Stochastic crossover | Stochastic + IfCrossAbove(%K, %D) + IfBelow(%K, Constant(20)) + And → Buy |

---

## v2 — Fundamental Strategy Nodes

> Requires `FundamentalSnapshot` DB table and fundamental data pipeline (see Market Data above).
> Data is forward-filled between quarterly reporting dates using point-in-time available_from date to avoid look-ahead bias.

- [ ] `PE` — outputs trailing P/E ratio for the symbol on each bar
- [ ] `PB` — outputs price-to-book ratio
- [ ] `EPS` — outputs trailing twelve-month EPS
- [ ] `EPSGrowth` — outputs YoY EPS growth rate (%)
- [ ] `RevenueGrowth` — outputs YoY revenue growth rate (%)
- [ ] `DividendYield` — outputs annual dividend yield (%)
- [ ] `ROE` — outputs return on equity (%)
- [ ] `DebtEquity` — outputs debt-to-equity ratio
- [ ] `ProfitMargin` — outputs net profit margin (%)
- [ ] `PEG` — outputs PEG ratio (P/E ÷ EPS growth); < 1 considered undervalued

**Fundamental strategies enabled:**
| Strategy | Nodes required |
|---|---|
| Value screen — low P/E + high dividend | PE + Constant(15) + IfBelow + DividendYield + Constant(3) + IfAbove + And → Buy |
| Growth screen — high EPS growth | EPSGrowth + Constant(20) + IfAbove → Buy |
| Quality filter — high ROE + low debt | ROE + Constant(15) + IfAbove + DebtEquity + Constant(1) + IfBelow + And → Buy |
| PEG undervalued | PEG + Constant(1) + IfBelow → Buy |
| Dogs of the Dow | DividendYield (rank by universe — requires batch mode) |

---

## v1 — Multi-Asset Backtest

- [ ] `BacktestBatch` DB model + Alembic migration
- [ ] Update `POST /backtests` to accept `symbols: list[str]` or `universe: str`
- [ ] Batch fan-out: create one `BacktestRun` per symbol + spawn N parallel Celery tasks
- [ ] `GET /backtests/batch/{batch_id}` — aggregate results (symbol / return / drawdown / sharpe / trades)
- [ ] `GET /backtests/batch` — list user's batch runs
- [ ] Universe registry — static JSON mapping universe keys to symbol lists
  - `mag7`: AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA
  - `dow30`: Dow Jones 30 components
  - `nasdaq100`: NASDAQ-100 components
  - `sp500_top50`: Top 50 S&P 500 by market cap
  - `crypto`: BTC-USD, ETH-USD, SOL-USD, BNB-USD
- [ ] `GET /market/universes` — return available universes + symbol lists
- [ ] Frontend: multi-symbol picker + universe dropdown in run settings
- [ ] Frontend: batch results page — comparison table + best/worst performer highlight

---

## v1 — pandas_ta Precompute Refactor

> Current: GraphStrategy computes SMA/EMA/RSI per-bar via rolling buffers (works but doesn't scale to 130+ nodes).
> Target: precompute all indicator series upfront as a DataFrame before the backtest loop; on_event becomes O(1) dict lookup.
> Benefit: vectorized, no warm-up state management, all pandas_ta indicators available with one line each.

- [ ] Pass full OHLCV DataFrame into `GraphStrategy.__init__`
- [ ] On init: scan graph nodes, call `df.ta.<indicator>()` for each used indicator
- [ ] Store results in `self._precomputed: dict[node_id, pd.Series]`
- [ ] `on_event`: index into series by bar timestamp instead of computing per-bar
- [ ] Remove `_price_buffers`, `_ema_values`, `_rsi_state` (replaced by precomputed series)
- [ ] Update `backtest.py` Celery task to build DataFrame before constructing `GraphStrategy`
- [ ] Update all unit tests to pass DataFrame

---

## v1 — Equity Curve

- [ ] Engine emits per-bar NAV snapshot (needs teammate to add portfolio snapshot hook in `engine.py`)
- [ ] Alembic migration: `equity_curve` hypertable (`run_id`, `time`, `nav`)
- [ ] Celery task stores per-bar NAV after `engine.run()`
- [ ] `GET /backtests/{id}/results` returns `equity` series (currently always `[]`)
- [ ] Frontend equity curve chart renders real data

---

## v1 — User Profile

- [ ] `GET /users/me` — return profile (name, email, join date)
- [ ] `PUT /users/me` — update display name
- [ ] Frontend profile page / settings drawer
- [ ] Implement `backend/api/user/route.py` (currently empty stub)

---

## Frontend — Builder (`/app/backtests/new`)

- [x] Drag-drop canvas (nodes, edges, pan/zoom)
- [x] Block palette + inspector
- [x] Strategy validation + "Run" gating
- [x] Export/Import strategy JSON
- [x] Save/Load strategy (backend API — POST creates, PUT overwrites)
- [x] Save/Load draft (localStorage)
- [x] Run settings (symbol, date range)
- [x] "Run" button calls real `POST /backtests` with JWT token
- [x] Redirects to `/app/backtests/<real-uuid>` on submit
- [x] Buy node `amount` parameter in inspector
- [ ] v1 — Multi-symbol picker: add/remove symbols, or select a universe
- [ ] v1 — New nodes in palette: IfBelow, IfCrossAbove, IfCrossBelow, Constant, MACD, BollingerBands, ATR, Volume, Stochastic, ADX, OBV, And, Or, Not
- [ ] v1 — Inspector fields for new nodes (MACD fast/slow/signal params, BB period/std, etc.)
- [ ] v1 — Warm-up estimate updated for new indicator nodes

---

## Frontend — Results Page (`/app/backtests/[id]`)

- [x] KPI summary cards (P/L, return, drawdown, sharpe, trades, win rate)
- [x] Candlestick chart with buy/sell markers
- [x] Equity curve chart (renders when data is present)
- [x] Polls `GET /{id}/status` every 2s until completed/failed
- [x] Fetches and renders real metrics + OHLC + trades from API
- [x] Failed state — shows error card with message from API
- [x] Trades table (sortable by date/side/price/qty)
- [ ] v1 — Equity curve populated (blocked by engine equity snapshot work above)

---

## Frontend — Batch Results Page (`/app/backtests/batch/[id]`)

- [ ] v1 — Aggregate KPI table: symbol / return / max drawdown / sharpe / total trades, sortable
- [ ] v1 — Best / worst performer highlight cards
- [ ] v1 — Link to individual run results per symbol
- [ ] v1 — Equity curves overlay chart (one line per symbol)

---

## Frontend — History Page (`/app/backtests`)

- [x] List user's backtest runs (date, symbol, status, total return)
- [x] Link to results page per run
- [ ] v1 — Show batch runs grouped + individual runs
- [ ] v1 — Delete run action

---

## Frontend — Other

- [x] Landing page at `/` — hero, feature strip, nav with login/signup buttons
- [x] Auth guard for `/app/*` routes

---

## Tests

- [x] 16 fast integration tests (SQLite, no Docker) — `uv run pytest tests/`
- [x] 3 e2e tests (real DB + Valkey + Celery worker) — `uv run pytest tests/test_e2e.py -m e2e`
- [x] 46 unit tests for GraphStrategy (topo-sort, SMA/EMA/RSI, IfAbove, Buy, Sell, position guard, reset, fallback)
- [ ] v1 — Unit tests for new node evaluators (IfBelow, IfCrossAbove, IfCrossBelow, Constant, MACD, BollingerBands, ATR, Stochastic)
- [ ] v1 — Integration test: full SMA crossover graph → backtest → trades at correct bars
- [ ] v1 — Integration test: multi-asset batch run → N results with correct metrics
- [ ] v2 — Unit tests for fundamental node evaluators

---

## DevOps / Setup

- [x] TimescaleDB in Docker (`docker start timescaledb`)
- [x] Valkey in Docker (`docker start valkey`)
- [x] `dev.sh` — single command starts full stack (Docker + backend + Celery + frontend)
- [x] `QUICKSTART.md` — step-by-step local dev guide
- [x] `CLAUDE.md` — project context for AI assistant
- [x] `ARCHITECTURE.md` — file/folder tree with descriptions
- [x] `.vscode/settings.json` — VS Code Python interpreter set to backend `.venv`
- [x] Alembic migration applied — `uv run python -m alembic upgrade head` creates full schema on fresh DB
- [ ] v1 — Docker Compose file for full local stack (one `docker compose up`)
- [ ] v1 — Cloud deployment guide (Timescale Cloud DB + backend hosting)

---

## Known Bugs / Issues

- [ ] Engine `pyproject.toml` declares `src/` layout but no `src/` dir — `pip install -e .` broken. **Teammate to fix.**
- [ ] User router (`backend/api/user/route.py`) is empty — blocked by v1 user profile work.
