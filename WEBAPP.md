# Web Application — Frontend & Backend

The user-facing layer of the project: a SvelteKit web app, a FastAPI service, a
Celery worker, a TimescaleDB database, and the data pipeline that keeps OHLC
and fundamentals fresh. The trading engine itself lives in a separate repo
([`trading_engine/`](trading_engine/README.md)) and is consumed here as a
git submodule.

This document covers everything in this repository (`backend/` and
`frontend/`) — what it does, how the pieces fit together, and how a single
backtest flows from a button click to a rendered equity curve.

---

## Overview

A no-code backtesting platform. Users build trading strategies in a visual
node-graph builder, parameterise the run (symbols, dates, capital, fees,
slippage), and submit. The backend persists the request, dispatches it to a
Celery worker, and the worker drives the deterministic engine end-to-end. The
frontend polls until the run is complete and then renders KPIs, charts, and
trades.

The platform supports four execution modes from a single submission:

| Mode | What it does | Output |
|------|--------------|--------|
| **Single** | One strategy, one symbol | One run + results page |
| **Fan-out** | One strategy, N symbols (independent) | One batch + N runs + combined portfolio view |
| **Universe** | One cross-sectional strategy ranking N symbols every bar | One batch + one universe run |
| **Sweep** | Parameter grid over one strategy | One batch + N runs + comparison table |

Single and fan-out submissions both create a `BacktestBatch` record so polling,
status, and history are uniform regardless of how many symbols are involved.

---

## Features

- **Visual strategy builder** — drag nodes onto a canvas, wire data → indicators → conditions → orders, parameters per node
- **Strategy templates + AI Builder** — preset strategies (DCA, momentum, golden cross, etc.) and an LLM-backed natural-language → graph generator
- **Multi-asset modes** — single symbol, custom symbol list, named universe (S&P 100 / NASDAQ 100 / sector), cross-sectional universe, or BYO uploaded dataset
- **Combined portfolio view** — fan-out batches are pooled into an equal-weight NAV with recomputed Sharpe / max DD / volatility
- **Parameter sweep** — grid over node parameters, results joined into one comparison table
- **Run comparison** — pick any 2+ completed runs, side-by-side metrics + overlaid equity curves
- **Saved strategies** — full-graph CRUD; open any saved strategy back into the builder
- **Performance metrics** — total/annualised return, Sharpe, Sortino, Calmar, max drawdown, volatility, win rate, alpha/beta vs Buy & Hold benchmark
- **Equity + candle charts** — Chart.js-rendered, with trade markers overlaid on price
- **CSV exports** — equity curve and trades downloads from any run
- **Auth + email verification** — JWT, password hashing, Resend transactional email on a custom domain

---

## High-level Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  SvelteKit (Vercel) │ ──► │  FastAPI (Railway)  │ ──► │  TimescaleDB Cloud  │
│  Visual builder UI  │     │  REST + JWT auth    │     │  PostgreSQL + TSDB  │
│  Charts, results    │     │  Pydantic schemas   │     │  ohlc / runs /      │
└─────────────────────┘     │  Job dispatcher     │     │  equity / metrics   │
                            └──────────┬──────────┘     └─────────────────────┘
                                       │
                                       │ enqueue
                                       ▼
                            ┌─────────────────────┐     ┌─────────────────────┐
                            │   Celery Worker     │ ──► │   Trading Engine    │
                            │   (Railway)         │     │   (submodule)       │
                            │   Reads OHLC,       │     │   Event loop, fills,│
                            │   wraps user graph  │     │   positions, NAV    │
                            └──────────┬──────────┘     └─────────────────────┘
                                       │
                                       │ persist results
                                       ▼
                            (back to TimescaleDB)
                            ┌─────────────────────┐
                            │  Upstash Redis      │
                            │  Celery broker      │
                            └─────────────────────┘
