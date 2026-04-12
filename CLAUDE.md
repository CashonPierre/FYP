# Quant Backtester FYP — Claude Context

## Project Overview
Web-based backtesting platform as a Final Year Project. Users build trading strategies visually (drag-and-drop), run backtests, and view results.

## Repo Structure
```
~/FYP/                        ← this repo (Quant-Backtester/FYP), branch: UI
├── frontend/                 ← SvelteKit (Svelte 5) + Tailwind v4 + shadcn-svelte
├── backend/                  ← FastAPI + PostgreSQL/TimescaleDB + Celery + Valkey
└── trading_engine/           ← git submodule (Quant-Backtester/trading_engine), teammate's work
```

**GitHub org:** `Quant-Backtester`
**Branches:** `UI` (woodylei's work), `Louis` (teammate's work), both merge to `main` via PRs.

## Tech Stack
- **Frontend:** SvelteKit (Svelte 5), Tailwind v4, shadcn-svelte, lucide icons, svelte-i18n, Chart.js
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL + TimescaleDB, Alembic, Celery, Valkey
- **Engine:** Python (submodule), event-driven backtesting loop
- **Formatter:** Ruff (Python), Svelte extension (VS Code). Tab size: 2.

## Dev Setup
```bash
# 1. Start DB (Docker must be running first)
docker start timescaledb        # user: dbuser, pass: dbadmin, db: appdb, port: 5432

# 2. Backend
cd ~/FYP/backend
python server.py

# 3. Frontend
cd ~/FYP/frontend
pnpm dev                        # → http://localhost:5173
```

## Database
- PostgreSQL + TimescaleDB in Docker container `timescaledb`
- `ohlc_bars`: 619k rows, S&P 500 daily OHLC, 2013–2018 (sufficient for MVP)
- Config: `backend/configs/config.py` — defaults already point to Docker container, no .env needed locally

## Current Backend State
| Area | Status |
|------|--------|
| Auth (register/login/verify/me) | ✅ Done |
| `GET /market/ohlc` | ✅ Done |
| `Strategy`, `BacktestRun`, `RunMetrics`, `Trade` DB models | ✅ Done (not migrated yet) |
| Alembic scaffold | ✅ Done (no migrations written yet) |
| Backtest API endpoints | ❌ Missing |
| Celery backtest task | ❌ Missing |
| User router | ❌ Empty |

## Current Frontend State
| Route | Status |
|-------|--------|
| `/login`, `/signup` | ✅ Wired to backend |
| `/app/backtests/new` | ✅ Full builder (mock run) |
| `/app/backtests/[id]` | ✅ Results page (mock data) |
| `/app/backtests` | ❌ Placeholder |
| `/` | ❌ Placeholder |

## Engine State (trading_engine submodule — teammate's work)
| Component | Status |
|-----------|--------|
| Core run loop | ✅ 95% |
| DCA + EDCA strategies | ✅ Done |
| CSV market data source | ✅ Done |
| Position + portfolio tracking | 🟡 85% (realized P&L bug) |
| Order manager | 🟡 50% (only AddSignal handled) |
| DB market data source | ❌ Stub |
| JSON/API integration | ❌ Missing |

## Engine Bugs (flag to teammate)
- `trading_engine/market_data/source.py` — `JsonMarketDataSource` inherits wrong class
- `trading_engine/core/order_manager.py` — Cancel/Modify/Close signals silently ignored
- `trading_engine/core/position_manager.py` — `_realized_pnl` never updated on close
- `trading_engine/pyproject.toml` — `src/` layout declared but no `src/` dir (`pip install -e .` broken)

## MVP Critical Path (what's left)
1. Write Alembic migrations for new models
2. Implement `POST /backtests`, `GET /backtests/{id}/status`, `GET /backtests/{id}/results`
3. Write Celery backtest task (calls engine, stores results)
4. Teammate: implement `DBMarketDataSource` + JSON strategy input
5. Frontend: wire Run button to real API

## Key Files
- `backend/server.py` — FastAPI app entry point
- `backend/database/models/` — all SQLAlchemy models
- `backend/api/` — route handlers (auth, market, user stub)
- `backend/background/celery_app.py` — Celery config
- `backend/configs/config.py` — app settings
- `backend/migrations/` — Alembic (versions/ is empty)
- `frontend/src/routes/app/backtests/new/+page.svelte` — main builder UI
- `frontend/src/routes/app/backtests/[id]/+page.svelte` — results UI
- `trading_engine/core/engine.py` — engine run loop
- `trading_engine/strategies/` — DCA, EDCA strategies
- `TODO.md` — full checklist
- `CONTEXT.md` — detailed conversation context (not committed)
