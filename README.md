# Quant Backtester

A web-based, no-code platform for designing and running trading-strategy
backtests. Users assemble strategies in a visual node-graph editor, parameterise
the run (symbols, dates, capital, fees, slippage), and submit; the platform
fetches the necessary market data, executes the strategy through a
deterministic in-house engine, and returns performance metrics, charts, and a
trade log.

This is the entry-point document. It orients you across the three components,
links to the deeper docs for each, and shows the minimum needed to run the
project locally.

---

## Live Demo

- **Frontend:** [https://fyp-kappa-cyan.vercel.app](https://fyp-kappa-cyan.vercel.app)
- **API:** the backend deployed on Railway (URL provided in deployment notes)

A demo account can be created via the in-app sign-up flow; the verification
email is delivered through Resend on a custom domain.

---

## What's in this Repository

The project is split across three components:

| Component | Path | Description | Document |
|-----------|------|-------------|----------|
| **Web application** | `frontend/`, `backend/` | The SvelteKit UI, the FastAPI service, the Celery worker, and the data pipeline. Everything the user interacts with. | [WEBAPP.md](WEBAPP.md) |
| **Trading engine** | `trading_engine/` *(submodule)* | The deterministic event-driven backtesting kernel. Owns the per-bar execution loop, fills, positions, and NAV mark-to-market. Maintained as its own repo. | [trading_engine/README.md](trading_engine/README.md) |
| **Documentation** | this repo root | Architecture references, deployment guide, evaluation methodology. | links below |

```
FYP/
├── frontend/        ← SvelteKit (Svelte 5) — visual builder, results pages
├── backend/         ← FastAPI + SQLAlchemy + Celery — REST API, async jobs
├── trading_engine/  ← Submodule (Quant-Backtester/trading_engine)
├── README.md        ← this file
├── WEBAPP.md        ← deep dive on frontend + backend
├── ARCHITECTURE.md  ← file-by-file reference for the codebase
├── QUICKSTART.md    ← how to run locally
├── DEPLOYMENT.md    ← production hosting setup (Vercel + Railway + Timescale)
└── EVALUATION.md    ← validation methodology, tests, limitations
```

---

## High-level Architecture

```
   ┌──────────────────┐    HTTPS    ┌──────────────────┐  enqueue   ┌──────────────────┐
   │   SvelteKit UI   │ ──────────► │   FastAPI API    │ ─────────► │  Celery Worker   │
   │   (Vercel)       │             │   (Railway)      │            │   (Railway)      │
   └──────────────────┘             └────────┬─────────┘            └─────────┬────────┘
                                             │                                │
                                             │ persist                        │ runs
                                             ▼                                ▼
                                  ┌────────────────────┐             ┌──────────────────┐
                                  │  TimescaleDB       │ ◄────────── │  Trading Engine  │
                                  │  (Timescale Cloud) │   results   │  (submodule)     │
                                  └────────────────────┘             └──────────────────┘
```

A backtest submission persists a `queued` row, the worker picks it up,
loads OHLC data (auto-fetching from yfinance / FMP if not yet cached), wraps
the user's strategy graph into the engine's `Strategy` ABC, drives the engine
to completion, then writes back metrics, the equity curve, and trades. The
frontend polls until the run is complete and renders the results.

For the full data flow and module-level breakdown, see
[WEBAPP.md](WEBAPP.md). For engine internals (event queue, determinism rules,
order/position model), see [trading_engine/README.md](trading_engine/README.md).

---

## What the Platform Does

- **Visual strategy builder** — drag nodes onto a canvas: data, indicators (SMA/EMA/RSI/MACD/Bollinger/...), fundamentals (EPS/ROE/...), math, conditions, orders, risk (stop-loss / take-profit / sizing).
- **AI Builder** — natural-language prompt → wired strategy graph via an LLM call.
- **Strategy templates** — preset starting points: DCA, EDCA, golden cross, RSI mean-reversion, value & momentum factor strategies.
- **Multiple execution modes** — single symbol, multi-symbol fan-out (independent runs), cross-sectional universe (one factor strategy ranking N symbols every bar), or BYO uploaded dataset.
- **Combined portfolio view** — fan-out batches are equal-weight pooled into one NAV, with portfolio metrics recomputed from the pooled curve.
- **Parameter sweep** — pick a node parameter, set a range, fan-out into a grid backtest with side-by-side comparison.
- **Run comparison** — overlay the equity curves of any two or more completed runs.
- **CSV exports** — equity and trade logs.
- **Auth** — JWT, password hashing, email verification via Resend.

A more thorough feature tour and the full API surface are in
[WEBAPP.md](WEBAPP.md#features).

---

## Quick Start

> **Prerequisites:** Docker Desktop, Python 3.11+ with [uv](https://github.com/astral-sh/uv), Node.js + pnpm.

```bash
# 1. Clone (with the engine submodule)
git clone https://github.com/Quant-Backtester/FYP.git
cd FYP
git submodule update --init --recursive

# 2. Start the database
docker run -d --name timescaledb -p 5432:5432 \
  -e POSTGRES_DB=appdb -e POSTGRES_USER=dbuser -e POSTGRES_PASSWORD=dbadmin \
  timescale/timescaledb:latest-pg16

# 3. Backend
cd backend
uv sync
uv run python -m alembic upgrade head
uv run python server.py    # → http://localhost:8000

# 4. Frontend (new terminal)
cd frontend
pnpm install
pnpm dev                   # → http://localhost:5173
```

Or, with everything in one terminal:

```bash
./dev.sh
```

The full local-dev guide — including loading sample S&P 500 data and the
Celery worker — is in [QUICKSTART.md](QUICKSTART.md).

---

## Project Documentation

| Document | Audience | What it covers |
|----------|----------|----------------|
| [README.md](README.md) | First-time reader | This file: orientation across the project |
| [WEBAPP.md](WEBAPP.md) | Reviewer / supervisor | Frontend + backend deep dive: features, architecture, modules, data flow, validation |
| [trading_engine/README.md](trading_engine/README.md) | Reviewer / supervisor | Engine deep dive: design philosophy, determinism rules, event model |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Developer | File-by-file reference for `backend/`, `frontend/`, `trading_engine/` |
| [QUICKSTART.md](QUICKSTART.md) | Developer | Step-by-step local setup with troubleshooting |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Operator | Production hosting: Vercel, Railway, Timescale Cloud, Upstash, env-var matrix |
| [EVALUATION.md](EVALUATION.md) | Reviewer | Validation methodology, tests, benchmarks, limitations |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | SvelteKit (Svelte 5), Tailwind v4, shadcn-svelte, Chart.js |
| Backend | FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Async jobs | Celery + Valkey/Redis broker |
| Database | PostgreSQL + TimescaleDB |
| Engine | In-house Python (zero-dependency, deterministic) |
| Hosting | Vercel · Railway · Timescale Cloud · Upstash Redis |
| Email | Resend (custom Cloudflare-DNS domain) |
