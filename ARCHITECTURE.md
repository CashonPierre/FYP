# Project Architecture

A reference for understanding what every file and folder does.

---

## Top-Level Structure

```
FYP/
├── backend/          ← Python API server
├── frontend/         ← SvelteKit web app
├── trading_engine/   ← Backtesting engine (git submodule, teammate's work)
├── CLAUDE.md         ← Auto-loaded context for Claude Code
├── QUICKSTART.md     ← How to run the project locally
├── TODO.md           ← MVP checklist
├── BACKEND_PLAN.md   ← Detailed backend design doc
├── UI_PLAN.md        ← Detailed frontend design doc
├── EVALUATION.md     ← How the system is validated: tests, benchmarks, limitations
├── DEPLOYMENT.md     ← Production topology (Vercel + Railway + Timescale Cloud)
└── CHANGES.md        ← Non-obvious change log
```

---

## Backend

```
backend/
├── server.py                  ← Entry point. Creates the FastAPI app, registers
│                                all routers, middleware, and exception handlers.
│                                Run with: uv run python server.py
│
├── api/                       ← All HTTP route handlers, grouped by feature
│   ├── auth/                  ← Authentication (register, login, verify email)
│   │   ├── route.py           ← Endpoint handlers (POST /auth/register, POST /auth/login, etc.)
│   │   ├── schemas.py         ← Request/response shapes (UserCreate, AccessToken, etc.)
│   │   ├── repositories.py    ← DB queries for users (get_user_by_email, etc.)
│   │   ├── dependencies.py    ← get_current_user() — JWT auth dependency for protected routes
│   │   ├── security.py        ← Password hashing, JWT generation helpers
│   │   ├── service.py         ← Business logic (create_jwt_token, register_user, etc.)
│   │   └── types.py           ← Auth-specific type aliases
│   │
│   ├── market/                ← Market data endpoints
│   │   ├── route.py           ← GET /market/ohlc — fetch OHLC bars from DB
│   │   └── schemas.py         ← OhlcBar response schema
│   │
│   ├── backtests/             ← Backtest job endpoints
│   │   ├── route.py           ← POST /backtests (single), POST /backtests/batch (fan-out),
│   │   │                        POST /backtests/sweep (parameter grid), GET list,
│   │   │                        GET /backtests/{id}/status, GET /backtests/{id}/results,
│   │   │                        POST /backtests/compare
│   │   ├── schemas.py         ← BacktestCreate, BacktestResults, BatchCreate, SweepCreate
│   │   └── repositories.py    ← DB queries (create_backtest_run, get_run_by_id, etc.)
│   │
│   ├── strategies/            ← Saved strategy graphs (persistent templates)
│   │   ├── route.py           ← CRUD (POST / GET / PATCH / DELETE /strategies)
│   │   └── schemas.py         ← StrategyCreate, StrategyOut
│   │
│   └── user/                  ← User datasets (BYO OHLC upload) + profile
│       └── datasets.py        ← POST /user/datasets (CSV), GET /user/datasets
│
├── background/                ← Celery async task workers
│   ├── celery_app.py          ← Celery app config (broker = Valkey/Redis)
│   └── tasks/
│       ├── backtest.py                 ← run_backtest — single strategy, full engine flow
│       ├── graph_strategy.py           ← GraphStrategy — topological eval of a node graph;
│       │                                 adapts a user graph into the engine's Strategy ABC
│       ├── cross_sectional.py          ← Momentum / Value factor rankings for universe runs
│       ├── ohlc_dispatch.py            ← Ad-hoc refresh router (picks yfinance or FMP)
│       ├── market_refresh.py           ← yfinance OHLC fetcher (primary, free)
│       ├── market_refresh_fmp.py       ← Financial Modeling Prep OHLC fetcher (fallback)
│       ├── fundamentals_refresh.py     ← yfinance fundamentals (~5 recent quarters)
│       ├── fundamentals_refresh_fmp.py ← FMP fundamentals (30+ yr history)
│       ├── _perf_metrics.py            ← Sharpe/Sortino/Calmar/max-DD/vol pure functions
│       └── email.py                    ← verification emails
│
├── common/                    ← Shared utilities used across the app
│   ├── enums/                 ← Enum definitions (PayloadEnum, RequestEnum, etc.)
│   ├── exceptions.py          ← Custom app exceptions (NotFoundError, ConflictError, etc.)
│   ├── exception_handlers.py  ← FastAPI exception → HTTP response mapping
│   └── mixins.py              ← (if present) shared base class helpers
│
├── configs/                   ← App configuration
│   ├── config.py              ← Settings class (DB URL, JWT secret, CORS origins, etc.)
│   │                            All values are env-driven with sensible defaults for local dev
│   ├── config_loader.py       ← Instantiates Settings as a singleton `settings` object
│   └── logging_config.py      ← Structured JSON logging setup
│
├── database/                  ← Database layer
│   ├── make_db.py             ← SQLAlchemy engine + session factory + Base class
│   │                            get_session() is the FastAPI dependency for DB access
│   └── models/                ← SQLAlchemy ORM table definitions
│       ├── users.py                   ← User (id, username, email, hashed_password, is_verified)
│       ├── ohlc_bars.py               ← OhlcBar hypertable (symbol, timeframe, time, OHLCV)
│       ├── fundamental_snapshots.py   ← FundamentalSnapshot (point-in-time EPS/ROE/etc.)
│       ├── user_datasets.py           ← UserDataset (BYOD uploaded OHLC namespace)
│       ├── strategies.py              ← Strategy (user_id, name, graph_json)
│       ├── backtest_runs.py           ← BacktestRun (status, settings_json, batch_id, timestamps)
│       ├── backtest_batches.py        ← BacktestBatch (fan-out/sweep parent record)
│       ├── run_metrics.py             ← RunMetrics (return, DD, sharpe, sortino, calmar, …)
│       ├── equity_points.py           ← EquityPoint (per-bar NAV for the equity curve)
│       └── trades.py                  ← Trade (run_id, time, side, price, qty)
│
├── middlewares/               ← FastAPI middleware
│   ├── logging_middleware.py  ← Logs every request/response
│   └── rate_limiter.py        ← Rate limiting (if active)
│
├── migrations/                ← Alembic database migrations
│   ├── env.py                 ← Alembic config (points at our models + DB URL)
│   └── versions/              ← Migration files (run in order)
│       ├── e5e0188f566c_...   ← Baseline (marks existing users + ohlc_bars tables)
│       └── 29535fedaf94_...   ← Adds strategies, backtest_runs, run_metrics, trades
│
└── scripts/                   ← One-off utility scripts (not part of the server)
    ├── ingest_ohlc_csv.py     ← Bulk-loads S&P 500 CSV into ohlc_bars via COPY
    ├── timescale_init.sql     ← Creates ohlc_bars hypertable (first-time DB setup)
    └── db_operation.py        ← (misc DB helpers)
```

