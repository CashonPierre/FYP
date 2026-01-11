# Backend Plan — Database + API (UI-Aligned)

This plan focuses on **database + backend API** needed by the UI. The **backtest engine/compute** can be implemented in parallel by your teammate, but the schema + API contract should be agreed early.

## 0) Goals

- Use **PostgreSQL + TimescaleDB** for time-series data (OHLC, equity curves).
- Use **Alembic** to version-control the **schema** (not data) so every environment stays consistent.
- Provide minimal **Backtest API endpoints** that match the current frontend expectations (strategy graph input; results JSON output).

## 1) Current Backend State (What Exists Today)

- FastAPI app entry: `backend/server.py`
  - CORS, logging middleware, app-level exception handler.
  - Only `auth_router` is registered.
- Auth module: `backend/api/auth/*`
  - Register/login/verify-email/me endpoints exist.
  - Uses SQLAlchemy `User` model.
  - Celery task exists for sending email (logs in debug).
- Database: `backend/database/make_db.py`
  - Engine/session are now env-driven via `settings.database_url` (defaults to Postgres on port 5432).
  - Models: `User` (`backend/database/models/users.py`) and `OhlcBar` (`backend/database/models/ohlc_bars.py`).
- Market data read API:
  - `GET /market/ohlc` backed by Timescale `ohlc_bars` (for UI candlestick chart).
- Background tasks: Celery configured (`backend/background/celery_app.py`) with valkey/redis URL.

## 2) High-Level Architecture (Target)

- **API service** (FastAPI):
  - Accept strategy graph payloads from UI.
  - Provide job status and results (JSON).
  - Provide history and saved strategies.
- **Database** (Postgres + TimescaleDB):
  - Relational entities (users, strategies, runs, trades).
  - Time-series hypertables (OHLC market data and/or per-run equity).
- **Async execution** (Celery):
  - Run backtests as background jobs.
  - Persist results and publish progress.

## 3) Database Plan (Postgres + TimescaleDB)

### 3.1 Tables (Relational)

Minimum recommended tables (names are suggestions):

- `users`
  - Existing `User` model maps here.
- `strategies`
  - `id`, `user_id`, `name`, `graph_json` (or normalized graph tables later), `created_at`, `updated_at`
- `backtest_runs`
  - `id`, `user_id`, `strategy_id`, `status` (`queued|running|completed|failed`), `started_at`, `ended_at`, `error_message?`
  - `settings_json` (initial capital, symbol, timeframe, fees/slippage, date range)
- `run_metrics`
  - `run_id` PK/FK, plus summary numbers (return, drawdown, sharpe, etc)
- `trades`
  - `id`, `run_id`, `time`, `side`, `symbol`, `price`, `qty`, `fee`, `slippage`

### 3.2 TimescaleDB hypertables (Time-series)

We are choosing **Option A**: store raw market data once and reuse it for all runs.

- Shared market data hypertable:
  - `ohlc_bars(symbol, timeframe, time, open, high, low, close, volume)`
  - hypertable on `time`
  - used by engine for all runs
- Per-run outputs (recommended):
  - `equity_curve(run_id, time, equity)` hypertable on `time`
  - `trades(run_id, time, side, price, qty, ...)` normal table or hypertable depending on volume

### 3.3 Ingesting your S&P500 daily OHLC dataset (Option A)

You already have a combined CSV:
- `/Users/woodylei/Downloads/archive (2)/all_stocks_5yr.csv`
- Columns: `date,open,high,low,close,volume,Name` (where `Name` is the ticker).

**Step 1: create the Timescale schema**
- Run `backend/scripts/timescale_init.sql` against your target Postgres database (must have Timescale installed).

**Step 2: load the CSV into `ohlc_bars`**
Fastest path is Postgres `COPY`. A simple helper script is included:
- `backend/scripts/ingest_ohlc_csv.py`

Example:
```bash
export DATABASE_URL="postgresql://dbuser:dbadmin@localhost:5432/appdb"
python backend/scripts/ingest_ohlc_csv.py --csv "/Users/woodylei/Downloads/archive (2)/all_stocks_5yr.csv" --timeframe 1D
```

