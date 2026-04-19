"""
Market data refresh — Financial Modeling Prep (FMP) source.

Parallel to `market_refresh.py` (yfinance) but backed by FMP's REST API.
Same DB target (`ohlc_bars`); same on-conflict upsert semantics; same
return shape so the CLI / auto-fetch helpers can toggle between sources.

Endpoint used (FMP "stable" API — v3 is deprecated since 2025-08-31 and
returns 403 with an "Error Message: Legacy Endpoint" body for new keys):
  GET /stable/historical-price-eod/full?symbol=SYM&from=YYYY-MM-DD&to=YYYY-MM-DD
Response shape is a flat list:
  [{"symbol": "AAPL", "date": "2026-04-17", "open": 266.96,
    "high": 272.3, "low": 266.72, "close": 270.23,
    "volume": 61436228, "change": ..., "changePercent": ..., "vwap": ...},
   ...]
Sorted newest-first; we don't depend on order.

FMP returns daily bars natively. Weekly and monthly are synthesised by
requesting daily bars and letting the caller downsample — we do NOT
fabricate weekly/monthly bars on the fly. For now this fetcher only
supports `timeframe="1D"`; raise explicitly otherwise so the caller can
fall back to yfinance.

Tasks:
  fetch_and_upsert_fmp(symbol, timeframe="1D", start=None, end=None, session=None)
    — Plain function; used by CLI + single-symbol Celery task.

  refresh_symbol_ohlc_fmp(symbol, timeframe)
    — Celery task with retry.

  refresh_universe_ohlc_fmp(universe_key, timeframe)
    — Celery task: fan out across a universe.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from celery import Task, group
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from background.celery_app import celery_worker
from configs import get_logger, settings
from database.make_db import SessionLocal
from database.models import OhlcBar

logger = get_logger()

_FMP_BASE = "https://financialmodelingprep.com/stable"
_HTTP_TIMEOUT = 30.0

# Default history window when a symbol has no data in DB yet. Mirrors the
# yfinance default so dispatch behavior is the same across sources.
_DEFAULT_START = "2010-01-01"


def _fmp_get(path: str, **params: Any) -> Any:
  """GET /{path}; returns the decoded JSON unchanged.

  The stable `historical-price-eod/full` endpoint returns a flat list of
  bar dicts. Some error responses come back as {"Error Message": "..."}
  with a 200, so we inspect the body even on success.
  """
  api_key = settings.fmp_api_key
  if not api_key:
    raise RuntimeError(
      "FMP_API_KEY is not set — OHLC fetch requires an API key"
    )

  url = f"{_FMP_BASE}{path}"
  all_params = {"apikey": api_key, **params}
  r = httpx.get(url, params=all_params, timeout=_HTTP_TIMEOUT)
  r.raise_for_status()
  data = r.json()
  if isinstance(data, dict) and "Error Message" in data:
    raise RuntimeError(f"FMP error for {path}: {data['Error Message']}")
  return data


def fetch_and_upsert_fmp(
  symbol: str,
  timeframe: str = "1D",
  start: str | None = None,
  end: str | None = None,
  session: Any = None,
) -> dict:
  """Fetch OHLCV from FMP and upsert into `ohlc_bars`.

  Returns the same shape as `market_refresh.fetch_and_upsert`:
    {"symbol": str, "timeframe": str, "rows_upserted": int, "fetch_start": str}
  """
  if timeframe != "1D":
    # FMP v3 exposes historical-chart/{interval} but this project's
    # ohlc_bars schema + universes currently only use daily. Fail loudly
    # rather than silently mis-bucketing weekly/monthly.
    raise ValueError(
      f"market_refresh_fmp only supports timeframe='1D' (got {timeframe!r})"
    )

  own_session = session is None
  if own_session:
    session = SessionLocal()

  try:
    # --- Determine fetch start date (resume from latest bar when unset) ---
    if start:
      fetch_start = start
    else:
      latest: datetime | None = session.execute(
        select(func.max(OhlcBar.time)).where(
          OhlcBar.symbol == symbol,
          OhlcBar.timeframe == timeframe,
        )
      ).scalar_one_or_none()

      if latest:
        fetch_start = (latest + timedelta(days=1)).strftime("%Y-%m-%d")
      else:
        fetch_start = _DEFAULT_START

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fetch_end = end or today
    if fetch_start >= fetch_end:
      logger.info("refresh(fmp) %s %s: already up to date", symbol, timeframe)
      return {
        "symbol": symbol, "timeframe": timeframe,
        "rows_upserted": 0, "fetch_start": fetch_start,
      }

    logger.info(
      "refresh(fmp) %s %s: fetching %s → %s",
      symbol, timeframe, fetch_start, fetch_end,
    )
    data = _fmp_get(
      "/historical-price-eod/full",
      symbol=symbol,
      **{"from": fetch_start, "to": fetch_end},
    )

    # The stable endpoint returns a flat list of bar dicts. A few older
    # schemas (or legacy callers mocking the v3 shape) return
    # {"symbol": ..., "historical": [...]} — we accept both.
    if isinstance(data, list):
      historical = data
    elif isinstance(data, dict):
      historical = data.get("historical") or []
    else:
      historical = []

    if not historical:
      logger.warning("refresh(fmp) %s %s: no data in window", symbol, timeframe)
      return {
        "symbol": symbol, "timeframe": timeframe,
        "rows_upserted": 0, "fetch_start": fetch_start,
      }

    dialect = session.connection().dialect.name
    rows_upserted = 0

    for entry in historical:
      raw_date = entry.get("date")
      if not raw_date:
        continue
      try:
        bar_time = datetime.strptime(raw_date[:10], "%Y-%m-%d").replace(
          tzinfo=timezone.utc,
        )
      except ValueError:
        continue

      # Daily bars — snap to midnight UTC so the PK dedupes cleanly, matching
      # the yfinance path.
      bar_time = bar_time.replace(hour=0, minute=0, second=0, microsecond=0)

      # FMP returns numeric fields as floats/ints; None/missing = skip row.
      try:
        open_v = float(entry["open"])
        high_v = float(entry["high"])
        low_v = float(entry["low"])
        close_v = float(entry["close"])
      except (KeyError, TypeError, ValueError):
        continue
      volume_raw = entry.get("volume")
      volume_v = int(volume_raw) if volume_raw is not None else None

      bar_data = dict(
        symbol=symbol,
        timeframe=timeframe,
        time=bar_time,
        open=open_v,
        high=high_v,
        low=low_v,
        close=close_v,
        volume=volume_v,
      )

      if dialect == "postgresql":
        stmt = pg_insert(OhlcBar).values(**bar_data)
        stmt = stmt.on_conflict_do_update(
          index_elements=["symbol", "timeframe", "time"],
          set_={
            k: stmt.excluded[k]
            for k in ("open", "high", "low", "close", "volume")
          },
        )
        session.execute(stmt)
      else:
        session.merge(OhlcBar(**bar_data))

      rows_upserted += 1

    session.commit()
    logger.info(
      "refresh(fmp) %s %s: upserted %d rows",
      symbol, timeframe, rows_upserted,
    )
    return {
      "symbol": symbol, "timeframe": timeframe,
      "rows_upserted": rows_upserted, "fetch_start": fetch_start,
    }

  except Exception:
    session.rollback()
    raise
  finally:
    if own_session:
      session.close()


# ---------------------------------------------------------------------------
# Celery tasks (FMP variant)
# ---------------------------------------------------------------------------

@celery_worker.task(bind=True, max_retries=3, default_retry_delay=60)
def refresh_symbol_ohlc_fmp(
  self: Task,
  symbol: str,
  timeframe: str = "1D",
  start: str | None = None,
  end: str | None = None,
) -> dict:
  try:
    return fetch_and_upsert_fmp(
      symbol=symbol, timeframe=timeframe, start=start, end=end,
    )
  except Exception as exc:
    logger.error("refresh_symbol_ohlc_fmp %s failed: %s", symbol, exc)
    raise self.retry(exc=exc)


@celery_worker.task(bind=True, max_retries=0)
def refresh_universe_ohlc_fmp(
  self: Task, universe_key: str, timeframe: str = "1D",
) -> dict:
  from api.market.universes import get_universe_symbols

  try:
    symbols = get_universe_symbols(universe_key)
  except KeyError:
    raise ValueError(f"Unknown universe: {universe_key!r}")

  job = group(
    refresh_symbol_ohlc_fmp.s(symbol, timeframe) for symbol in symbols
  )
  result = job.apply_async()
  logger.info(
    "refresh_universe_ohlc_fmp %s: enqueued %d tasks (group %s)",
    universe_key, len(symbols), result.id,
  )
  return {
    "universe": universe_key,
    "symbols_enqueued": len(symbols),
    "group_id": result.id,
  }