---

## Frontend

```
frontend/src/
├── app.html                   ← Root HTML shell (injected by SvelteKit)
├── i18n.ts                    ← Locale initialisation (loads en/zh JSON)
│
├── lib/                       ← Shared code (reusable across routes)
│   ├── components/
│   │   ├── app/
│   │   │   └── AppShell.svelte        ← Top nav + layout wrapper for /app/* pages
│   │   ├── charts/
│   │   │   ├── CandlestickChart.svelte ← OHLC candlestick chart (results page)
│   │   │   └── EquityCurveChart.svelte ← Equity over time line chart (results page)
│   │   └── ui/                        ← shadcn-svelte UI primitives
│   │       ├── button/, card/, input/ ← Generic reusable UI components
│   │       ├── form/                  ← Form field wrappers with validation
│   │       └── alert/, checkbox/, ... ← Other UI components
│   │
│   ├── locales/
│   │   ├── en.json            ← English UI strings
│   │   └── zh.json            ← Chinese UI strings
│   │
│   ├── schemas/
│   │   ├── LoginSchema.ts     ← Zod validation schema for login form
│   │   └── SignupSchema.ts    ← Zod validation schema for signup form
│   │
│   ├── types/
│   │   └── auth.ts            ← TypeScript types for auth (LoginFormData, etc.)
│   │
│   └── utils/
│       └── auth.ts            ← Auth helpers (read/write JWT from localStorage)
│
└── routes/                    ← SvelteKit file-based routing
    ├── +layout.svelte         ← Root layout (initialises i18n, wraps all pages)
    ├── +page.svelte           ← / landing page (placeholder, needs replacing)
    ├── layout.css             ← Global CSS variables (shadcn design tokens)
    │
    ├── login/
    │   ├── +page.svelte       ← Login form UI
    │   └── +page.server.ts    ← Server action: calls POST /auth/login, stores token
    │
    ├── signup/
    │   ├── +page.svelte       ← Signup page shell
    │   ├── SignupForm.svelte   ← Signup form component
    │   └── +page.server.ts    ← Server action: calls POST /auth/register
    │
    ├── forget-password/
    │   └── +page.svelte       ← Forgot password UI (mocked, no backend yet)
    │
    └── app/                   ← Main app (auth-guarded, needs JWT)
        ├── +layout.svelte     ← App shell layout with nav
        ├── +page.svelte       ← /app → redirects to /app/backtests/new
        │
        ├── backtests/
        │   ├── +page.svelte           ← History list (skeleton loader + empty state)
        │   ├── new/                   ← MAIN BUILDER: drag-drop canvas + palette + inspector
        │   │   └── +page.svelte       ← Wired to POST /backtests, subscribes to /status
        │   ├── [id]/
        │   │   └── +page.svelte       ← Results — KPIs, candles, equity curve, trades table
        │   ├── batch/                 ← Fan-out one strategy across a symbol universe
        │   ├── compare/               ← Side-by-side comparison of selected runs
        │   └── sweep/                 ← Parameter grid sweep UI
        │
        ├── strategies/                ← Saved strategy graphs (CRUD, search, open-in-builder)
        ├── datasets/                  ← User-uploaded OHLC CSV datasets
        ├── settings/                  ← Profile + theme
        └── docs/                      ← In-app node reference ("What does each node do?")
```

