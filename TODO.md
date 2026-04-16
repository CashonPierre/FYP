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
- [ ] Forget password backend endpoint (UI exists, backend missing)
- [x] Auth guard for `/app/*` routes (redirect to `/login` if no token)
- [ ] **Email delivery via Resend** — replace fake SMTP in `background/tasks/email.py` with Resend API (free tier, 100 emails/day). Add `RESEND_API_KEY` to `.env`. Unblocks real email verification for new signups.

---

## Market Data

- [x] `OhlcBar` DB model (TimescaleDB hypertable)
- [x] `GET /market/ohlc` endpoint (symbol, timeframe, date range)
- [x] S&P500 OHLC data in DB (619k rows, 2013–2018 daily)
- [ ] Refresh market data via yfinance (post-MVP — extend to 2013–today)

---

## Database / Migrations

- [x] SQLAlchemy + PostgreSQL configured
- [x] Alembic scaffold set up
- [x] `Strategy` model
- [x] `BacktestRun` model
- [x] `RunMetrics` model
- [x] `Trade` model
- [x] Write + apply Alembic migration for all models (baseline + new tables migration; fresh setup: `uv run python -m alembic upgrade head`)
- [ ] Add `EquityCurve` hypertable (post-MVP)

---

## Backtest API

- [x] `POST /backtests` — enqueue job, return `{ id, status }`
- [x] `GET /backtests/{id}/status` — return job status
- [x] `GET /backtests/{id}/results` — return summary + OHLC series + trades
- [x] `GET /backtests` — list user's backtest history
- [x] Registered in `server.py`

---

## Strategy API

- [x] `POST /strategies` — save a strategy graph
- [x] `GET /strategies` — list user's saved strategies
- [x] `GET /strategies/{id}` — get a single strategy

---

## Celery / Background Tasks

- [x] Valkey (Redis-compatible) broker configured and running in Docker
- [x] Celery worker connects and picks up jobs
- [x] Email send task (`background/tasks/email.py`)
- [x] Backtest execution task — loads OHLC from DB, runs engine, stores RunMetrics + Trade results
- [ ] Equity curve capture — engine doesn't yet emit equity snapshots per bar; `equity` series is always empty in results

---

## Engine Integration

- [x] Engine added as git submodule at `trading_engine/`
- [x] Backend renamed `common/` → `app_common/` to avoid namespace collision with engine's `common/`
- [x] Fix `trading_engine/strategies/strategy.py` inconsistent import (was `trading_engine.common.mixins`, now `common.mixins`)
- [x] Celery task feeds OHLC bars to engine as `MarketDataEvent`s and stores results
- [x] **MOCKED: Strategy input** — task hardcodes `DCA(buyframe=10, buy_amount=10)` regardless of the graph JSON submitted. Graph is saved to DB but not yet parsed or used.
- [ ] Parse graph JSON → instantiate strategy dynamically (`background/tasks/backtest.py` line 85)
- [ ] `DBMarketDataSource` fully implemented — **teammate**
- [ ] Fix `JsonMarketDataSource` wrong base class — **teammate**
- [ ] Fix Cancel/Modify/Close signals in OrderManager — **teammate**
- [ ] Fix `_realized_pnl` never updated on close — **teammate**
- [ ] Take profit / stop loss — general order feature, should be configurable per Buy/Sell node in the builder UI; currently disabled (`None`) in DCA until UI supports it

---

## Frontend — Builder (`/app/backtests/new`)

- [x] Drag-drop canvas (nodes, edges, pan/zoom)
- [x] Block palette + inspector
- [x] Strategy validation + "Run" gating
- [x] Export/Import strategy JSON
- [x] Save/Load draft (localStorage)
- [x] Run settings (symbol, date range)
- [x] "Run" button calls real `POST /backtests` with JWT token
- [x] Redirects to `/app/backtests/<real-uuid>` on submit

---

## Frontend — Results Page (`/app/backtests/[id]`)

- [x] KPI summary cards (P/L, return, drawdown, sharpe, trades, win rate)
- [x] Candlestick chart with buy/sell markers
- [x] Equity curve chart
- [x] Polls `GET /{id}/status` every 2s until completed/failed
- [x] Fetches and renders real metrics + OHLC + trades from API
- [x] Legacy mock path preserved for `mock_*` run IDs
- [x] **MOCKED: "Running (mock)"** label on progress card — fixed: now shows real status
- [x] **MOCKED: "From sessionStorage (mock)"** label on Run Config card — removed
- [ ] Equity curve is always empty (engine doesn't emit equity snapshots yet)
- [x] Failed state — shows error card with message from API
- [ ] Trades table (sortable, filterable) — currently only shown as chart markers

---

## Frontend — History Page (`/app/backtests`)

- [ ] List user's backtest runs (date, symbol, status, total return)
- [ ] Link to results page per run
- [ ] Delete run action (optional)

---

## Frontend — Other

- [x] Landing page at `/` — hero, feature strip, nav with login/signup buttons
- [ ] Auth guard for `/app/*` routes (redirect to `/login` if no token in localStorage)

---

## Tests

- [x] 16 fast integration tests (SQLite, no Docker) — `uv run pytest tests/`
- [x] 3 e2e tests (real DB + Valkey + Celery worker) — `uv run pytest tests/test_e2e.py -m e2e`
- [ ] Test for failed backtest error message surfaced to frontend

---

## DevOps / Setup

- [x] TimescaleDB in Docker (`docker start timescaledb`)
- [x] Valkey in Docker (`docker start valkey`)
- [x] `QUICKSTART.md` — step-by-step local dev guide
- [x] `CLAUDE.md` — project context for AI assistant
- [x] `ARCHITECTURE.md` — file/folder tree with descriptions
- [x] `.vscode/settings.json` — VS Code Python interpreter set to backend `.venv`
- [ ] Docker Compose file for full local stack (backend + TimescaleDB + Valkey + Celery)
- [ ] Alembic migration applied so teammates can `uv run python -m alembic upgrade head` instead of relying on `create_all`

---

## Known Bugs / Issues

- [ ] Engine `pyproject.toml` declares `src/` layout but no `src/` dir — `pip install -e .` broken. **Teammate to fix.**
- [ ] `trading_engine/market_data/source.py` — `JsonMarketDataSource` inherits wrong class. **Teammate to fix.**
- [ ] `trading_engine/core/order_manager.py` — Cancel/Modify/Close signals silently ignored. **Teammate to fix.**
- [ ] `trading_engine/core/position_manager.py` — `_realized_pnl` never updated on close. **Teammate to fix.**
- [ ] User router (`backend/api/user/route.py`) is empty — no profile/settings endpoints.