```

Celery is the seam between the synchronous REST API and the long-running
engine. The API never blocks on a backtest — it persists a `queued` row and
returns immediately; the worker picks the job up and updates the row as it
progresses (`queued` → `running` → `completed | failed | partial`).

---

## Repository Layout

```
FYP/
├── frontend/              ← SvelteKit (Svelte 5) + Tailwind v4 + shadcn-svelte
│   └── src/
│       ├── routes/        ← File-based routing (login, signup, /app/*)
│       └── lib/           ← Reusable components, charts, schemas, utils
│
├── backend/               ← FastAPI + SQLAlchemy + Alembic + Celery
│   ├── api/               ← Route handlers grouped by feature
│   ├── background/        ← Celery app + async tasks
│   ├── database/          ← SQLAlchemy ORM models
│   ├── migrations/        ← Alembic schema migrations
│   ├── configs/           ← Settings, logging, env loader
│   ├── common/            ← Shared exceptions, enums, mixins
│   ├── middlewares/       ← Logging, rate limiting
│   ├── scripts/           ← One-off DB / data ingest helpers
│   └── tests/             ← Pytest suite (≈ 24 backtest tests + auth + market)
│
└── trading_engine/        ← Git submodule — see trading_engine/README.md
```

A file-by-file breakdown lives in [ARCHITECTURE.md](ARCHITECTURE.md). This
section keeps to the system view.

---

## Backend

### Stack

- **FastAPI** for the HTTP layer (Pydantic v2 schemas, OpenAPI auto-generated at `/docs`)
- **SQLAlchemy 2.x** ORM, **Alembic** for schema migrations
- **Celery** for async job execution, **Valkey/Redis** as the broker
- **PostgreSQL + TimescaleDB** for OHLC and fundamentals (hypertables)
- **JWT** auth, bcrypt password hashing, **Resend** for transactional email

### API surface

| Group | Endpoint | Purpose |
|-------|----------|---------|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/verify-email` | Account lifecycle (register, log in, verify token from email link) |
| Auth | `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/send-again` | Password reset + resend verification |
| Auth | `GET /auth/me` | JWT-guarded current-user lookup |
| Market | `GET /market/ohlc` | OHLC bars for a symbol/timeframe/range |
| Market | `GET /market/universes` | Named universes (S&P 100, NASDAQ 100, sector, etc.) |
| Market | `POST /market/refresh` | Pull fresh OHLC for a symbol via the data dispatcher |
| Backtests | `POST /backtests` | Submit single, multi-symbol fan-out, universe, or sweep backtest |
| Backtests | `GET /backtests` | History — flat per-run list |
| Backtests | `GET /backtests/batches` | History — collapsed one row per batch |
| Backtests | `GET /backtests/status` | Bulk status lookup for many run IDs (used by sweep poller) |
| Backtests | `GET /backtests/{id}/status` | Single-run status |
| Backtests | `GET /backtests/{id}/results` | Full results: summary + series + trades |
| Backtests | `GET /backtests/batch/{id}` | Per-symbol results inside a batch |
| Backtests | `GET /backtests/batch/{id}/combined` | Equal-weight pooled portfolio for a batch |
| Strategies | `POST/GET/PUT/DELETE /strategies` | Saved strategy graphs (CRUD) |
| AI | `POST /ai/build-graph` | Natural-language prompt → strategy graph |
| User | `GET/PUT /user/me`, `POST /user/change-password` | Profile + password change |
| User | `POST /user/datasets/upload`, `GET /user/datasets`, `GET /user/datasets/{id}/preview`, `DELETE /user/datasets/{id}` | BYOD CSV upload, listing, preview, delete |

### Module map

```
backend/
├── server.py              ← FastAPI app entry; registers routers, middleware,
│                            exception handlers; dev: `uv run python server.py`
│
├── api/
│   ├── auth/              ← Register, login, verify-email, JWT dependency
│   ├── market/            ← OHLC fetch
│   ├── backtests/         ← Submit, status, results, batch, sweep, compare,
│   │                        combined-portfolio, history endpoints
│   │   ├── route.py
│   │   ├── schemas.py     ← Pydantic request/response models
│   │   ├── repositories.py← SQL queries via SQLAlchemy
│   │   └── _combine.py    ← Pure equal-weight equity-curve combiner (unit-tested)
│   ├── strategies/        ← CRUD on saved graphs
│   ├── user/              ← BYOD datasets + profile
│   └── ai/                ← LLM strategy generator
│
├── background/
│   ├── celery_app.py      ← Celery config (broker = Valkey/Redis)
│   └── tasks/
│       ├── backtest.py            ← run_backtest_batch_task — per-symbol fan-out
│       ├── graph_strategy.py      ← Adapts a user node graph into the engine's
│       │                            Strategy ABC (topological sort + per-bar eval)
│       ├── cross_sectional.py     ← Universe (factor) strategy: rank N symbols
│       │                            every bar and rebalance into the top-K
│       ├── ohlc_dispatch.py       ← Routes OHLC refresh requests (yfinance / FMP)
│       ├── market_refresh.py      ← yfinance fetcher (primary, free)
│       ├── market_refresh_fmp.py  ← FMP fetcher (fallback, deeper history)
│       ├── fundamentals_refresh.py     ← yfinance ~5-quarter fundamentals
│       ├── fundamentals_refresh_fmp.py ← FMP 30-yr fundamentals
│       ├── _perf_metrics.py       ← Pure functions: Sharpe / Sortino / Calmar / DD
│       └── email.py               ← Verification email send
│
├── database/
│   ├── make_db.py         ← SQLAlchemy engine, session factory, FastAPI dep
│   └── models/            ← ORM tables (one file per table)
│
└── migrations/            ← Alembic versions
```

### Database schema

| Table | Rows scale | Purpose |
|-------|-----------|---------|
| `users` | 10s | Account + email verification |
| `ohlc_bars` | 600k+ (Timescale hypertable) | Historical S&P 500 daily bars |
| `user_ohlc_bars` | per-user | BYOD uploaded data |
| `user_datasets` | per-user | BYOD dataset metadata |
| `fundamental_snapshots` | 1k+ | Point-in-time EPS / ROE / etc. |
| `strategies` | per-user | Saved strategy graphs (JSON) |
| `backtest_batches` | per-submission | Parent of one or more runs |
| `backtest_runs` | per-symbol per-submission | Status, settings, error |
| `run_metrics` | one per completed run | Returns + ratios + drawdowns |
| `equity_points` | bars × runs | Per-bar NAV — drives equity charts |
| `trades` | per fill | Time, side, price, qty for every executed order |

OHLC and equity-point tables are TimescaleDB hypertables — the schema falls
back to plain PostgreSQL automatically if the extension is not installed
(local dev convenience).

### Backtest job lifecycle

```
POST /backtests {settings, graph, symbols?}
  │
  ▼
1. Validate payload (Pydantic) and persist BacktestBatch + N BacktestRun rows (status=queued)
  │
  ▼
2. Enqueue run_backtest_batch_task(batch_id) on Celery
  │
  └──► Worker picks up the task
       │
       ▼
       For each child run (or once for universe mode):
         a. status = running, started_at = now
         b. Load OHLC for symbol/range. Auto-fetch from yfinance/FMP if the
            requested window is not yet covered in ohlc_bars.
         c. Wrap user graph in GraphStrategy:
              - topological sort of nodes
              - per-bar: OnBar → Indicators / Fundamentals → Math → Conditions → Order
         d. Drive trading_engine event loop:
              MarketDataEvent → StrategyHandler → Signal
                 → OrderManager → OrderFillEvent → PositionManager → NAV
         e. After loop: persist RunMetrics, EquityPoint[], Trade[]
         f. status = completed | failed
       │
       ▼
3. Recompute batch.status from child statuses (running | completed | partial | failed)

GET /backtests/{id}/results → returns whatever is persisted at that point
```

The engine itself imposes the determinism contract — same inputs, same
outputs, every time. The Celery task is the boundary that loads inputs,
configures the engine, and writes outputs back. See
[`trading_engine/README.md`](trading_engine/README.md) for engine internals.

### Performance metrics

`_perf_metrics.py` recomputes the standard set from the raw equity curve, not
from the engine — keeping ratio calculation in one well-tested place:

- **Total return** and **annualised return** (CAGR over the active window)
- **Sharpe** and **Sortino** (rf = 0, daily-to-annualised √252)
- **Calmar** = annualised return / |max drawdown|
- **Max drawdown** (peak-to-trough on the NAV series)
- **Volatility** (annualised σ of daily returns)
- **Win rate** (fraction of closed trades with positive realised P&L)
- **Alpha / Beta / Information Ratio** vs Buy & Hold of the same symbol

These are the exact same functions used by the combined-portfolio endpoint,
which means a fan-out batch's pooled NAV gets metrics computed identically to
any single run.

---

## Frontend

### Stack

- **SvelteKit** with **Svelte 5** runes (`$state`, `$derived`, `$props`)
- **Tailwind CSS v4** + **shadcn-svelte** primitives
- **Chart.js** for equity and candle charts
- **lucide-svelte** icons, **svelte-i18n** locale loader
- **Zod** for form validation

### Route map

```
src/routes/
├── +layout.svelte                    ← root: i18n init + theme
├── login / signup / forget-password  ← public auth pages
└── app/                              ← JWT-guarded
    ├── +layout.svelte                ← AppShell with top nav
    ├── backtests/
    │   ├── +page.svelte              ← History (Runs / Batches tab toggle)
    │   ├── new/+page.svelte          ← MAIN BUILDER: canvas + palette + inspector
    │   ├── [id]/+page.svelte         ← Single-run results: KPIs + charts + trades
    │   ├── batch/[id]/+page.svelte   ← Batch results: per-symbol + combined portfolio
    │   ├── compare/+page.svelte      ← Multi-run comparison
    │   └── sweep/+page.svelte        ← Parameter sweep results
    ├── strategies/+page.svelte       ← Saved strategies (search, open, delete)
    ├── datasets/+page.svelte         ← BYOD upload + listing
    ├── docs/+page.svelte             ← In-app node reference
    └── settings/+page.svelte         ← Profile + theme
```

### The builder

The builder at `/app/backtests/new` is the centre of gravity of the UI.

- **Palette** of node categories: Data, Indicators, Fundamentals, Math,
  Conditions, Orders, Risk (SL/TP, sizing). Each node carries a typed param
  schema, validated as the user wires the graph.
- **Canvas** with pan/zoom, drag-to-connect, snap-to-grid. Edges enforce
  socket types (e.g. a Number socket cannot connect to a Boolean socket), so
  invalid graphs are caught before submission.
- **Inspector** panel for the selected node — shows form inputs for that
  node's parameters with inline validation hints.
- **Run config** — symbol/symbols/universe/dataset, start/end date, initial
  capital, fees (bps), slippage (bps).
- **Templates** library — preset strategies users can drop in as a starting
  point (DCA, EDCA, golden cross, RSI mean-reversion, value/momentum factor,
  etc.).
- **AI Builder** — natural-language prompt ("buy when RSI < 30, sell at +8%
  or RSI > 70") generates a wired graph via an LLM call to `/ai/build-graph`.
- **Save Strategy / Load Strategy** — persists the graph to the server, fully
  round-trips back into the builder.
- **Sweep** — pick a parameter on any node, set a numeric range, fan it out
  into a grid backtest.

The builder, like the rest of the app, talks to the backend over `fetch` with
a JWT in the `Authorization` header — there is no Svelte server-side
rendering of authenticated pages, so the same code runs identically on Vercel
and on `pnpm dev`.

### Charts

- **`EquityCurveChart.svelte`** — line chart of NAV over time. Used by
  single-run results, batch combined view, and run comparison (overlays
  multiple curves with shared axes).
- **`CandlestickChart.svelte`** — OHLC candles for the underlying symbol,
  with buy/sell markers overlaid at trade timestamps.

Both components accept time series in their own minimal shape so they can be
fed by any endpoint that returns `{ time, equity }` or `{ time, ohlc }`.

---

## Data Pipeline

The platform's market data is fetched on demand:

```
User submits backtest with symbol, start, end
  │
  ▼
Worker: is the requested [symbol, timeframe, start..end] window covered by ohlc_bars?
  │
  ├─ Yes ──► load and run
  │
  └─ No ───► dispatch refresh
              │
              ▼
              Try yfinance (primary, free, ~250 calls/min effective)
              │
              ├─ Success ──► upsert into ohlc_bars, then load and run
              │
              └─ Rate-limited / missing ──► fall back to FMP
                                              (Financial Modeling Prep —
                                               paid, deeper history)
```

Fundamentals follow the same primary/fallback pattern. yfinance gives roughly
five recent quarters of EPS / ROE / etc., which is enough for short
backtests; longer windows route through FMP for full history.

The dispatcher is `background/tasks/ohlc_dispatch.py` — a single entry point
the rest of the worker uses without caring which provider answered.

---

## Environments

### Local development

The full stack runs in one terminal via `./dev.sh`:

```bash
./dev.sh
```

This boots TimescaleDB + Valkey (Docker), the FastAPI backend, the Celery
worker, and the SvelteKit dev server, with colour-coded interleaved logs.
Press `Ctrl-C` once to stop everything.

Alternatively, four manual terminals:

```bash
docker start timescaledb valkey
cd backend && uv run python server.py
cd backend && uv run celery -A background.celery_app worker --loglevel=info
cd frontend && pnpm dev
```

Full setup steps (database init, migrations, sample data) live in
[QUICKSTART.md](QUICKSTART.md).

### Production

```
Vercel (frontend) ──► Railway API (FastAPI) ──► Timescale Cloud
                  ──► Railway Worker (Celery) ──► Upstash Redis
```

Both Railway services build from a shared `Dockerfile` at the repo root and
must be configured with **Clone submodules = on** so the engine ships into
the image. Detailed env-var matrix and step-by-step provisioning live in
[DEPLOYMENT.md](DEPLOYMENT.md).

### Deployment topology note

The repo is mirrored to two GitHub remotes intentionally: `origin` is the
team's organisation (which Railway watches for backend deploys), and a
personal fork (which Vercel watches for frontend deploys). Every prod-bound
change is merged to `origin/main` first, then `fork/main` is fast-forwarded.
This keeps backend and frontend deploys independent without the operational
cost of a monorepo split.

---

## Validation

| Layer | How it's validated |
|-------|--------------------|
| Backend HTTP | Pytest suite covering auth, market, backtests (≈ 24 backtest tests), strategies — runs against an in-memory SQLite DB so it's hermetic |
| Pure functions | `_combine.py` (equity combiner) and `_perf_metrics.py` (metric helpers) have dedicated unit tests with float-precision asserts |
| Schema | Alembic migrations are checked in — production state is reproducible from `alembic upgrade head` |
| Engine | The submodule has its own deterministic test suite — see [`trading_engine/README.md`](trading_engine/README.md) |
| Frontend | `svelte-check` type-checks every commit; `pnpm build` is the deploy gate |
| End-to-end methodology | Reproducibility, fee/slippage realism, metric correctness, and known limitations are written up in [EVALUATION.md](EVALUATION.md) |

---

## Tech-stack summary

| Concern | Choice | Why |
|---------|--------|-----|
| Frontend framework | SvelteKit (Svelte 5) | Compiler does the work — small bundles, no virtual-DOM diffing tax on the builder canvas |
| Styling | Tailwind v4 + shadcn-svelte | Standard primitives, easy theming |
| Charting | Chart.js | Mature, decent defaults, two simple chart types are enough |
| Backend framework | FastAPI | Pydantic typing, automatic OpenAPI docs, good async story |
| ORM | SQLAlchemy 2.x | First-class with FastAPI, straightforward migrations |
| Migrations | Alembic | Standard for SQLAlchemy |
| Database | PostgreSQL + TimescaleDB | Time-series performance for OHLC + equity points; falls back to plain Postgres |
| Async jobs | Celery + Redis | Battle-tested, the worker model fits long-running backtests |
| Engine | In-house Python (submodule) | Determinism contract is easier to enforce in code we own |
| Hosting | Vercel + Railway + Timescale Cloud + Upstash | Free / hobby tiers cover the FYP scope |
| Email | Resend | Transactional sends from a custom domain (Cloudflare DNS) |

---

## Final note

The webapp is intentionally a *thin layer* over the engine. The frontend's
job is to make a strategy easy to express and a result easy to read. The
backend's job is to schedule, persist, and pool. The engine itself owns
correctness. Keeping those responsibilities separate is what lets the same
test suite, the same metric code, and the same equity-curve combiner answer
every question — single run, fan-out batch, universe rebalance, parameter
sweep — from one source of truth.
