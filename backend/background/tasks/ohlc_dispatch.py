"""
OHLC source dispatcher.

Callers (CLI, backtest auto-fetch) should go through `fetch_and_upsert_any`
rather than importing `market_refresh.fetch_and_upsert` directly — that way
`OHLC_SOURCE=fmp|yfinance` consistently selects the backend without every
call site re-implementing the check.
"""

from __future__ import annotations

import os
from typing import Any

from configs import settings


def _resolve_source(explicit: str | None = None) -> str:
  """Pick an OHLC source: explicit arg > OHLC_SOURCE env > settings default."""
  src = explicit or os.environ.get("OHLC_SOURCE") or settings.ohlc_source
  src = src.lower().strip()
  if src not in ("fmp", "yfinance"):
    raise ValueError(
      f"Unknown OHLC source {src!r}; expected 'fmp' or 'yfinance'"
    )
  return src


def fetch_and_upsert_any(
  symbol: str,
  timeframe: str = "1D",
  start: str | None = None,
  end: str | None = None,
  session: Any = None,
  source: str | None = None,
) -> dict:
  """Route to the FMP or yfinance fetcher based on `source` / env / config."""
  src = _resolve_source(source)
  if src == "fmp":
    from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp
    return fetch_and_upsert_fmp(
      symbol=symbol, timeframe=timeframe,
      start=start, end=end, session=session,
    )
  from background.tasks.market_refresh import fetch_and_upsert
  return fetch_and_upsert(
    symbol=symbol, timeframe=timeframe,
    start=start, end=end, session=session,
  )
