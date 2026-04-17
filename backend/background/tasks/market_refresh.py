"""
Market data refresh tasks.

Three entry points:
  refresh_symbol_ohlc(symbol, timeframe)
    — Celery task: fetches one symbol from yfinance, upserts into ohlc_bars.
    — Incremental: only fetches bars newer than the latest bar already in DB.
    — Can also be called as a plain function (for CLI / tests) by passing
      _session directly.

  refresh_universe(universe_key)
    — Celery task: fans out one refresh_symbol_ohlc per symbol in a universe.

  refresh_all_tracked_symbols()
    — Celery Beat task: daily refresh for every symbol already in DB plus all
      universe symbols.  Deduplicated so each symbol is only fetched once.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import Task, group
from sqlalchemy import func, select

from background.celery_app import celery_worker
from configs import get_logger
from database.make_db import SessionLocal
from database.models import OhlcBar

logger = get_logger()

# Default history window when a symbol has no data in DB yet
_DEFAULT_START = "2010-01-01"

# yfinance timeframe string → our DB timeframe label
_TF_MAP: dict[str, str] = {
    "1D": "1d",
    "1W": "1wk",
    "1M": "1mo",
}


# ---------------------------------------------------------------------------
# Core fetch-and-upsert logic (reused by task + CLI script)
# ---------------------------------------------------------------------------

def fetch_and_upsert(
    symbol: str,
    timeframe: str = "1D",
    start: str | None = None,
    session: Any = None,
) -> dict:
    """
    Fetch OHLCV from yfinance and upsert into ohlc_bars.

    Parameters
    ----------
    symbol    : ticker symbol (e.g. "AAPL", "BTC-USD")
    timeframe : DB timeframe label ("1D", "1W", "1M")
    start     : ISO date string override; if None, resumes from latest bar in DB
    session   : SQLAlchemy session; if None, a new SessionLocal() is opened

    Returns
    -------
    {"symbol": str, "timeframe": str, "rows_upserted": int, "fetch_start": str}
    """
    import yfinance as yf

    own_session = session is None
    if own_session:
        session = SessionLocal()

    try:
        yf_interval = _TF_MAP.get(timeframe, "1d")

        # --- Determine fetch start date ---
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
                # Resume from the day after the last bar we have
                fetch_start = (latest + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                fetch_start = _DEFAULT_START

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if fetch_start >= today:
            logger.info("refresh %s %s: already up to date", symbol, timeframe)
            return {"symbol": symbol, "timeframe": timeframe, "rows_upserted": 0, "fetch_start": fetch_start}

        # --- Fetch from yfinance ---
        logger.info("refresh %s %s: fetching from %s", symbol, timeframe, fetch_start)
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=fetch_start,
            interval=yf_interval,
            auto_adjust=True,
            actions=False,
        )

        if df.empty:
            logger.warning("refresh %s %s: yfinance returned no data", symbol, timeframe)
            return {"symbol": symbol, "timeframe": timeframe, "rows_upserted": 0, "fetch_start": fetch_start}

        # --- Upsert rows ---
        rows_upserted = 0
        for ts, row in df.iterrows():
            # yfinance returns tz-aware timestamps; normalise to UTC midnight for daily
            bar_time = ts.to_pydatetime()
            if bar_time.tzinfo is None:
                bar_time = bar_time.replace(tzinfo=timezone.utc)
            else:
                bar_time = bar_time.astimezone(timezone.utc)

            bar = OhlcBar(
                symbol=symbol,
                timeframe=timeframe,
                time=bar_time,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]) if row.get("Volume") is not None else None,
            )
            session.merge(bar)
            rows_upserted += 1

        session.commit()
        logger.info("refresh %s %s: upserted %d rows", symbol, timeframe, rows_upserted)
        return {"symbol": symbol, "timeframe": timeframe, "rows_upserted": rows_upserted, "fetch_start": fetch_start}

    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@celery_worker.task(bind=True, max_retries=3, default_retry_delay=60)
def refresh_symbol_ohlc(
    self: Task,
    symbol: str,
    timeframe: str = "1D",
    start: str | None = None,
) -> dict:
    """
    Celery task: fetch + upsert one symbol.
    Retries up to 3 times on failure (yfinance network errors, etc.).
    """
    try:
        return fetch_and_upsert(symbol=symbol, timeframe=timeframe, start=start)
    except Exception as exc:
        logger.error("refresh_symbol_ohlc %s failed: %s", symbol, exc)
        raise self.retry(exc=exc)


@celery_worker.task(bind=True, max_retries=0)
def refresh_universe(self: Task, universe_key: str, timeframe: str = "1D") -> dict:
    """
    Celery task: fan out one refresh_symbol_ohlc task per symbol in a universe.
    Returns immediately after enqueuing; individual tasks run in parallel.
    """
    from api.market.universes import get_universe_symbols

    try:
        symbols = get_universe_symbols(universe_key)
    except KeyError:
        raise ValueError(f"Unknown universe: {universe_key!r}")

    job = group(
        refresh_symbol_ohlc.s(symbol, timeframe) for symbol in symbols
    )
    result = job.apply_async()
    logger.info("refresh_universe %s: enqueued %d tasks (group %s)", universe_key, len(symbols), result.id)
    return {"universe": universe_key, "symbols_enqueued": len(symbols), "group_id": result.id}


@celery_worker.task(bind=True, max_retries=0)
def refresh_all_tracked_symbols(self: Task, timeframe: str = "1D") -> dict:
    """
    Celery Beat task: daily refresh for all symbols already in DB plus every
    symbol in every universe.  Deduplicates so each symbol is fetched once.
    """
    from api.market.universes import UNIVERSES

    session = SessionLocal()
    try:
        # Symbols already in DB
        db_symbols: list[str] = list(
            session.execute(
                select(OhlcBar.symbol).where(OhlcBar.timeframe == timeframe).distinct()
            ).scalars().all()
        )
    finally:
        session.close()

    # All universe symbols
    universe_symbols: list[str] = [
        sym
        for universe in UNIVERSES.values()
        for sym in universe["symbols"]
    ]

    all_symbols = list(dict.fromkeys(db_symbols + universe_symbols))  # dedup, preserve order

    job = group(
        refresh_symbol_ohlc.s(symbol, timeframe) for symbol in all_symbols
    )
    result = job.apply_async()
    logger.info(
        "refresh_all_tracked_symbols: enqueued %d symbols (group %s)",
        len(all_symbols), result.id,
    )
    return {"symbols_enqueued": len(all_symbols), "group_id": result.id}
