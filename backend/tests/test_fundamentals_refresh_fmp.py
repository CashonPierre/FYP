"""
Unit tests for the FMP fundamentals fetcher (stable API namespace).

Uses in-memory SQLite + mocked httpx — no network, no FMP key needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.make_db import Base
from database.models import FundamentalSnapshot


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
  """All tests pretend an API key is set, so _fmp_get doesn't bail early."""
  from configs import settings
  monkeypatch.setattr(settings, "fmp_api_key", "test-key-123", raising=True)


# ---------------------------------------------------------------------------
# Fixture data that mimics FMP /stable responses (as of 2026-04)
# ---------------------------------------------------------------------------

_INCOME = [
  {
    "date": "2024-03-31",
    "filingDate": "2024-05-10",
    "revenue": 1_000_000_000,
    "netIncome": 200_000_000,
    "epsDiluted": 2.50,
    "weightedAverageShsOutDil": 1_500_000_000,
  },
  {
    "date": "2023-12-31",
    "filingDate": "2024-02-14",
    "revenue": 900_000_000,
    "netIncome": 180_000_000,
    "epsDiluted": 2.25,
    "weightedAverageShsOutDil": 1_510_000_000,
  },
]

# /stable balance sheet no longer includes commonStockSharesOutstanding — the
# fetcher falls back to income.weightedAverageShsOutDil for shares.
_BALANCE = [
  {
    "date": "2024-03-31",
    "totalAssets": 10_000_000_000,
    "totalStockholdersEquity": 4_000_000_000,
    "totalDebt": 2_000_000_000,
  },
  {
    "date": "2023-12-31",
    "totalAssets": 9_500_000_000,
    "totalStockholdersEquity": 3_800_000_000,
    "totalDebt": 1_900_000_000,
  },
]

_DIVIDENDS = [
  {"date": "2024-02-15", "dividend": 0.24, "adjDividend": 0.24},
  {"date": "2024-01-15", "dividend": 0.24, "adjDividend": 0.24},
  {"date": "2023-12-15", "dividend": 0.23, "adjDividend": 0.23},
]


def _mock_httpx_get(responses: dict[str, list]):
  """Return a side_effect that routes based on URL path substring."""
  def _side_effect(url, params=None, timeout=None):
    for path, body in responses.items():
      if path in url:
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.return_value = body
        resp.raise_for_status = MagicMock()
        return resp
    raise AssertionError(f"unexpected URL: {url}")
  return _side_effect


# ---------------------------------------------------------------------------
# Happy path: income + balance + dividends → rows with derived fields
# ---------------------------------------------------------------------------

