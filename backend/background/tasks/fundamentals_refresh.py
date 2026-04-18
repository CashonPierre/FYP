"""
Fundamentals refresh tasks.

Pulls quarterly financials + balance sheet + dividends from yfinance and
upserts into `fundamental_snapshots`. Point-in-time semantics are enforced
via `available_from = period_end + filing_lag_days` (default 45 days, per
SEC 10-Q window).

Price-dependent ratios (P/E, P/B, dividend yield) are NOT stored — they
need the bar close and are computed at strategy-time.

Entry points:
  fetch_fundamentals(symbol, session=None, filing_lag_days=45)
    — Plain function; also used by CLI.

  refresh_symbol_fundamentals(symbol)
    — Celery task: single symbol, retries on failure.

  refresh_universe_fundamentals(universe_key)
    — Celery task: fans out per symbol in a universe.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import Task, group
from sqlalchemy.dialects.postgresql import insert as pg_insert

from background.celery_app import celery_worker
from configs import get_logger
from database.make_db import SessionLocal
from database.models import FundamentalSnapshot

logger = get_logger()


# Row labels to try, in order. yfinance renames these periodically; keep
# the list close to what the library returns today and fall through.
_REVENUE_KEYS = ("Total Revenue", "Revenue")
_NET_INCOME_KEYS = (
  "Net Income",
  "Net Income Common Stockholders",
  "Net Income From Continuing Operation Net Minority Interest",
)
_DILUTED_EPS_KEYS = ("Diluted EPS", "Basic EPS")
_TOTAL_ASSETS_KEYS = ("Total Assets",)
_TOTAL_EQUITY_KEYS = (
  "Stockholders Equity",
  "Total Equity Gross Minority Interest",
  "Common Stock Equity",
)
_TOTAL_DEBT_KEYS = ("Total Debt", "Long Term Debt And Capital Lease Obligation")
_SHARES_KEYS = ("Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding")


def _lookup(df, column, candidates) -> float | None:
  """Find the first row label in `candidates` that exists in `df.index`;
  return df.at[label, column] cast to float, else None."""
  if df is None or df.empty:
    return None
  for name in candidates:
    if name in df.index:
      try:
        val = df.at[name, column]
      except KeyError:
        continue
      # pd.isna handles both NaN and NaT
      import pandas as pd
      if val is None or pd.isna(val):
        continue
      try:
        return float(val)
      except (TypeError, ValueError):
        continue
  return None


def _safe_div(a: float | None, b: float | None) -> float | None:
  if a is None or b is None:
    return None
  try:
    if float(b) == 0.0:
      return None
    return float(a) / float(b)
  except (TypeError, ValueError):
    return None


def fetch_fundamentals(
  symbol: str,
  session: Any = None,
  filing_lag_days: int = 45,
) -> dict:
  """Fetch quarterly fundamentals for one symbol and upsert into DB.

  Returns {"symbol", "periods_upserted"}.

  yfinance can return partial data (balance sheet missing for newer quarters,
  etc.) — we upsert whatever we can extract and log the rest.
  """
  import pandas as pd
  import yfinance as yf

  own_session = session is None
  if own_session:
    session = SessionLocal()

  try:
    ticker = yf.Ticker(symbol)
    # `quarterly_income_stmt` is the modern yfinance name;
    # `quarterly_financials` is the legacy alias.
    income = getattr(ticker, "quarterly_income_stmt", None)
    if income is None or (hasattr(income, "empty") and income.empty):
      income = getattr(ticker, "quarterly_financials", None)
    balance = getattr(ticker, "quarterly_balance_sheet", None)
    dividends = getattr(ticker, "dividends", None)

    if income is None or income.empty:
      logger.warning("fundamentals %s: no income statement data", symbol)
      return {"symbol": symbol, "periods_upserted": 0}

    dialect = session.connection().dialect.name
    upserted = 0

    for period_col in income.columns:
      period_end = pd.Timestamp(period_col).to_pydatetime()
      if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)
      available_from = period_end + timedelta(days=filing_lag_days)

      revenue = _lookup(income, period_col, _REVENUE_KEYS)
      net_income = _lookup(income, period_col, _NET_INCOME_KEYS)
      diluted_eps = _lookup(income, period_col, _DILUTED_EPS_KEYS)

      total_assets = _lookup(balance, period_col, _TOTAL_ASSETS_KEYS) if balance is not None else None
      total_equity = _lookup(balance, period_col, _TOTAL_EQUITY_KEYS) if balance is not None else None
      total_debt = _lookup(balance, period_col, _TOTAL_DEBT_KEYS) if balance is not None else None
      shares_raw = _lookup(balance, period_col, _SHARES_KEYS) if balance is not None else None
      shares_outstanding = int(shares_raw) if shares_raw is not None else None

      # Dividends paid within the quarter ending at period_end.
      dps: float | None = None
      if dividends is not None and len(dividends) > 0:
        q_start = period_end - pd.DateOffset(months=3)
        div_index = dividends.index
        if getattr(div_index, "tz", None) is None:
          div_index = div_index.tz_localize("UTC")
        # Align index tz for comparison
        in_quarter = dividends[
          (div_index > q_start) & (div_index <= period_end)
        ]
        if len(in_quarter) > 0:
          dps = float(in_quarter.sum())

      # Derived scalars — annualise ROE from a single quarter's net income.
      roe = _safe_div(
        (net_income * 4) if net_income is not None else None, total_equity,
      )
      debt_to_equity = _safe_div(total_debt, total_equity)
      profit_margin = _safe_div(net_income, revenue)

      row = dict(
        symbol=symbol,
        period_end=period_end,
        available_from=available_from,
        revenue=revenue,
        net_income=net_income,
        diluted_eps=diluted_eps,
        total_assets=total_assets,
        total_equity=total_equity,
        total_debt=total_debt,
        shares_outstanding=shares_outstanding,
        dividend_per_share=dps,
        roe=roe,
        debt_to_equity=debt_to_equity,
        profit_margin=profit_margin,
      )

      if dialect == "postgresql":
        stmt = pg_insert(FundamentalSnapshot).values(**row)
        stmt = stmt.on_conflict_do_update(
          index_elements=["symbol", "period_end"],
          set_={
            k: stmt.excluded[k]
            for k in row
            if k not in ("symbol", "period_end")
          },
        )
        session.execute(stmt)
      else:
        session.merge(FundamentalSnapshot(**row))

      upserted += 1

    session.commit()
    logger.info("fundamentals %s: upserted %d periods", symbol, upserted)
    return {"symbol": symbol, "periods_upserted": upserted}

  except Exception:
    session.rollback()
    raise
  finally:
    if own_session:
      session.close()


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@celery_worker.task(bind=True, max_retries=3, default_retry_delay=120)
def refresh_symbol_fundamentals(self: Task, symbol: str) -> dict:
  """Celery task: fetch + upsert fundamentals for one symbol."""
  try:
    return fetch_fundamentals(symbol=symbol)
  except Exception as exc:
    logger.error("refresh_symbol_fundamentals %s failed: %s", symbol, exc)
    raise self.retry(exc=exc)


@celery_worker.task(bind=True, max_retries=0)
def refresh_universe_fundamentals(self: Task, universe_key: str) -> dict:
  """Celery task: fan out per-symbol refresh across a universe."""
  from api.market.universes import get_universe_symbols

  try:
    symbols = get_universe_symbols(universe_key)
  except KeyError:
    raise ValueError(f"Unknown universe: {universe_key!r}")

  job = group(refresh_symbol_fundamentals.s(s) for s in symbols)
  result = job.apply_async()
  logger.info(
    "refresh_universe_fundamentals %s: enqueued %d tasks (group %s)",
    universe_key, len(symbols), result.id,
  )
  return {
    "universe": universe_key,
    "symbols_enqueued": len(symbols),
    "group_id": result.id,
  }