This loads into:
- `ohlc_bars(time, symbol, timeframe, open, high, low, close, volume)`

Notes:
- The CSV `date` is loaded into the `time` column (timestamptz). For daily bars it’s “midnight” in the DB timezone.
- For large datasets, always prefer `COPY`/bulk load over ORM inserts.
- The ingest script loads into a temp staging table and does an upsert, so it’s safe to re-run.

### 3.4 Migrations (Alembic)

Use Alembic for:
- Creating tables + indexes
- Creating Timescale extension: `CREATE EXTENSION IF NOT EXISTS timescaledb;`
- Creating hypertables: `SELECT create_hypertable('equity_curve', 'time', if_not_exists => TRUE);`
- Future schema changes

Rule: avoid `Base.metadata.create_all()` in production workflows once Alembic is in place.

## 4) Backend API Plan (UI-Aligned)

### 4.1 Strategy Graph input (from UI)

The UI already exports a graph shape (nodes + edges + handles). Backend should accept something like:
- `POST /backtests` body: `{ version, settings, graph: { nodes, edges } }`

### 4.2 Results output (to UI)

The UI expects this structure (also documented in `UI_PLAN.md`):
- `GET /backtests/{id}/results` → JSON:
  - `summary`: KPIs + metadata
  - `series.ohlc[]`: `{ time, open, high, low, close, volume? }`
  - `series.equity[]`: `{ time, equity }`
  - `series.trades[]`: `{ time, side, price, qty?, symbol?, ... }`

### 4.3 Minimal endpoint list (MVP)

- `GET /market/ohlc`
  - Read OHLC bars for a symbol/timeframe/range (used by UI charts)
- `POST /backtests`
  - Create a run, enqueue background job, return `{ id, status }`
- `GET /backtests/{id}/status`
  - `{ status, progress?, startedAt?, eta?, message? }`
- `GET /backtests/{id}/results`
  - Final results payload (shape above)
- `GET /backtests`
  - List history for the user (id, status, timeframe, return, createdAt, etc)
- Optional: `POST /strategies`, `GET /strategies`
  - Save/reuse templates

## 5) Implementation Phases (No Engine Work Required)

### Phase 0 — Environment + config
- Add a Postgres/Timescale dev setup (Docker compose recommended).
- Make DB choice env-driven (don’t hardcode SQLite vs Postgres).
- Confirm CORS allows the Svelte dev origin(s).

### Phase 1 — Alembic + schema skeleton
- Add Alembic.
- Create initial migrations for: users (if needed), strategies, backtest_runs, trades, run_metrics.
- Add Timescale extension + hypertables.

### Phase 2 — API scaffolding (mocked results)
- Implement `/backtests` endpoints with mocked job execution + mocked results payload that matches the UI.
- Persist `graph` and `settings` in DB so results are reproducible.

### Phase 3 — Integrate engine outputs
- Replace mocked results with real engine results (same JSON shape).

## 6) Notes / Risks to Track

- `backend/database/make_db.py` currently uses SQLite by a hardcoded flag; plan is to move to env-driven config.
- TimescaleDB requires explicit SQL for extension/hypertables; autogenerate migrations may not capture this automatically.
- Auth code should be validated before UI auth integration (there are signs of logic inconsistencies); defer fixes until API wiring begins.

## 7) Open Questions (Decide Early)

- Timeframe model: store as string (`"1h"`, `"1D"`) vs enum.
- Progress delivery: polling (`/status`) vs websocket/SSE.
- Multi-asset runs: how to represent series (`ohlc` per symbol) and trades for multiple symbols.

## 8) Beginner Walkthrough — Postgres + TimescaleDB in This Repo

This section is a “from SQLite to Postgres/Timescale” guide.

### 8.1 Mental model
- **PostgreSQL** is your main database (tables, indexes, SQL, transactions).
- **TimescaleDB** is a Postgres extension specialized for time-series tables (hypertables).
- You still use **SQLAlchemy** the same way for normal tables (users/strategies/runs/trades).
- For Timescale-specific operations (create extension, create hypertable), you usually run raw SQL once (via Alembic migrations or an init SQL).

