# Quickstart Guide

Get the project running locally in a few steps.

---

## Prerequisites

Make sure you have these installed:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/) (`npm install -g pnpm`)
- [Python 3.11+](https://www.python.org/) + [uv](https://github.com/astral-sh/uv) (`pip install uv`)

---

## 1. Clone the Repo

```bash
git clone https://github.com/Quant-Backtester/FYP.git
cd FYP
git submodule update --init --recursive   # pulls trading_engine
```

---

## 2. Start the Database

Open **Docker Desktop** first, then:

```bash
# First time only — create and start the container
docker run -d --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_DB=appdb \
  -e POSTGRES_USER=dbuser \
  -e POSTGRES_PASSWORD=dbadmin \
  -v timescale_data:/var/lib/postgresql/data \
  timescale/timescaledb:latest-pg16

# After first time — just start it
docker start timescaledb
```

---

## 3. Set Up the Backend

```bash
cd backend

# Install dependencies
uv sync

# Run database migrations (creates all tables)
uv run python -m alembic upgrade head

# Start the backend server
uv run python server.py
```

Backend runs at `http://localhost:8000`.
API docs available at `http://localhost:8000/docs`.

---

## 4. Set Up the Frontend

Open a new terminal:

```bash
cd frontend

# Install dependencies
pnpm install

# Start the frontend dev server
pnpm dev
```

Frontend runs at `http://localhost:5173`.

---

## 5. (Optional) Load Market Data

If you have the S&P 500 CSV (`all_stocks_5yr.csv` from Kaggle):

```bash
cd backend
export DATABASE_URL="postgresql://dbuser:dbadmin@localhost:5432/appdb"
uv run python scripts/ingest_ohlc_csv.py --csv "/path/to/all_stocks_5yr.csv" --timeframe 1D
```

The backend and UI work without this — market data endpoints will just return empty results.

---

## Everyday Dev Workflow

```bash
cd ~/FYP
./dev.sh
```

This starts TimescaleDB + Valkey (Docker), the FastAPI backend, the Celery worker, and the SvelteKit frontend — all in one terminal with colour-coded logs.

Press `Ctrl+C` to stop everything at once.

**If you prefer separate terminals:**
```bash
# Terminal 1
docker start timescaledb valkey

# Terminal 2
cd ~/FYP/backend && uv run python server.py

# Terminal 3
cd ~/FYP/backend && uv run celery -A background.celery_app worker --loglevel=info

# Terminal 4
cd ~/FYP/frontend && pnpm dev
```

---

## Repo Structure

```
FYP/
├── frontend/          ← SvelteKit (Svelte 5) + Tailwind v4
├── backend/           ← FastAPI + PostgreSQL/TimescaleDB + Celery
│   ├── api/           ← route handlers (auth, market, backtests)
│   ├── database/      ← SQLAlchemy models
│   ├── migrations/    ← Alembic migrations
│   └── server.py      ← app entry point
└── trading_engine/    ← backtesting engine (git submodule)
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'psycopg2'`**
Run commands with `uv run` (not bare `python`) to use the project venv.

**`Cannot connect to Docker daemon`**
Docker Desktop is not running — open it and wait for the whale icon to stop animating.

**`connection to server at localhost port 5432 failed`**
The DB container is not running. Run `docker start timescaledb`.

**`pnpm: command not found`**
Install pnpm: `npm install -g pnpm`
