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

## Market Data

- [x] `OhlcBar` DB model (TimescaleDB hypertable)
- [x] `GET /market/ohlc` endpoint (symbol, timeframe, date range)
- [x] S&P500 OHLC data in DB (619k rows, 2013–2018 daily)
- [ ] v1 — Refresh market data via yfinance (extend to 2013–today)

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

---

## Backtest API

- [x] `POST /backtests` — enqueue job, return `{ id, status }`
- [x] `GET /backtests/{id}/status` — return job status
- [x] `GET /backtests/{id}/results` — return summary + OHLC series + trades
- [x] `GET /backtests` — list user's backtest history
- [x] Registered in `server.py`
- [ ] v1 — `DELETE /backtests/{id}` — delete a run and its results

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

---

## Engine Integration

- [x] Engine added as git submodule at `trading_engine/`
- [x] Backend renamed `common/` → `app_common/` to avoid namespace collision with engine's `common/`
- [x] Fix `trading_engine/strategies/strategy.py` inconsistent import
- [x] Celery task feeds OHLC bars to engine as `MarketDataEvent`s and stores results
- [x] Graph JSON parsed: `OnBar → Buy` pattern → `DCA(buyframe=1, buy_amount=<amount>)`
- [ ] ⚠️ MVP — Engine PR `Quant-Backtester/trading_engine#1` merged by teammate (fixes JsonMarketDataSource, _realized_pnl, CancelSignal, CloseSignal)
- [ ] v1 — `DBMarketDataSource` fully implemented — **teammate**
- [ ] v1 — Take profit / stop loss configurable per Buy/Sell node in builder UI

---

## v1 — Graph Interpreter (Option B)

**Goal:** Every node in the visual builder executes real logic, not just `OnBar → Buy`.
**Approach:** A `GraphStrategy` class that topologically sorts the graph and evaluates each node per bar.
Replaces the current `_strategy_from_graph` DCA-only fallback in `background/tasks/backtest.py`.

### Step 1 — Topological sort
- [x] Parse graph nodes + edges into a dependency map
- [x] Kahn's algorithm produces stable evaluation order
- [x] Cycle detection — unreachable nodes logged as warning

### Step 2 — Node evaluators
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

## Frontend — History Page (`/app/backtests`)

- [x] List user's backtest runs (date, symbol, status, total return)
- [x] Link to results page per run
- [ ] v1 — Delete run action

---

## Frontend — Other

- [x] Landing page at `/` — hero, feature strip, nav with login/signup buttons
- [x] Auth guard for `/app/*` routes

---

## Tests

- [x] 16 fast integration tests (SQLite, no Docker) — `uv run pytest tests/`
- [x] 3 e2e tests (real DB + Valkey + Celery worker) — `uv run pytest tests/test_e2e.py -m e2e`
- [ ] v1 — Unit tests for `GraphStrategy` evaluators (SMA, EMA, RSI, IfAbove)
- [ ] v1 — Integration test for full graph → backtest → results pipeline

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

---

## Known Bugs / Issues

- [ ] Engine `pyproject.toml` declares `src/` layout but no `src/` dir — `pip install -e .` broken. **Teammate to fix.**
- [ ] Engine PR `Quant-Backtester/trading_engine#1` waiting for review. Contains: JsonMarketDataSource base class, _realized_pnl, CancelSignal, CloseSignal fixes.
- [ ] User router (`backend/api/user/route.py`) is empty — blocked by v1 user profile work.
