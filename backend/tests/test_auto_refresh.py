"""
Unit tests for the auto-refresh-before-backtest helper.

Covers the branches of _auto_refresh_if_needed:
  - DB completely missing the symbol → fetch
  - Latest bar is > 1 day behind requested end_date → fetch tail (no force start)
  - Earliest bar is AFTER requested start_date → force fetch from start_date
  - Window already fully covered → skip
  - Timeframe unsupported by the refresh pipeline → skip
  - Fetch failures are swallowed (best-effort)
  - Garbage end_date strings don't raise
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.make_db import Base
from database.models import OhlcBar


_UNIT_DB_URL = "sqlite:///:memory:"
_unit_engine = create_engine(_UNIT_DB_URL, connect_args={"check_same_thread": False})


@pytest.fixture()
def unit_db():
  Base.metadata.create_all(_unit_engine)
  yield _unit_engine
  Base.metadata.drop_all(_unit_engine)


def _seed_bar(engine, symbol: str, timeframe: str, time: datetime) -> None:
  with Session(engine) as s:
    s.add(OhlcBar(
      symbol=symbol, timeframe=timeframe, time=time,
      open=100.0, high=101.0, low=99.0, close=100.5, volume=1_000_000,
    ))
    s.commit()


def _patched(monkeypatch, engine):
  """Point the helper at our test engine and return (helper, fetch_mock)."""
  TestSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
  monkeypatch.setattr(
    "background.tasks.backtest.SessionLocal",
    TestSessionLocal,
  )

  fetch_mock = MagicMock(return_value={"rows_upserted": 10})
  monkeypatch.setattr(
    "background.tasks.market_refresh.fetch_and_upsert",
    fetch_mock,
  )

  from background.tasks.backtest import _auto_refresh_if_needed
  return _auto_refresh_if_needed, fetch_mock


# ---------------------------------------------------------------------------
# No data at all → fetch with force-start if user asked for historical data
# ---------------------------------------------------------------------------

def test_fetches_when_symbol_completely_missing(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)

  helper(symbol="AAPL", timeframe="1D", start_date=None, end_date=None)

  fetch_mock.assert_called_once_with(symbol="AAPL", timeframe="1D", start=None)


def test_fetches_with_force_start_when_symbol_missing_and_start_given(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)

  helper(symbol="AAPL", timeframe="1D", start_date="2015-01-01", end_date="2020-12-31")

  fetch_mock.assert_called_once_with(symbol="AAPL", timeframe="1D", start="2015-01-01")


# ---------------------------------------------------------------------------
# Tail stale → fetch incrementally (no force start)
# ---------------------------------------------------------------------------

def test_fetches_tail_when_latest_is_stale(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)

  old = (datetime.now(timezone.utc) - timedelta(days=30)).replace(
    hour=0, minute=0, second=0, microsecond=0
  )
  _seed_bar(unit_db, "AAPL", "1D", old)

  helper(symbol="AAPL", timeframe="1D", start_date=None, end_date=None)

  fetch_mock.assert_called_once_with(symbol="AAPL", timeframe="1D", start=None)


# ---------------------------------------------------------------------------
# Head missing → force-fetch from start_date
# ---------------------------------------------------------------------------

def test_fetches_head_when_earliest_is_after_requested_start(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)

  # DB has 2018 onward but user wants 2010→2020
  _seed_bar(unit_db, "AAPL", "1D", datetime(2018, 1, 2, tzinfo=timezone.utc))
  _seed_bar(unit_db, "AAPL", "1D", datetime(2020, 12, 31, tzinfo=timezone.utc))

  helper(symbol="AAPL", timeframe="1D", start_date="2010-01-01", end_date="2020-12-31")

  fetch_mock.assert_called_once_with(symbol="AAPL", timeframe="1D", start="2010-01-01")


# ---------------------------------------------------------------------------
# Window fully covered → skip
# ---------------------------------------------------------------------------

def test_skips_when_window_fully_covered(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)

  _seed_bar(unit_db, "AAPL", "1D", datetime(2015, 1, 1, tzinfo=timezone.utc))
  _seed_bar(unit_db, "AAPL", "1D", datetime(2020, 12, 31, tzinfo=timezone.utc))

  helper(symbol="AAPL", timeframe="1D", start_date="2016-01-01", end_date="2020-12-30")

  fetch_mock.assert_not_called()


def test_skips_when_fresh_and_no_start_given(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)

  today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
  _seed_bar(unit_db, "AAPL", "1D", today)

  helper(symbol="AAPL", timeframe="1D", start_date=None, end_date=None)

  fetch_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Unsupported timeframe → skip
# ---------------------------------------------------------------------------

def test_skips_unsupported_timeframe(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)

  helper(symbol="AAPL", timeframe="5m", start_date=None, end_date=None)

  fetch_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Best-effort: fetch failures don't bubble up
# ---------------------------------------------------------------------------

def test_swallows_fetch_errors(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)
  fetch_mock.side_effect = RuntimeError("yfinance down")

  helper(symbol="AAPL", timeframe="1D", start_date=None, end_date=None)

  fetch_mock.assert_called_once()


# ---------------------------------------------------------------------------
# Garbage date strings don't raise
# ---------------------------------------------------------------------------

def test_handles_bad_end_date(unit_db, monkeypatch):
  helper, fetch_mock = _patched(monkeypatch, unit_db)

  helper(symbol="AAPL", timeframe="1D", start_date=None, end_date="not-a-date")

  fetch_mock.assert_called_once()
