"""
Unit tests for the market data refresh pipeline.

All tests use an in-memory SQLite DB and mock yfinance — no Docker, no network.
Run with: uv run pytest tests/test_market_refresh.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.make_db import Base
from database.models import OhlcBar

# ---------------------------------------------------------------------------
# Isolated in-memory DB for fetch_and_upsert unit tests
# (separate from conftest's test_engine so there's no state bleed)
# ---------------------------------------------------------------------------

_UNIT_DB_URL = "sqlite:///:memory:"
_unit_engine = create_engine(_UNIT_DB_URL, connect_args={"check_same_thread": False})


@pytest.fixture()
def unit_session():
    """Fresh schema + session per test. Dropped after each test."""
    Base.metadata.create_all(_unit_engine)
    session = Session(_unit_engine)
    yield session
    session.close()
    Base.metadata.drop_all(_unit_engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_yf_df(prices: list[float], base_date: str = "2024-01-01") -> pd.DataFrame:
    """Build a minimal yfinance-style DataFrame."""
    dates = pd.date_range(start=base_date, periods=len(prices), freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "Open": prices,
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.99 for p in prices],
            "Close": prices,
            "Volume": [1_000_000] * len(prices),
        },
        index=dates,
    )


def _run_fetch(
    symbol: str,
    timeframe: str = "1D",
    start: str | None = None,
    df: pd.DataFrame | None = None,
    session: Session | None = None,
):
    """Call fetch_and_upsert with a mocked yfinance Ticker."""
    from background.tasks.market_refresh import fetch_and_upsert

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df if df is not None else _make_yf_df([100.0, 101.0, 102.0])

    with patch("yfinance.Ticker", return_value=mock_ticker):
        return fetch_and_upsert(symbol=symbol, timeframe=timeframe, start=start, session=session)


# ---------------------------------------------------------------------------
# Universe registry tests
# ---------------------------------------------------------------------------

class TestUniverses:
    def test_all_universes_have_required_keys(self):
        from api.market.universes import UNIVERSES
        for key, meta in UNIVERSES.items():
            assert "name" in meta, f"{key} missing 'name'"
            assert "description" in meta, f"{key} missing 'description'"
            assert "symbols" in meta, f"{key} missing 'symbols'"
            assert len(meta["symbols"]) > 0, f"{key} has empty symbol list"

    def test_get_universe_symbols_returns_list(self):
        from api.market.universes import get_universe_symbols
        symbols = get_universe_symbols("mag7")
        assert isinstance(symbols, list)
        assert len(symbols) == 7
        assert "AAPL" in symbols
        assert "NVDA" in symbols

    def test_get_universe_symbols_raises_on_unknown(self):
        from api.market.universes import get_universe_symbols
        with pytest.raises(KeyError):
            get_universe_symbols("nonexistent_universe")

    def test_list_universes_returns_all(self):
        from api.market.universes import list_universes, UNIVERSES
        result = list_universes()
        assert set(result.keys()) == set(UNIVERSES.keys())

    def test_crypto_universe_contains_btc(self):
        from api.market.universes import get_universe_symbols
        assert "BTC-USD" in get_universe_symbols("crypto")

    def test_no_duplicate_symbols_within_universe(self):
        from api.market.universes import UNIVERSES
        for key, meta in UNIVERSES.items():
            symbols = meta["symbols"]
            assert len(symbols) == len(set(symbols)), f"{key} has duplicate symbols"


# ---------------------------------------------------------------------------
# fetch_and_upsert — basic behaviour
# ---------------------------------------------------------------------------

class TestFetchAndUpsert:
    def test_inserts_rows_from_yfinance(self, unit_session):
        result = _run_fetch("AAPL", df=_make_yf_df([100.0, 101.0, 102.0]), session=unit_session)
        assert result["rows_upserted"] == 3
        assert result["symbol"] == "AAPL"
        assert result["timeframe"] == "1D"

        rows = unit_session.execute(select(OhlcBar).where(OhlcBar.symbol == "AAPL")).scalars().all()
        assert len(rows) == 3
        closes = sorted(r.close for r in rows)
        assert closes == [100.0, 101.0, 102.0]

    def test_stores_correct_ohlcv(self, unit_session):
        _run_fetch("MSFT", df=_make_yf_df([150.0]), session=unit_session)

        bar = unit_session.execute(select(OhlcBar).where(OhlcBar.symbol == "MSFT")).scalar_one()
        assert bar.close == 150.0
        assert bar.open == 150.0
        assert bar.high == pytest.approx(150.0 * 1.01, rel=1e-6)
        assert bar.low == pytest.approx(150.0 * 0.99, rel=1e-6)
        assert bar.volume == 1_000_000

    def test_empty_dataframe_returns_zero_upserted(self, unit_session):
        result = _run_fetch("EMPTY", df=pd.DataFrame(), session=unit_session)
        assert result["rows_upserted"] == 0

    def test_upsert_updates_existing_row(self, unit_session):
        _run_fetch("AAPL", df=_make_yf_df([100.0], base_date="2024-01-02"), session=unit_session)
        _run_fetch("AAPL", df=_make_yf_df([999.0], base_date="2024-01-02"), session=unit_session)

        rows = unit_session.execute(select(OhlcBar).where(OhlcBar.symbol == "AAPL")).scalars().all()
        assert len(rows) == 1
        assert rows[0].close == 999.0

    def test_different_symbols_stored_separately(self, unit_session):
        _run_fetch("AAPL", df=_make_yf_df([100.0, 101.0]), session=unit_session)
        _run_fetch("MSFT", df=_make_yf_df([200.0, 201.0]), session=unit_session)

        aapl = unit_session.execute(select(OhlcBar).where(OhlcBar.symbol == "AAPL")).scalars().all()
        msft = unit_session.execute(select(OhlcBar).where(OhlcBar.symbol == "MSFT")).scalars().all()
        assert len(aapl) == 2
        assert len(msft) == 2

    def test_respects_explicit_start_date(self, unit_session):
        from background.tasks.market_refresh import fetch_and_upsert

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_df([100.0])

        with patch("yfinance.Ticker", return_value=mock_ticker):
            fetch_and_upsert(symbol="AAPL", timeframe="1D", start="2015-01-01", session=unit_session)

        call_kwargs = mock_ticker.history.call_args[1]
        assert call_kwargs["start"] == "2015-01-01"

    def test_incremental_resumes_from_latest_bar(self, unit_session):
        """After seeding, second call requests only bars after the latest stored bar."""
        from background.tasks.market_refresh import fetch_and_upsert

        # Seed 3 bars
        first_ticker = MagicMock()
        first_ticker.history.return_value = _make_yf_df([100.0, 101.0, 102.0], base_date="2024-01-01")
        with patch("yfinance.Ticker", return_value=first_ticker):
            fetch_and_upsert(symbol="AAPL", timeframe="1D", session=unit_session)

        # Second call — should start from day after last bar
        second_ticker = MagicMock()
        second_ticker.history.return_value = pd.DataFrame()
        with patch("yfinance.Ticker", return_value=second_ticker):
            fetch_and_upsert(symbol="AAPL", timeframe="1D", session=unit_session)

        call_kwargs = second_ticker.history.call_args[1]
        # Latest seeded bar is 2024-01-03 (3rd business day), so next fetch starts 2024-01-04
        assert call_kwargs["start"] > "2024-01-03"

    def test_already_up_to_date_skips_yfinance(self, unit_session):
        """If the latest bar is today, yfinance should not be called at all."""
        from background.tasks.market_refresh import fetch_and_upsert

        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        unit_session.add(OhlcBar(
            symbol="SKIP", timeframe="1D", time=today,
            open=100.0, high=101.0, low=99.0, close=100.0, volume=0,
        ))
        unit_session.commit()

        mock_ticker = MagicMock()
        with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
            result = fetch_and_upsert(symbol="SKIP", timeframe="1D", session=unit_session)

        assert result["rows_upserted"] == 0
        mock_yf.assert_not_called()


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestUniversesEndpoint:
    def test_returns_all_universes(self, client):
        resp = client.get("/market/universes")
        assert resp.status_code == 200
        data = resp.json()
        assert "universes" in data
        keys = {u["key"] for u in data["universes"]}
        assert "mag7" in keys
        assert "crypto" in keys
        assert "dow30" in keys

    def test_mag7_has_correct_count_and_symbols(self, client):
        resp = client.get("/market/universes")
        universes = {u["key"]: u for u in resp.json()["universes"]}
        mag7 = universes["mag7"]
        assert mag7["count"] == 7
        assert "AAPL" in mag7["symbols"]
        assert "NVDA" in mag7["symbols"]


class TestRefreshEndpoint:
    def test_requires_auth(self, client):
        resp = client.post("/market/refresh", json={"symbols": ["AAPL"]})
        assert resp.status_code == 401

    def test_unknown_universe_returns_400(self, auth_client):
        resp = auth_client.post("/market/refresh", json={"universe": "nonexistent"})
        assert resp.status_code == 400
        assert "nonexistent" in resp.json()["detail"]

    def test_empty_payload_returns_400(self, auth_client):
        resp = auth_client.post("/market/refresh", json={})
        assert resp.status_code == 400

    def test_enqueues_one_task_per_symbol(self, auth_client):
        mock_result = MagicMock()
        mock_result.id = "fake-task-id"

        with patch("background.tasks.market_refresh.refresh_symbol_ohlc") as mock_task:
            mock_task.delay.return_value = mock_result
            resp = auth_client.post("/market/refresh", json={"symbols": ["AAPL", "MSFT"]})

        assert resp.status_code == 202
        data = resp.json()
        assert data["enqueued"] == 2
        assert len(data["tasks"]) == 2
        assert {t["symbol"] for t in data["tasks"]} == {"AAPL", "MSFT"}

    def test_deduplicates_symbols(self, auth_client):
        mock_result = MagicMock()
        mock_result.id = "fake-task-id"

        with patch("background.tasks.market_refresh.refresh_symbol_ohlc") as mock_task:
            mock_task.delay.return_value = mock_result
            resp = auth_client.post("/market/refresh", json={"symbols": ["AAPL", "aapl", "AAPL"]})

        assert resp.status_code == 202
        assert resp.json()["enqueued"] == 1

    def test_universe_enqueues_correct_count(self, auth_client):
        from api.market.universes import get_universe_symbols
        expected = len(get_universe_symbols("mag7"))

        mock_result = MagicMock()
        mock_result.id = "fake-task-id"

        with patch("background.tasks.market_refresh.refresh_symbol_ohlc") as mock_task:
            mock_task.delay.return_value = mock_result
            resp = auth_client.post("/market/refresh", json={"universe": "mag7"})

        assert resp.status_code == 202
        assert resp.json()["enqueued"] == expected

    def test_symbols_and_universe_merged_and_deduped(self, auth_client):
        """Explicit symbols + universe — overlap is deduplicated."""
        from api.market.universes import get_universe_symbols
        mag7 = get_universe_symbols("mag7")
        # AAPL is in mag7; passing it explicitly too should not double-count
        extra = "NFLX"
        expected = len(set(mag7) | {extra})

        mock_result = MagicMock()
        mock_result.id = "fake-task-id"

        with patch("background.tasks.market_refresh.refresh_symbol_ohlc") as mock_task:
            mock_task.delay.return_value = mock_result
            resp = auth_client.post(
                "/market/refresh",
                json={"symbols": ["AAPL", extra], "universe": "mag7"},
            )

        assert resp.status_code == 202
        assert resp.json()["enqueued"] == expected
