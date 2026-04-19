"""
Fundamentals refresh — Financial Modeling Prep (FMP) source.

Parallel to `fundamentals_refresh.py` (yfinance) but backed by FMP's REST API.
Same DB target (`fundamental_snapshots`); same {symbol, periods_upserted} return.

Rationale: FMP exposes 30+ years of quarterly statements per symbol in a
single call (yfinance only returns ~5 recent quarters — insufficient for any
backtest window). Filing date comes back on the response, so
`available_from` is the actual SEC filing date rather than a 45-day heuristic.

Endpoints used (FMP "stable" API — v3 is deprecated since 2025-08-31 and
returns 403 "Error Message: Legacy Endpoint" for keys issued after that date):
  GET /stable/income-statement?symbol=SYM&period=quarter&limit=N
  GET /stable/balance-sheet-statement?symbol=SYM&period=quarter&limit=N
  GET /stable/dividends?symbol=SYM

Field-name changes vs. v3 that affect parsing:
  fillingDate (v3 typo)       → filingDate
  epsdiluted                  → epsDiluted
  commonStockSharesOutstanding (balance sheet) — NOT returned on /stable.
  Shares fall back to income statement's weightedAverageShsOutDil /
  weightedAverageShsOut, which is all we need for per-share ratios.

Tasks:
  fetch_fundamentals_fmp(symbol, session=None, limit=120, filing_lag_days=45)
    — Plain function; used by CLI + single-symbol Celery task.

  refresh_symbol_fundamentals_fmp(symbol)
    — Celery task with retry.

  refresh_universe_fundamentals_fmp(universe_key)
    — Celery task: fan out across a universe.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from celery import Task, group
from sqlalchemy.dialects.postgresql import insert as pg_insert

from background.celery_app import celery_worker
from configs import get_logger, settings
from database.make_db import SessionLocal
from database.models import FundamentalSnapshot

logger = get_logger()

_FMP_BASE = "https://financialmodelingprep.com/stable"
_HTTP_TIMEOUT = 30.0


def _fmp_get(path: str, **params: Any) -> list[dict]:
  """GET /{path}; returns the decoded JSON (always a list for these endpoints).

  Raises httpx.HTTPStatusError on 4xx/5xx so the caller can decide whether to
  retry or skip the symbol. FMP sometimes returns {"Error Message": "..."}
  with a 200 status on quota / auth failures — we surface those as RuntimeError
  so Celery retries engage.
  """
  api_key = settings.fmp_api_key
  if not api_key:
    raise RuntimeError(
      "FMP_API_KEY is not set — fundamentals fetch requires an API key"
    )

  url = f"{_FMP_BASE}{path}"
  all_params = {"apikey": api_key, **params}
  r = httpx.get(url, params=all_params, timeout=_HTTP_TIMEOUT)
  r.raise_for_status()
  data = r.json()
  if isinstance(data, dict) and "Error Message" in data:
    raise RuntimeError(f"FMP error for {path}: {data['Error Message']}")
  if not isinstance(data, list):
    return []
  return data


def _parse_date(s: str | None) -> datetime | None:
  """Parse 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' into a UTC-aware datetime."""
  if not s:
    return None
  try:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
  except ValueError:
    try:
      dt = datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
      return None
  if dt.tzinfo is None:
    dt = dt.replace(tzinfo=timezone.utc)
  return dt


def _safe_float(v: Any) -> float | None:
  if v is None:
    return None
  try:
    return float(v)
  except (TypeError, ValueError):
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


