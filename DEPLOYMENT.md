# Deployment Guide

## Architecture

```
Vercel (Frontend SvelteKit)
        │
        │ HTTPS
        ▼
Railway — API service   (FastAPI, port 8000)  ──► Timescale Cloud (PostgreSQL + TSDB)
Railway — Worker service (Celery)             ──► Upstash Redis   (Celery broker)
```

Both Railway services share the same Docker image built from the repo-root `Dockerfile`.

The HKU WordPress site (wp2025.cs.hku.hk) is a separate project showcase page —
it is NOT where the app is deployed. It should link to the Vercel URL as the live demo.

---

## Services to Provision

| Service | Provider | Cost |
|---------|----------|------|
| Frontend (SvelteKit) | **Vercel** | Free |
| Backend API | **Railway** | ~$5/mo hobby plan |
| Celery Worker | **Railway** (second service, same project) | same |
| Database | **Timescale Cloud** | Free tier: 1 CPU / 1 GB / 10 GB |
| Redis (broker) | **Upstash Redis** | Free tier: 10k req/day |

---

## Step 1 — Timescale Cloud (Database)

1. Sign up at [cloud.timescale.com](https://cloud.timescale.com) → create a service
   - Pick the region closest to your Railway deployment (e.g. US East)
2. Copy the connection details (host, port, user, password, dbname)
3. Run Alembic migrations from your local machine against the cloud DB:
   ```bash
   cd backend
   DATABASE_HOST=xxx.tsdb.cloud.timescale.com \
   DATABASE_USERNAME=tsdbadmin \
   DATABASE_PASSWORD=yourpassword \
   DATABASE_PORT=5432 \
   DATABASE=tsdb \
   uv run alembic upgrade head
   ```
4. Load market data (≈5 min for all 64 universe symbols, 2013–2018):
   ```bash
   cd backend
   DATABASE_HOST=xxx DATABASE_PASSWORD=xxx \
   DATABASE_USERNAME=tsdbadmin DATABASE_PORT=5432 DATABASE=tsdb \
   uv run python - <<'EOF'
   import sys; sys.path.insert(0, ".")
   from background.tasks.market_refresh import fetch_and_upsert
   from api.market.universes import UNIVERSES
   symbols = list(dict.fromkeys(s for u in UNIVERSES.values() for s in u["symbols"]))
   for sym in symbols:
       r = fetch_and_upsert(sym, "1D", start="2013-01-01", end="2019-01-01")
       print(sym, r["rows_upserted"])
   EOF
   ```

---

## Step 2 — Upstash Redis (Celery Broker)

1. Sign up at [upstash.com](https://upstash.com) → create a Redis database
2. From the "Connect" tab, copy the `rediss://` TLS connection string
3. You'll need: host, port (usually 6379), and password separately for the env vars

---

## Step 3 — Railway (Backend API + Worker)

> **Important:** The backend depends on the `trading_engine` git submodule.
> In each Railway service settings → Source → enable **"Clone submodules"**.
> Without this the Docker build will fail (trading_engine/ will be empty).

#### Service 1: API

1. New project → **Deploy from GitHub repo** → `Quant-Backtester/FYP`
2. Railway auto-detects `Dockerfile` at repo root — no extra config needed
3. Set start command: `uv run python server.py`
4. Settings → Source → enable **Clone submodules**
5. Add env vars (see table below)
6. Note the public URL Railway assigns (e.g. `https://fyp-api.railway.app`)

#### Service 2: Worker

1. Same Railway project → **+ New service** → same GitHub repo
2. Set start command: `uv run celery -A background.celery_app worker --loglevel=info`
3. Settings → Source → enable **Clone submodules**
4. Add the same env vars as the API service — both must share identical database, Redis, and JWT config

#### Env vars for both Railway services

| Variable | Value |
|----------|-------|
| `DEBUG` | `false` |
| `APP_PORT` | `8000` |
| `DATABASE_HOST` | Timescale Cloud host |
| `DATABASE_PORT` | `5432` |
| `DATABASE` | `tsdb` |
| `DATABASE_USERNAME` | `tsdbadmin` |
| `DATABASE_PASSWORD` | *(Timescale password)* |
| `DATABASE_DRIVER` | `postgresql+psycopg2` |
| `VALKEY_SCHEME` | `rediss` |
| `VALKEY_HOST` | Upstash Redis host |
| `VALKEY_PORT` | `6379` |
| `VALKEY_DB` | `0` |
| `JWT_SECRET_KEY` | *(generate: `python -c "import secrets; print(secrets.token_hex(32))"`)* |
| `FRONTEND_URL` | `https://your-app.vercel.app` |
| `ALLOWED_ORIGIN` | `["https://your-app.vercel.app"]` |
| `RESEND_API_KEY` | *(from Resend dashboard)* |
| `RESEND_FROM_EMAIL` | *(verified domain in Resend, e.g. noreply@yourdomain.com)* |

---

## Step 4 — Vercel (Frontend)

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → import `Quant-Backtester/FYP`
2. Set **Root Directory** to `frontend/`
3. Framework preset: **SvelteKit** (auto-detected)
4. Add env vars:

| Variable | Value |
|----------|-------|
| `PUBLIC_BACKEND_URL` | `https://fyp-api.railway.app` *(your Railway API URL)* |
| `BACKEND_ORIGIN` | same as above |

5. Deploy — Vercel auto-deploys on every push to `main`

---

## Step 5 — HKU FYP WordPress Site

The HKU server (`wp2025.cs.hku.hk`) runs WordPress — it cannot host the SvelteKit app.
Use it as a **project showcase page** that the department evaluates.

Suggested content for the WordPress site:
- Project title, abstract, team members
- Link to the **live demo** (your Vercel URL)
- Screenshots / demo video of the backtest UI
- Architecture diagram
- Progress updates as the project develops

Login at: `https://wp2025.cs.hku.hk/fypxxxxx/wp-admin/`

---

## Security Checklist (before going live)

- [ ] `JWT_SECRET_KEY` is a real random 32-byte hex string (not the default `"123"`)
- [ ] `DEBUG=false` on both Railway services
- [ ] `ALLOWED_ORIGIN` set to the exact Vercel URL only (locks down CORS)
- [ ] `RESEND_FROM_EMAIL` uses a verified custom domain
- [ ] Database password is strong (not the local dev default `dbadmin`)
- [ ] Redis uses `rediss://` TLS (Upstash default — just copy their URL)
- [ ] No `.env` files committed to git (`.gitignore` already covers this)

---

## Known Limitations / TODOs

| Item | Notes |
|------|-------|
| Only 64 symbols in DB | SOL-USD excluded (no 2013-2018 data). Expand `universes.py` + re-fetch to add more. |
| Mock data fallback (`mock_` run IDs) | Legacy path in `app/backtests/[id]/+page.svelte` — remove after full API validation |
| No Celery Beat scheduler | OHLC data refresh must be triggered manually for now |
| Engine bugs (teammate's code) | See CLAUDE.md → Engine Bugs section |

---

## Local Dev Reference

```bash
./dev.sh                              # full stack (requires Docker running)
cd backend && uv run pytest           # run tests
cd backend && uv run alembic upgrade head  # apply DB migrations
```
