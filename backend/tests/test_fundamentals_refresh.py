"""
Unit tests for the fundamentals refresh pipeline.

Uses an in-memory SQLite DB and mocks yfinance — no Docker, no network.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.make_db import Base
from database.models import FundamentalSnapshot


_UNIT_DB_URL = "sqlite:///:memory:"
_unit_engine = create_engine(_UNIT_DB_URL, connect_args={"check_same_thread": False})


@pytest.fixture()
def unit_session():
  Base.metadata.create_all(_unit_engine)
  session = Session(_unit_engine)
  yield session
  session.close()
  Base.metadata.drop_all(_unit_engine)


def _mk_income_df(periods: list[str]) -> pd.DataFrame:
  """Minimal quarterly income statement — revenue, net income, diluted eps."""
  return pd.DataFrame(
    {
      pd.Timestamp(p, tz="UTC"): {
        "Total Revenue": 1_000_000_000.0,
        "Net Income": 200_000_000.0,
        "Diluted EPS": 2.50,
      }
      for p in periods
    }
  )


def _mk_balance_df(periods: list[str]) -> pd.DataFrame:
  return pd.DataFrame(
    {
      pd.Timestamp(p, tz="UTC"): {
        "Total Assets": 10_000_000_000.0,
        "Stockholders Equity": 4_000_000_000.0,
        "Total Debt": 2_000_000_000.0,
        "Ordinary Shares Number": 1_500_000_000.0,
      }
      for p in periods
    }
  )


def _patch_ticker(income_df, balance_df, dividends=None):
  """Return a context manager that patches yfinance.Ticker."""
  mock_ticker = MagicMock()
  mock_ticker.quarterly_income_stmt = income_df
  mock_ticker.quarterly_balance_sheet = balance_df
  mock_ticker.dividends = (
    dividends
    if dividends is not None
    else pd.Series([], dtype=float, index=pd.DatetimeIndex([], tz="UTC"))
  )
  return patch("yfinance.Ticker", return_value=mock_ticker)


# ---------------------------------------------------------------------------
# Happy path: income + balance → populated row
# ---------------------------------------------------------------------------

def test_fetch_fundamentals_happy_path(unit_session):
  from background.tasks.fundamentals_refresh import fetch_fundamentals

  periods = ["2024-03-31", "2023-12-31"]
  with _patch_ticker(_mk_income_df(periods), _mk_balance_df(periods)):
    result = fetch_fundamentals(symbol="AAPL", session=unit_session)

  assert result == {"symbol": "AAPL", "periods_upserted": 2}

  rows = list(
    unit_session.execute(
      select(FundamentalSnapshot).order_by(FundamentalSnapshot.period_end)
    ).scalars().all()
  )
  assert len(rows) == 2

  r = rows[-1]  # most recent
  assert r.symbol == "AAPL"
  assert r.revenue == 1_000_000_000.0
  assert r.net_income == 200_000_000.0
  assert r.diluted_eps == 2.5
  assert r.total_equity == 4_000_000_000.0
  assert r.shares_outstanding == 1_500_000_000
  # Derived: profit margin = net_income / revenue = 0.2
  assert abs(r.profit_margin - 0.2) < 1e-9
  # D/E = 2B / 4B = 0.5
  assert abs(r.debt_to_equity - 0.5) < 1e-9
  # ROE annualised = 4 * net_income / equity = 800M / 4B = 0.2
  assert abs(r.roe - 0.2) < 1e-9


def test_available_from_is_period_end_plus_lag(unit_session):
  from background.tasks.fundamentals_refresh import fetch_fundamentals

  periods = ["2024-03-31"]
  with _patch_ticker(_mk_income_df(periods), _mk_balance_df(periods)):
    fetch_fundamentals(symbol="AAPL", session=unit_session, filing_lag_days=45)

  row = unit_session.execute(
    select(FundamentalSnapshot)
  ).scalar_one()

  expected = datetime(2024, 3, 31, tzinfo=timezone.utc) + timedelta(days=45)
  # SQLite strips tz on read; compare as naive UTC
  got = row.available_from
  if got.tzinfo is None:
    got = got.replace(tzinfo=timezone.utc)
  assert got == expected


# ---------------------------------------------------------------------------
# Balance sheet missing → row still upserted; balance-derived fields are NULL
# ---------------------------------------------------------------------------

def test_fetch_fundamentals_without_balance_sheet(unit_session):
  from background.tasks.fundamentals_refresh import fetch_fundamentals

  periods = ["2024-03-31"]
  with _patch_ticker(_mk_income_df(periods), balance_df=None):
    result = fetch_fundamentals(symbol="AAPL", session=unit_session)

  assert result["periods_upserted"] == 1
  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  assert row.revenue == 1_000_000_000.0
  assert row.total_assets is None
  assert row.total_equity is None
  assert row.debt_to_equity is None
  assert row.roe is None


# ---------------------------------------------------------------------------
# Dividends within the quarter get summed into dividend_per_share
# ---------------------------------------------------------------------------

def test_dividends_aggregated_per_quarter(unit_session):
  from background.tasks.fundamentals_refresh import fetch_fundamentals

  periods = ["2024-03-31"]
  # Two dividend payments in Q1 2024, one outside the window
  div_index = pd.DatetimeIndex(
    ["2024-01-15", "2024-02-15", "2023-12-15"], tz="UTC"
  )
  dividends = pd.Series([0.24, 0.24, 0.23], index=div_index)

  with _patch_ticker(_mk_income_df(periods), _mk_balance_df(periods), dividends):
    fetch_fundamentals(symbol="AAPL", session=unit_session)

  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  # Only the two Q1 dividends count; 2023-12-15 is excluded
  assert abs(row.dividend_per_share - 0.48) < 1e-9


# ---------------------------------------------------------------------------
# Empty income statement → zero rows, no crash
# ---------------------------------------------------------------------------

def test_empty_income_statement_returns_zero(unit_session):
  from background.tasks.fundamentals_refresh import fetch_fundamentals

  with _patch_ticker(pd.DataFrame(), pd.DataFrame()):
    result = fetch_fundamentals(symbol="AAPL", session=unit_session)

  assert result == {"symbol": "AAPL", "periods_upserted": 0}
  assert unit_session.execute(select(FundamentalSnapshot)).first() is None


# ---------------------------------------------------------------------------
# Upsert semantics: re-running on the same period overwrites
# ---------------------------------------------------------------------------

def test_rerun_upserts_not_duplicates(unit_session):
  from background.tasks.fundamentals_refresh import fetch_fundamentals

  periods = ["2024-03-31"]

  with _patch_ticker(_mk_income_df(periods), _mk_balance_df(periods)):
    fetch_fundamentals(symbol="AAPL", session=unit_session)

  # Second run with altered revenue
  income2 = _mk_income_df(periods)
  income2.at["Total Revenue", pd.Timestamp("2024-03-31", tz="UTC")] = 999_999.0

  with _patch_ticker(income2, _mk_balance_df(periods)):
    fetch_fundamentals(symbol="AAPL", session=unit_session)

  rows = list(
    unit_session.execute(select(FundamentalSnapshot)).scalars().all()
  )
  assert len(rows) == 1
  assert rows[0].revenue == 999_999.0


# ---------------------------------------------------------------------------
# Helper functions (_lookup, _safe_div) cover edge cases
# ---------------------------------------------------------------------------

def test_lookup_skips_missing_and_nan():
  from background.tasks.fundamentals_refresh import _lookup

  df = pd.DataFrame(
    {
      pd.Timestamp("2024-03-31", tz="UTC"): {
        "Total Revenue": float("nan"),
        "Revenue": 500.0,  # fallback candidate
      }
    }
  )
  col = pd.Timestamp("2024-03-31", tz="UTC")
  assert _lookup(df, col, ("Total Revenue", "Revenue")) == 500.0
  # None for unknown labels
  assert _lookup(df, col, ("Nonexistent",)) is None
  # Empty df → None
  assert _lookup(pd.DataFrame(), col, ("Total Revenue",)) is None


def test_safe_div_handles_zero_and_none():
  from background.tasks.fundamentals_refresh import _safe_div

  assert _safe_div(10, 2) == 5.0
  assert _safe_div(None, 2) is None
  assert _safe_div(10, None) is None
  assert _safe_div(10, 0) is None