---

## Trading Engine (Submodule)

```
trading_engine/
├── main.py                    ← CLI entry point (csv/db/json mode, initial capital)
├── core/
│   ├── engine.py              ← Main event loop: pop event → fill orders → run strategies
│   ├── order_manager.py       ← Handles AddSignal → creates orders, fills MARKET orders
│   ├── position_manager.py    ← Tracks positions per symbol, calculates P&L
│   ├── portfolio.py           ← Trade analytics: win rate, Sharpe, max drawdown
│   ├── strategy_handler.py    ← Registry that runs all strategies on each event
│   ├── clock.py               ← Simulated time (advances per event, not wall clock)
│   └── event_queue.py         ← Priority queue ordered by timestamp
│
├── events/
│   ├── event.py               ← MarketDataEvent, OrderFillEvent, TimerEvent
│   └── payloads/
│       ├── market_payload.py  ← MarketDataPayload (timestamp, symbol, OHLCV)
│       ├── order_payload.py   ← OrderPayload, OrderFillPayload
│       └── timer_payload.py   ← TimerPayload (not yet used)
│
├── strategies/
│   ├── strategy.py            ← Abstract base: on_event() → Signal, get_hash_key()
│   ├── signal.py              ← NullSignal, AddSignal, CancelSignal, ModifySignal, CloseSignal
│   ├── dca.py                 ← Dollar-Cost Averaging: buy fixed amount every N bars
│   └── EDCA.py                ← Enhanced DCA: adjusts qty based on recent performance
│
├── market_data/
│   ├── source.py              ← CSVMarketDataSource ✅, DBMarketDataSource ❌ (stub)
│   └── replayer.py            ← Reads source in chunks, pushes MarketDataEvents to engine
│
└── common/
    ├── types.py               ← Type aliases (Cash, Symbol, Price, etc.)
    └── enums.py               ← Side (BUY/SELL), OrderType (MARKET/LIMIT), etc.
```

---

## How a Request Flows (End to End)

```
Browser
  │
  ▼
Frontend (SvelteKit)
  │  +page.server.ts or fetch()
  ▼
Backend (FastAPI) — server.py
  │  router → route.py
  │  dependency → get_current_user() [JWT check]
  │  dependency → get_session() [DB connection]
  ▼
repositories.py — SQL queries via SQLAlchemy
  │
  ▼
PostgreSQL + TimescaleDB (Docker)
```

**For backtest execution (live path):**
```
POST /backtests {symbol, timeframe, dates, capital, graph_json}
  │  FastAPI route creates BacktestRun row (status=queued), returns id
  ▼
Celery task run_backtest (background/tasks/backtest.py)
  │  status → running
  │  loads OHLC via DBMarketDataSource (auto-fetches from yfinance/FMP
  │  if the requested window isn't covered in ohlc_bars)
  │  wraps the user's graph_json in GraphStrategy (graph_strategy.py)
  │     └─ topological sort of nodes
  │     └─ per-bar: OnBar → indicators/fundamentals → math → conditions → orders
  ▼
trading_engine Engine loop
  │  MarketDataEvent → StrategyHandler → Signal → OrderManager → FillEvent
  │  PositionManager tracks holdings, NAV mark-to-market each bar
  ▼
Persistence
  │  RunMetrics: total_return, Sharpe, Sortino, Calmar, max_DD, win_rate …
  │  EquityPoint: NAV per bar (drives the equity curve chart)
  │  Trade: every fill
  │  BacktestRun: status=completed
  ▼
GET /backtests/{id}/results → Frontend renders KPIs + charts + trades
```

**For batch / sweep runs** the route creates a `BacktestBatch` parent row and fans
out N `BacktestRun` children (one per symbol or parameter combo) into Celery in
parallel. The compare page joins their metrics via `POST /backtests/compare`.
