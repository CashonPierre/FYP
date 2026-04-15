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
│   │   ├── route.py           ← POST /backtests, GET /backtests,
│   │   │                        GET /backtests/{id}/status, GET /backtests/{id}/results
│   │   ├── schemas.py         ← BacktestCreate, BacktestResults, ResultSummary, etc.
│   │   └── repositories.py    ← DB queries (create_backtest_run, get_run_by_id, etc.)
│   │
│   └── user/                  ← User profile endpoints (empty, not yet implemented)
│
├── background/                ← Celery async task workers
│   ├── celery_app.py          ← Celery app config (broker = Valkey/Redis)
│   └── tasks/
│       └── email.py           ← send_email Celery task (used for email verification)
│                                TODO: add run_backtest task here
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
│       ├── users.py           ← User table (id, username, email, hashed_password, is_verified)
│       ├── ohlc_bars.py       ← OhlcBar hypertable (symbol, timeframe, time, OHLCV)
│       ├── strategies.py      ← Strategy table (user_id, name, graph_json)
│       ├── backtest_runs.py   ← BacktestRun table (status, settings_json, timestamps)
│       ├── run_metrics.py     ← RunMetrics table (return, drawdown, sharpe, etc.)
│       └── trades.py          ← Trade table (run_id, time, side, price, qty)
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
    ├── app/                   ← Main app (auth-guarded, needs JWT)
    │   ├── +layout.svelte     ← App shell layout with nav
    │   ├── +page.svelte       ← /app → redirects to /app/backtests/new
    │   │
    │   └── backtests/
    │       ├── +page.svelte           ← /app/backtests — run history (placeholder)
    │       ├── new/
    │       │   └── +page.svelte       ← /app/backtests/new — MAIN BUILDER UI
    │       │                            Drag-drop canvas, palette, inspector, mock run
    │       └── [id]/
    │           └── +page.svelte       ← /app/backtests/[id] — results page
    │                                    KPIs, candlestick chart, equity curve (mock data)
    │
    └── backtest/              ← Old backtest routes (pre-app scaffold, mostly unused)
        ├── input/             ← Old simple form input (superseded by /app/backtests/new)
        └── results/           ← Old results page (superseded by /app/backtests/[id])
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

**For backtest execution (future):**
```
POST /backtests
  │
  ▼
Celery task (background/tasks/backtest.py) — TODO
  │
  ▼
trading_engine (run loop)
  │  reads market data from ohlc_bars
  ▼
Results stored in run_metrics + trades tables
  │
  ▼
GET /backtests/{id}/results → Frontend
```