def fetch_fundamentals_fmp(
  symbol: str,
  session: Any = None,
  limit: int = 120,
  filing_lag_days: int = 45,
) -> dict:
  """Fetch quarterly fundamentals for `symbol` from FMP and upsert into DB.

  Parameters
  ----------
  symbol : str
  session : SQLAlchemy Session, optional — opened + closed internally when None.
  limit : int — max quarters per endpoint (FMP caps around 120 = 30 years).
  filing_lag_days : int — fallback for `available_from` when FMP's
      `filingDate` field is absent (rare for US listings).
  """
  own_session = session is None
  if own_session:
    session = SessionLocal()

  try:
    income = _fmp_get(
      "/income-statement", symbol=symbol, period="quarter", limit=limit,
    )
    balance = _fmp_get(
      "/balance-sheet-statement", symbol=symbol, period="quarter", limit=limit,
    )
    div_resp = _fmp_get("/dividends", symbol=symbol)

    balance_by_date: dict[str, dict] = {
      (r.get("date") or "")[:10]: r for r in balance
    }
    # /stable/dividends returns a flat list of {date, dividend, adjDividend,...}.
    # We keep the dict-with-"historical" fallback in case FMP ever wraps the
    # shape again (the v3 endpoint used to).
    if isinstance(div_resp, list):
      dividends = div_resp
    elif isinstance(div_resp, dict):
      dividends = div_resp.get("historical") or []
    else:
      dividends = []

    div_rows = sorted(
      [
        {
          "date": _parse_date((d.get("date") or "")[:10]),
          "amount": _safe_float(d.get("dividend")),
        }
        for d in dividends
      ],
      key=lambda d: d["date"] or datetime.min.replace(tzinfo=timezone.utc),
    )

    if not income:
      logger.warning("fundamentals(fmp) %s: no income statement data", symbol)
      return {"symbol": symbol, "periods_upserted": 0}

    dialect = session.connection().dialect.name
    upserted = 0

    for inc in income:
      period_end = _parse_date((inc.get("date") or "")[:10])
      if period_end is None:
        continue

      # Prefer FMP's reported filing date over our filing_lag heuristic when
      # present. /stable uses `filingDate`; we accept the v3 typo `fillingDate`
      # as a fallback in case a caller pins the legacy endpoint.
      filing_date = _parse_date(
        inc.get("filingDate") or inc.get("fillingDate")
      )
      available_from = filing_date or (
        period_end + timedelta(days=filing_lag_days)
      )

      revenue = _safe_float(inc.get("revenue"))
      net_income = _safe_float(inc.get("netIncome"))
      # /stable uses camelCase `epsDiluted`; keep v3 `epsdiluted` as fallback.
      diluted_eps = _safe_float(
        inc.get("epsDiluted") or inc.get("epsdiluted") or inc.get("eps")
      )

      bs = balance_by_date.get(period_end.strftime("%Y-%m-%d"), {})
      total_assets = _safe_float(bs.get("totalAssets"))
      total_equity = _safe_float(
        bs.get("totalStockholdersEquity") or bs.get("totalEquity")
      )
      total_debt = _safe_float(
        bs.get("totalDebt")
        or (
          (_safe_float(bs.get("shortTermDebt")) or 0)
          + (_safe_float(bs.get("longTermDebt")) or 0)
          if bs else None
        )
      )
      # /stable balance sheet no longer returns commonStockSharesOutstanding,
      # so we rely on weighted-avg diluted / basic from the income statement.
      shares_raw = _safe_float(
        bs.get("commonStockSharesOutstanding")
        or inc.get("weightedAverageShsOutDil")
        or inc.get("weightedAverageShsOut")
      )
      shares_outstanding = int(shares_raw) if shares_raw is not None else None

      # Dividends inside the quarter ending at `period_end`. ~92d window
      # captures a full fiscal quarter without bleeding into the next one.
      q_start = period_end - timedelta(days=92)
      dps: float | None = None
      in_q = [
        d["amount"] for d in div_rows
        if d["date"] is not None
        and q_start < d["date"] <= period_end
        and d["amount"] is not None
      ]
      if in_q:
        dps = float(sum(in_q))

      # Annualise ROE from a single quarter's net income.
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
    logger.info("fundamentals(fmp) %s: upserted %d periods", symbol, upserted)
    return {"symbol": symbol, "periods_upserted": upserted}

  except Exception:
    session.rollback()
    raise
  finally:
    if own_session:
      session.close()


# ---------------------------------------------------------------------------
# Celery tasks (FMP variant)
# ---------------------------------------------------------------------------

@celery_worker.task(bind=True, max_retries=3, default_retry_delay=120)
def refresh_symbol_fundamentals_fmp(self: Task, symbol: str) -> dict:
  try:
    return fetch_fundamentals_fmp(symbol=symbol)
  except Exception as exc:
    logger.error("refresh_symbol_fundamentals_fmp %s failed: %s", symbol, exc)
    raise self.retry(exc=exc)


@celery_worker.task(bind=True, max_retries=0)
def refresh_universe_fundamentals_fmp(self: Task, universe_key: str) -> dict:
  from api.market.universes import get_universe_symbols

  try:
    symbols = get_universe_symbols(universe_key)
  except KeyError:
    raise ValueError(f"Unknown universe: {universe_key!r}")

  job = group(refresh_symbol_fundamentals_fmp.s(s) for s in symbols)
  result = job.apply_async()
  logger.info(
    "refresh_universe_fundamentals_fmp %s: enqueued %d tasks (group %s)",
    universe_key, len(symbols), result.id,
  )
  return {
    "universe": universe_key,
    "symbols_enqueued": len(symbols),
    "group_id": result.id,
  }
