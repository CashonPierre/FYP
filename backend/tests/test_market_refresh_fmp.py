"""
Unit tests for the FMP OHLC fetcher.

Uses in-memory SQLite + mocked httpx — no network, no FMP key needed.
Mirrors the structure of tests/test_fundamentals_refresh_fmp.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.make_db import Base
from database.models import OhlcBar


_DB_URL = "sqlite:///:memory:"
_engine = create_engine(_DB_URL, connect_args={"check_same_thread": False})


@pytest.fixture()
def unit_session():
  Base.metadata.create_all(_engine)
  session = Session(_engine)
  yield session
  session.close()
  Base.metadata.drop_all(_engine)


@pytest.fixture(autouse=True)
def _fmp_key(monkeypatch):
  from configs import settings
  monkeypatch.setattr(settings, "fmp_api_key", "test-key-123", raising=True)


# ---------------------------------------------------------------------------
# Fixture data that mimics FMP /historical-price-full
# ---------------------------------------------------------------------------

_HISTORICAL = {
  "symbol": "AAPL",
  "historical": [
    {"date": "2024-03-31", "open": 170.0, "high": 172.5, "low": 169.1,
     "close": 171.2, "volume": 55_000_000},
    {"date": "2024-03-28", "open": 168.0, "high": 170.0, "low": 167.0,
     "close": 169.5, "volume": 48_000_000},
    {"date": "2024-03-27", "open": 167.0, "high": 169.1, "low": 166.5,
     "close": 168.0, "volume": 42_000_000},
  ],
}


def _mock_httpx_get(body):
  def _side_effect(url, params=None, timeout=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    return resp
  return _side_effect


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_fmp_ohlc_happy_path(unit_session):
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp

  with patch("httpx.get", side_effect=_mock_httpx_get(_HISTORICAL)):
    result = fetch_and_upsert_fmp(
      symbol="AAPL", timeframe="1D",
      start="2024-03-27", end="2024-04-01",
      session=unit_session,
    )

  assert result["symbol"] == "AAPL"
  assert result["timeframe"] == "1D"
  assert result["rows_upserted"] == 3
  assert result["fetch_start"] == "2024-03-27"

  rows = list(
    unit_session.execute(
      select(OhlcBar).order_by(OhlcBar.time)
    ).scalars().all()
  )
  assert len(rows) == 3
  r = rows[-1]  # 2024-03-31
  assert r.symbol == "AAPL"
  assert r.timeframe == "1D"
  assert r.open == 170.0
  assert r.high == 172.5
  assert r.low == 169.1
  assert r.close == 171.2
  assert r.volume == 55_000_000
  # Midnight UTC snap — same convention as the yfinance path
  assert r.time.hour == 0
  assert r.time.minute == 0


# ---------------------------------------------------------------------------
# Empty window
# ---------------------------------------------------------------------------

def test_fmp_empty_historical_returns_zero(unit_session):
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp

  with patch("httpx.get", side_effect=_mock_httpx_get({"symbol": "AAPL", "historical": []})):
    result = fetch_and_upsert_fmp(
      symbol="AAPL", timeframe="1D",
      start="2024-03-27", end="2024-04-01",
      session=unit_session,
    )

  assert result["rows_upserted"] == 0
  assert unit_session.execute(select(OhlcBar)).first() is None


def test_fmp_missing_historical_key_returns_zero(unit_session):
  """FMP sometimes returns {} or {"symbol": X} with no historical key."""
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp

  with patch("httpx.get", side_effect=_mock_httpx_get({"symbol": "AAPL"})):
    result = fetch_and_upsert_fmp(
      symbol="AAPL", timeframe="1D",
      start="2024-03-27", end="2024-04-01",
      session=unit_session,
    )

  assert result["rows_upserted"] == 0


# ---------------------------------------------------------------------------
# Error surfacing
# ---------------------------------------------------------------------------

def test_fmp_error_message_surfaces_as_exception(unit_session):
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp

  def _side_effect(url, params=None, timeout=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"Error Message": "Rate limit exceeded"}
    resp.raise_for_status = MagicMock()
    return resp

  with patch("httpx.get", side_effect=_side_effect):
    with pytest.raises(RuntimeError, match="Rate limit exceeded"):
      fetch_and_upsert_fmp(
        symbol="AAPL", timeframe="1D",
        start="2024-03-27", end="2024-04-01",
        session=unit_session,
      )


def test_fmp_missing_api_key_raises(unit_session, monkeypatch):
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp
  from configs import settings

  monkeypatch.setattr(settings, "fmp_api_key", "", raising=True)

  with pytest.raises(RuntimeError, match="FMP_API_KEY"):
    fetch_and_upsert_fmp(
      symbol="AAPL", timeframe="1D",
      start="2024-03-27", end="2024-04-01",
      session=unit_session,
    )


# ---------------------------------------------------------------------------
# Idempotent upsert — a rerun must not create duplicates
# ---------------------------------------------------------------------------

def test_fmp_rerun_upserts_not_duplicates(unit_session):
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp

  with patch("httpx.get", side_effect=_mock_httpx_get(_HISTORICAL)):
    fetch_and_upsert_fmp(
      symbol="AAPL", timeframe="1D",
      start="2024-03-27", end="2024-04-01",
      session=unit_session,
    )

  # Second run with one mutated close price
  mutated = {
    "symbol": "AAPL",
    "historical": [
      {**_HISTORICAL["historical"][0], "close": 999.99},
      *_HISTORICAL["historical"][1:],
    ],
  }
  with patch("httpx.get", side_effect=_mock_httpx_get(mutated)):
    fetch_and_upsert_fmp(
      symbol="AAPL", timeframe="1D",
      start="2024-03-27", end="2024-04-01",
      session=unit_session,
    )

  rows = list(
    unit_session.execute(
      select(OhlcBar).order_by(OhlcBar.time)
    ).scalars().all()
  )
  assert len(rows) == 3
  assert rows[-1].close == 999.99


# ---------------------------------------------------------------------------
# Unsupported timeframes — raise explicitly (callers can fall back)
# ---------------------------------------------------------------------------

def test_fmp_rejects_weekly_and_monthly(unit_session):
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp

  for tf in ("1W", "1M"):
    with pytest.raises(ValueError, match="1D"):
      fetch_and_upsert_fmp(
        symbol="AAPL", timeframe=tf,
        session=unit_session,
      )


# ---------------------------------------------------------------------------
# Resume: no explicit start AND DB already has bars → fetch_start = last+1d
# ---------------------------------------------------------------------------

def test_fmp_resume_from_latest_bar(unit_session):
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp

  # Seed one bar so the fetcher resumes the next day
  unit_session.add(OhlcBar(
    symbol="AAPL", timeframe="1D",
    time=datetime(2024, 3, 27, tzinfo=timezone.utc),
    open=100.0, high=101.0, low=99.0, close=100.5, volume=1000,
  ))
  unit_session.commit()

  captured = {}

  def _capture(url, params=None, timeout=None):
    captured["params"] = params
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = _HISTORICAL
    resp.raise_for_status = MagicMock()
    return resp

  with patch("httpx.get", side_effect=_capture):
    fetch_and_upsert_fmp(
      symbol="AAPL", timeframe="1D",
      end="2024-04-01", session=unit_session,
    )

  # `from` param should be 2024-03-28 (latest + 1d), not the default 2010
  assert captured["params"]["from"] == "2024-03-28"


# ---------------------------------------------------------------------------
# Skip: start >= end → zero calls, zero rows
# ---------------------------------------------------------------------------

def test_fmp_noop_when_window_is_empty(unit_session):
  from background.tasks.market_refresh_fmp import fetch_and_upsert_fmp

  with patch("httpx.get") as mock_get:
    result = fetch_and_upsert_fmp(
      symbol="AAPL", timeframe="1D",
      start="2024-04-01", end="2024-04-01",
      session=unit_session,
    )

  mock_get.assert_not_called()
  assert result["rows_upserted"] == 0


# ---------------------------------------------------------------------------
# Dispatch helper — respects --source / OHLC_SOURCE / settings.ohlc_source
# ---------------------------------------------------------------------------

def test_dispatch_routes_to_fmp_by_default(unit_session, monkeypatch):
  from background.tasks import ohlc_dispatch

  calls = {"fmp": 0, "yf": 0}

  def _fake_fmp(**kwargs):
    calls["fmp"] += 1
    return {"symbol": kwargs["symbol"], "timeframe": kwargs["timeframe"],
            "rows_upserted": 0, "fetch_start": "x"}

  def _fake_yf(**kwargs):
    calls["yf"] += 1
    return {"symbol": kwargs["symbol"], "timeframe": kwargs["timeframe"],
            "rows_upserted": 0, "fetch_start": "x"}

  monkeypatch.setattr(
    "background.tasks.market_refresh_fmp.fetch_and_upsert_fmp", _fake_fmp,
  )
  monkeypatch.setattr(
    "background.tasks.market_refresh.fetch_and_upsert", _fake_yf,
  )
  monkeypatch.delenv("OHLC_SOURCE", raising=False)
  from configs import settings
  monkeypatch.setattr(settings, "ohlc_source", "fmp", raising=True)

  ohlc_dispatch.fetch_and_upsert_any(symbol="AAPL", session=unit_session)
  assert calls == {"fmp": 1, "yf": 0}


def test_dispatch_explicit_source_overrides_env(unit_session, monkeypatch):
  from background.tasks import ohlc_dispatch

  calls = {"fmp": 0, "yf": 0}
  monkeypatch.setattr(
    "background.tasks.market_refresh_fmp.fetch_and_upsert_fmp",
    lambda **k: calls.__setitem__("fmp", calls["fmp"] + 1) or {},
  )
  monkeypatch.setattr(
    "background.tasks.market_refresh.fetch_and_upsert",
    lambda **k: calls.__setitem__("yf", calls["yf"] + 1) or {},
  )
  monkeypatch.setenv("OHLC_SOURCE", "fmp")

  ohlc_dispatch.fetch_and_upsert_any(
    symbol="AAPL", session=unit_session, source="yfinance",
  )
  assert calls == {"fmp": 0, "yf": 1}


def test_dispatch_rejects_unknown_source():
  from background.tasks import ohlc_dispatch

  with pytest.raises(ValueError, match="Unknown OHLC source"):
    ohlc_dispatch.fetch_and_upsert_any(symbol="AAPL", source="nasdaq-direct")