### 8.2 What changes compared to SQLite
- SQLite is a single local file (`app.db`). Postgres is a server process with a database name, user, password, and port.
- In Postgres, schema changes should be tracked via **Alembic** migrations (recommended once you have teammates/environments).
- Bulk data loads (like your S&P500 OHLC CSV) should use Postgres `COPY` (fast) rather than ORM inserts (slow).

### 8.3 Install + run TimescaleDB locally (Docker, recommended)

**1) Install Docker Desktop**
- Install Docker Desktop for macOS/Windows and make sure `docker` works in terminal:
  - `docker version`

**2) Start a TimescaleDB container**
This starts Postgres+Timescale on port `5432` and persists data in a Docker volume:
```bash
docker volume create timescale_data

docker run -d --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_DB=appdb \
  -e POSTGRES_USER=dbuser \
  -e POSTGRES_PASSWORD=dbadmin \
  -v timescale_data:/var/lib/postgresql/data \
  timescale/timescaledb:latest-pg16
```

**3) Connect with psql (inside the container)**
```bash
docker exec -it timescaledb psql -U dbuser -d appdb
```

Useful `psql` commands:
- `\\dt` list tables
- `\\d ohlc_bars` describe table
- `\\dx` list installed extensions
- quit: `\\q`

**4) Create the schema + hypertable**
```bash
docker exec -i timescaledb psql -U dbuser -d appdb < backend/scripts/timescale_init.sql
```

**5) Verify Timescale is working**
```bash
docker exec -it timescaledb psql -U dbuser -d appdb -c "SELECT extname FROM pg_extension;"
docker exec -it timescaledb psql -U dbuser -d appdb -c "SELECT * FROM timescaledb_information.hypertables;"
```

### 8.4 Set backend config to point at Postgres

There are two “URLs” in this repo right now:
- The ingest script uses `DATABASE_URL` (env var) for convenience.
- The backend app settings currently use separate env vars (`DATABASE_HOST`, `DATABASE_USERNAME`, etc) from `backend/configs/config.py`.

To point your backend at the docker DB, you typically want:
```bash
export DATABASE_DRIVER="postgresql+psycopg2"
export DATABASE_USERNAME="dbuser"
export DATABASE_PASSWORD="dbadmin"
export DATABASE_HOST="localhost"
export DATABASE_PORT="5432"
export DATABASE="appdb"
```

And for the ingest script:
```bash
export DATABASE_URL="postgresql://dbuser:dbadmin@localhost:5432/appdb"
```

### 8.5 Ingesting your CSV (S&P500 daily OHLC)
1) Ensure you’ve run the init SQL (schema + hypertable).
2) Ensure your python environment has `psycopg2` (already listed in `backend/requirements.txt`).
3) Run:
```bash
export DATABASE_URL="postgresql://dbuser:dbadmin@localhost:5432/appdb"
python backend/scripts/ingest_ohlc_csv.py --csv "/Users/woodylei/Downloads/archive (2)/all_stocks_5yr.csv" --timeframe 1D
```

Verify row counts:
```bash
docker exec -it timescaledb psql -U dbuser -d appdb -c "SELECT COUNT(*) FROM ohlc_bars;"
docker exec -it timescaledb psql -U dbuser -d appdb -c "SELECT symbol, MIN(time), MAX(time) FROM ohlc_bars GROUP BY symbol ORDER BY symbol LIMIT 5;"
```

### 8.6 How the backend code will talk to Postgres
Where it’s wired today:
- DB engine + session dependency: `backend/database/make_db.py`
  - currently hardcoded to SQLite (temporary)
- Settings that will be used for Postgres URL: `backend/configs/config.py` (`database_url` computed field)

In FastAPI, the common flow is:
- A route depends on `get_session()` from `backend/database/make_db.py`
- That yields a SQLAlchemy `Session`
- Repositories run queries using that session (see auth example: `backend/api/auth/repositories.py`)

### 8.7 How Timescale data is used by the product
- `ohlc_bars` is **shared market data** for all backtests (Option A).
- The engine reads `ohlc_bars` for the requested symbol(s)/timeframe/date range.
- Run outputs (equity/trades/metrics) get stored per `run_id`, so results pages can load quickly.