def test_fmp_happy_path(unit_session):
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  responses = {
    "/income-statement": _INCOME,
    "/balance-sheet-statement": _BALANCE,
    "/dividends": _DIVIDENDS,
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    result = fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  assert result == {"symbol": "AAPL", "periods_upserted": 2}

  rows = list(
    unit_session.execute(
      select(FundamentalSnapshot).order_by(FundamentalSnapshot.period_end)
    ).scalars().all()
  )
  assert len(rows) == 2

  r = rows[-1]  # 2024-03-31
  assert r.symbol == "AAPL"
  assert r.revenue == 1_000_000_000.0
  assert r.net_income == 200_000_000.0
  assert r.diluted_eps == 2.5
  assert r.total_equity == 4_000_000_000.0
  # Shares fall back to income.weightedAverageShsOutDil under /stable.
  assert r.shares_outstanding == 1_500_000_000
  assert abs(r.profit_margin - 0.2) < 1e-9
  assert abs(r.debt_to_equity - 0.5) < 1e-9
  assert abs(r.roe - 0.2) < 1e-9  # annualised net_income / equity


def test_stable_endpoints_called_with_symbol_query(unit_session):
  """Regression guard: /stable puts symbol in the query string, not the path."""
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  seen: list[tuple[str, dict]] = []

  def _side_effect(url, params=None, timeout=None):
    seen.append((url, dict(params or {})))
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = []
    resp.raise_for_status = MagicMock()
    return resp

  with patch("httpx.get", side_effect=_side_effect):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  assert seen, "fetcher made no HTTP calls"
  paths = [u for u, _ in seen]
  assert all("/stable/" in u for u in paths), paths
  assert any("/stable/income-statement" in u for u in paths), paths
  assert any("/stable/balance-sheet-statement" in u for u in paths), paths
  assert any("/stable/dividends" in u for u in paths), paths
  # Symbol is in the query, never the path — i.e. no /stable/income-statement/AAPL
  assert all("/AAPL" not in u for u in paths), paths
  for _, params in seen:
    assert params.get("symbol") == "AAPL", params


def test_available_from_uses_fmp_filing_date(unit_session):
  """When FMP returns `filingDate`, we use it instead of period+45d."""
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  responses = {
    "/income-statement": [_INCOME[0]],
    "/balance-sheet-statement": [_BALANCE[0]],
    "/dividends": [],
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  expected = datetime(2024, 5, 10, tzinfo=timezone.utc)
  got = row.available_from
  if got.tzinfo is None:
    got = got.replace(tzinfo=timezone.utc)
  assert got == expected


def test_available_from_accepts_legacy_filling_date(unit_session):
  """Back-compat: callers that still see the v3 `fillingDate` typo keep working."""
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  legacy = {
    "date": "2024-03-31",
    "fillingDate": "2024-05-10",  # v3 typo
    "revenue": 100, "netIncome": 10, "epsdiluted": 0.1,
  }
  responses = {
    "/income-statement": [legacy],
    "/balance-sheet-statement": [],
    "/dividends": [],
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  got = row.available_from
  if got.tzinfo is None:
    got = got.replace(tzinfo=timezone.utc)
  assert got == datetime(2024, 5, 10, tzinfo=timezone.utc)


def test_available_from_falls_back_when_filing_date_missing(unit_session):
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  inc_no_filing = [
    {"date": "2024-03-31", "revenue": 100, "netIncome": 10, "epsDiluted": 0.1},
  ]
  responses = {
    "/income-statement": inc_no_filing,
    "/balance-sheet-statement": [],
    "/dividends": [],
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    fetch_fundamentals_fmp(
      symbol="AAPL", session=unit_session, filing_lag_days=30,
    )

  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  expected = datetime(2024, 4, 30, tzinfo=timezone.utc)  # 2024-03-31 + 30d
  got = row.available_from
  if got.tzinfo is None:
    got = got.replace(tzinfo=timezone.utc)
  assert got == expected


def test_dividends_aggregated_per_quarter(unit_session):
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  responses = {
    "/income-statement": [_INCOME[0]],
    "/balance-sheet-statement": [_BALANCE[0]],
    # Two Q1 2024 dividends (Jan + Feb) + one outside (Dec 2023)
    "/dividends": _DIVIDENDS,
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  assert abs(row.dividend_per_share - 0.48) < 1e-9


def test_dividends_legacy_wrapped_shape_still_works(unit_session):
  """Defensive: if FMP wraps dividends in {"historical": [...]} again we
  should still parse them — the v3 endpoint used this shape."""
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  responses = {
    "/income-statement": [_INCOME[0]],
    "/balance-sheet-statement": [_BALANCE[0]],
    "/dividends": {"symbol": "AAPL", "historical": _DIVIDENDS},
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  # _fmp_get coerces non-list responses to [], so wrapped dividends are
  # silently dropped; the snapshot still lands but with NULL dps.
  assert row.dividend_per_share is None


def test_balance_sheet_missing_fields_nullable(unit_session):
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  responses = {
    "/income-statement": [_INCOME[0]],
    "/balance-sheet-statement": [],
    "/dividends": [],
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    result = fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  assert result["periods_upserted"] == 1
  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  assert row.revenue == 1_000_000_000.0
  assert row.total_assets is None
  assert row.total_equity is None
  assert row.roe is None
  assert row.debt_to_equity is None
  # Shares still populated from income fallback even without balance data.
  assert row.shares_outstanding == 1_500_000_000


def test_shares_fallback_from_income_when_balance_omits(unit_session):
  """/stable balance-sheet drops commonStockSharesOutstanding; shares must
  come from income.weightedAverageShsOutDil (falling back to ShsOut)."""
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  inc_only_basic = [
    {
      "date": "2024-03-31",
      "filingDate": "2024-05-10",
      "revenue": 100, "netIncome": 10, "epsDiluted": 0.1,
      # No diluted; should fall back to weightedAverageShsOut.
      "weightedAverageShsOut": 1_200_000_000,
    },
  ]
  responses = {
    "/income-statement": inc_only_basic,
    "/balance-sheet-statement": [_BALANCE[0]],
    "/dividends": [],
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  row = unit_session.execute(select(FundamentalSnapshot)).scalar_one()
  assert row.shares_outstanding == 1_200_000_000


def test_empty_income_returns_zero(unit_session):
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  responses = {
    "/income-statement": [],
    "/balance-sheet-statement": [],
    "/dividends": [],
  }

  with patch("httpx.get", side_effect=_mock_httpx_get(responses)):
    result = fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  assert result == {"symbol": "AAPL", "periods_upserted": 0}
  assert unit_session.execute(select(FundamentalSnapshot)).first() is None


def test_rerun_upserts_not_duplicates(unit_session):
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  responses_first = {
    "/income-statement": [_INCOME[0]],
    "/balance-sheet-statement": [_BALANCE[0]],
    "/dividends": [],
  }
  with patch("httpx.get", side_effect=_mock_httpx_get(responses_first)):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  second = dict(_INCOME[0])
  second["revenue"] = 999_999.0
  responses_second = {
    "/income-statement": [second],
    "/balance-sheet-statement": [_BALANCE[0]],
    "/dividends": [],
  }
  with patch("httpx.get", side_effect=_mock_httpx_get(responses_second)):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)

  rows = list(
    unit_session.execute(select(FundamentalSnapshot)).scalars().all()
  )
  assert len(rows) == 1
  assert rows[0].revenue == 999_999.0


def test_missing_api_key_raises(unit_session, monkeypatch):
  """Re-set the key to empty AFTER the autouse fixture to simulate misconfig."""
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp
  from configs import settings

  monkeypatch.setattr(settings, "fmp_api_key", "", raising=True)

  with pytest.raises(RuntimeError, match="FMP_API_KEY"):
    fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)


def test_fmp_error_message_surfaces_as_exception(unit_session):
  """FMP returns a dict with 'Error Message' on quota/auth issues; we must raise."""
  from background.tasks.fundamentals_refresh_fmp import fetch_fundamentals_fmp

  def _side_effect(url, params=None, timeout=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"Error Message": "Rate limit exceeded"}
    resp.raise_for_status = MagicMock()
    return resp

  with patch("httpx.get", side_effect=_side_effect):
    with pytest.raises(RuntimeError, match="Rate limit exceeded"):
      fetch_fundamentals_fmp(symbol="AAPL", session=unit_session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_safe_div_edges():
  from background.tasks.fundamentals_refresh_fmp import _safe_div
  assert _safe_div(10, 2) == 5.0
  assert _safe_div(None, 2) is None
  assert _safe_div(10, None) is None
  assert _safe_div(10, 0) is None


def test_parse_date_handles_variants():
  from background.tasks.fundamentals_refresh_fmp import _parse_date
  assert _parse_date("2024-03-31") == datetime(2024, 3, 31, tzinfo=timezone.utc)
  assert _parse_date("2024-03-31 18:00:00") is not None
  assert _parse_date("garbage") is None
  assert _parse_date(None) is None
