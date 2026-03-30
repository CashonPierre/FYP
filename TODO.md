# Project To-Do Checklist

Track what's done and what's left. Update this file as you go.

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

---

## Market Data

- [x] `OhlcBar` DB model (TimescaleDB hypertable)
- [x] `GET /market/ohlc` endpoint (symbol, timeframe, date range)
- [x] S&P500 CSV ingest script (`backend/scripts/ingest_ohlc_csv.py`)
- [x] TimescaleDB init SQL (`backend/scripts/timescale_init.sql`)

---

## Database / Migrations

- [x] SQLAlchemy + PostgreSQL configured
- [x] Alembic structure set up
- [ ] Create initial Alembic migration (User + OhlcBar)
- [ ] Add `Strategy` model
- [ ] Add `BacktestRun` model (status, settings_json, timestamps)
- [ ] Add `RunMetrics` model (return, drawdown, sharpe, etc.)
- [ ] Add `Trade` model (per-run trades)
- [ ] Add `EquityCurve` hypertable (per-run equity time-series)
- [ ] Generate + apply migration for all new models

---

## Backtest API (Critical Path)

- [ ] `POST /backtests` — accept strategy graph + settings, enqueue Celery job, return `{ id, status }`
- [ ] `GET /backtests/{id}/status` — return job status + progress
- [ ] `GET /backtests/{id}/results` — return full results payload (summary + series)
- [ ] `GET /backtests` — list user's backtest history
- [ ] Register backtest router in `server.py`

---

## Strategy API

- [ ] `POST /strategies` — save a strategy graph
- [ ] `GET /strategies` — list user's saved strategies
- [ ] `GET /strategies/{id}` — get a single strategy

---

## Celery / Background Tasks

- [x] Celery app configured (Valkey broker)
- [x] Email send task (`background/tasks/email.py`)
- [ ] Backtest execution task — calls engine, stores results in DB
- [ ] Progress tracking (update `BacktestRun.status` during execution)

---

## Engine Integration

- [x] Engine added as git submodule (`engine/`, `Quant-Backtester/trading_engine`)
- [x] Temporary `sys.path` workaround in `backend/server.py` (teammate needs to fix engine `pyproject.toml`)
- [ ] Wire engine to accept strategy graph JSON from API
- [ ] `DBMarketDataSource` fully implemented in engine (currently stub)
- [ ] Engine returns structured results (trades, equity curve, metrics) storable in DB

---

## Frontend — Builder

- [x] Drag-drop canvas (nodes, edges, pan/zoom)
- [x] Block palette + inspector
- [x] Strategy validation + "Run" gating
- [x] Export/Import strategy JSON
- [x] Save/Load draft (localStorage)
- [x] Run settings (symbol, date range)
- [x] Mock run + mock results
- [ ] Wire "Run" button to real `POST /backtests`
- [ ] Poll `GET /backtests/{id}/status` for progress
- [ ] Load results from `GET /backtests/{id}/results`

---

## Frontend — Results Page

- [x] KPI summary panel (P/L, return, drawdown, sharpe)
- [x] Candlestick chart with buy/sell markers
- [x] Equity curve chart
- [ ] Running state (progress bar / spinner)
- [ ] Failed state (error message + retry)
- [ ] Trades table (sortable, filterable)
- [ ] "Duplicate in Builder" flow

---

## Frontend — History Page (`/app/backtests`)

- [ ] List user's backtest runs (date, symbol, status, return)
- [ ] Open results / duplicate / delete actions

---

## Frontend — Other

- [ ] Landing page at `/` (replace Svelte placeholder)
- [ ] Auth guard for `/app/*` routes (check JWT token)
- [ ] User settings page (`/app/settings`)

---

## DevOps / Setup

- [x] Docker + TimescaleDB setup documented (`BACKEND_PLAN.md`)
- [x] `CHANGES.md` for non-obvious changes
- [x] `DevGuide.md` for formatter/tooling setup
- [ ] Docker Compose file for full local stack (backend + DB + Valkey + Celery)
- [ ] `.env` template documented (see `env_template.txt`)

---

## Post-MVP / Nice to Have

- [ ] **Refresh market data via yfinance** — current DB has S&P 500 daily OHLC from 2013–2018 (619k rows, sufficient for MVP). Write `backend/scripts/fetch_ohlc_yfinance.py` to pull 2013–today for all ~500 symbols and upsert into `ohlc_bars`. Use Wikipedia S&P 500 list as ticker source.

---

## Known Bugs / Issues

- [ ] Engine `pyproject.toml` declares `src/` layout but no `src/` dir exists — `pip install -e ./engine` broken. **Teammate (engine repo) needs to fix.** Workaround: `sys.path` patch in `backend/server.py`.
- [ ] User router (`backend/api/user/route.py`) is empty — no profile/settings endpoints.
- [ ] Forget password UI is mocked — no backend endpoint.
