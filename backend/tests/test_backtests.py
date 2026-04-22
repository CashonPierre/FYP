"""
Tests for /backtests endpoints.
"""
import json
import uuid
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


VALID_PAYLOAD = {
  "version": 0,
  "settings": {
    "symbol": "AAPL",
    "timeframe": "1D",
    "start_date": "2013-01-01",
    "end_date": "2018-01-01",
    "initial_capital": 10000.0,
    "fees_bps": 0.0,
    "slippage_bps": 0.0,
  },
  "graph": {
    "nodes": [{"id": "1", "type": "Data", "position": {"x": 0, "y": 0}, "data": {}}],
    "edges": [],
  },
}

MULTI_SYMBOL_PAYLOAD = {
  "version": 0,
  "settings": {
    "timeframe": "1D",
    "start_date": "2013-01-01",
    "end_date": "2018-01-01",
    "initial_capital": 10000.0,
    "fees_bps": 0.0,
    "slippage_bps": 0.0,
  },
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "graph": {
    "nodes": [{"id": "1", "type": "Data", "position": {"x": 0, "y": 0}, "data": {}}],
    "edges": [],
  },
}


def _mock_batch_task():
  """Return a mock that swallows .delay() calls."""
  mock = MagicMock()
  mock.delay = MagicMock(return_value=None)
  return mock


# ---------------------------------------------------------------------------
# Single-symbol (backward compat)
# ---------------------------------------------------------------------------

def test_submit_backtest_unauthenticated(client: TestClient):
  """No token returns 401."""
  resp = client.post("/backtests", json=VALID_PAYLOAD)
  assert resp.status_code == 401


def test_submit_backtest_success(client: TestClient, verified_user, auth_headers):
  """Authenticated user can submit a backtest, gets id + queued status."""
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    resp = client.post("/backtests", json=VALID_PAYLOAD, headers=auth_headers)

  assert resp.status_code == 201
  data = resp.json()
  assert "id" in data
  assert data["status"] == "queued"
  assert data["batch_id"] is not None


def test_list_backtests_empty(client: TestClient, verified_user, auth_headers):
  """New user has no backtest runs."""
  resp = client.get("/backtests", headers=auth_headers)
  assert resp.status_code == 200
  assert resp.json() == []


def test_list_backtests_after_submit(client: TestClient, verified_user, auth_headers):
  """After submitting, the run appears in the list."""
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    client.post("/backtests", json=VALID_PAYLOAD, headers=auth_headers)

  resp = client.get("/backtests", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()
  assert len(data) == 1
  assert data[0]["symbol"] == "AAPL"
  assert data[0]["status"] == "queued"


def test_get_status_not_found(client: TestClient, auth_headers):
  """Unknown run ID returns 404."""
  fake_id = str(uuid.uuid4())
  resp = client.get(f"/backtests/{fake_id}/status", headers=auth_headers)
  assert resp.status_code == 404


def test_get_status_after_submit(client: TestClient, verified_user, auth_headers):
  """Status endpoint returns correct status for a submitted run."""
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    submit_resp = client.post("/backtests", json=VALID_PAYLOAD, headers=auth_headers)

  run_id = submit_resp.json()["id"]
  resp = client.get(f"/backtests/{run_id}/status", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()
  assert data["id"] == run_id
  assert data["status"] == "queued"


def test_get_results_not_completed(client: TestClient, verified_user, auth_headers):
  """Results for a queued run returns id + status with no summary."""
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    submit_resp = client.post("/backtests", json=VALID_PAYLOAD, headers=auth_headers)

  run_id = submit_resp.json()["id"]
  resp = client.get(f"/backtests/{run_id}/results", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()
  assert data["status"] == "queued"
  assert data["summary"] is None


def test_get_results_not_found(client: TestClient, auth_headers):
  """Unknown run ID on results endpoint returns 404."""
  fake_id = str(uuid.uuid4())
  resp = client.get(f"/backtests/{fake_id}/results", headers=auth_headers)
  assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Multi-symbol batch
# ---------------------------------------------------------------------------

def test_submit_multi_symbol_creates_batch(client: TestClient, verified_user, auth_headers):
  """Multi-symbol submit returns batch_id as id and populates run_ids."""
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    resp = client.post("/backtests", json=MULTI_SYMBOL_PAYLOAD, headers=auth_headers)

  assert resp.status_code == 201
  data = resp.json()
  assert data["batch_id"] is not None
  assert data["id"] == data["batch_id"]   # multi: id = batch_id
  assert len(data["run_ids"]) == 3


def test_submit_multi_symbol_creates_runs_in_list(client: TestClient, verified_user, auth_headers):
  """After multi-symbol submit, one run per symbol appears in the run list."""
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    client.post("/backtests", json=MULTI_SYMBOL_PAYLOAD, headers=auth_headers)

  resp = client.get("/backtests", headers=auth_headers)
  data = resp.json()
  assert len(data) == 3
  symbols_in_list = {item["symbol"] for item in data}
  assert symbols_in_list == {"AAPL", "MSFT", "GOOGL"}
  # All runs share the same batch_id
  batch_ids = {item["batch_id"] for item in data}
  assert len(batch_ids) == 1


def test_get_batch_status_not_found(client: TestClient, auth_headers):
  """Unknown batch ID returns 404."""
  fake_id = str(uuid.uuid4())
  resp = client.get(f"/backtests/batch/{fake_id}", headers=auth_headers)
  assert resp.status_code == 404


def test_get_batch_status_after_submit(client: TestClient, verified_user, auth_headers):
  """Batch status endpoint returns correct structure after multi-symbol submit."""
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    submit_resp = client.post("/backtests", json=MULTI_SYMBOL_PAYLOAD, headers=auth_headers)

  batch_id = submit_resp.json()["batch_id"]
  resp = client.get(f"/backtests/batch/{batch_id}", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()

  assert data["id"] == batch_id
  assert data["status"] == "queued"
  assert set(data["symbols"]) == {"AAPL", "MSFT", "GOOGL"}
  assert len(data["runs"]) == 3
  assert data["aggregate"]["total_symbols"] == 3
  assert data["aggregate"]["queued"] == 3
  assert data["aggregate"]["completed"] == 0


def test_get_batch_status_universe_mode(client: TestClient, verified_user, auth_headers):
  """Batch status for a universe-mode run must serialise even though the run
  has no single `symbol` (its settings carry `symbols` plural).

  Regression: BatchRunSummary.symbol was non-optional, so the endpoint 500'd
  with a Pydantic validation error whenever a universe-mode batch was queried.
  """
  universe_mode_payload = {
    "version": 0,
    "settings": {
      "timeframe": "1D",
      "start_date": "2013-01-01",
      "end_date": "2018-01-01",
      "initial_capital": 10000.0,
      "fees_bps": 0.0,
      "slippage_bps": 0.0,
      "execution_mode": "universe",
    },
    "symbols": ["AAPL", "MSFT"],
    "graph": {
      "nodes": [{"id": "1", "type": "Data", "position": {"x": 0, "y": 0}, "data": {}}],
      "edges": [],
    },
  }
  with patch("api.backtests.route.run_universe_backtest_task", _mock_batch_task()):
    submit_resp = client.post("/backtests", json=universe_mode_payload, headers=auth_headers)

  assert submit_resp.status_code == 201
  batch_id = submit_resp.json()["batch_id"]

  resp = client.get(f"/backtests/batch/{batch_id}", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()
  assert len(data["runs"]) == 1
  assert data["runs"][0]["symbol"] is None  # universe run has no single symbol


def test_list_backtests_universe_mode_run(client: TestClient, verified_user, auth_headers):
  """GET /backtests must serialise a universe-mode run whose settings have
  `symbols` (plural) and no single `symbol`.

  Regression: BacktestListItem.symbol was non-optional, so once a user had
  even one universe-mode run in their history, the list endpoint 500'd.
  """
  universe_mode_payload = {
    "version": 0,
    "settings": {
      "timeframe": "1D",
      "start_date": "2013-01-01",
      "end_date": "2018-01-01",
      "initial_capital": 10000.0,
      "fees_bps": 0.0,
      "slippage_bps": 0.0,
      "execution_mode": "universe",
    },
    "symbols": ["AAPL", "MSFT"],
    "graph": {
      "nodes": [{"id": "1", "type": "Data", "position": {"x": 0, "y": 0}, "data": {}}],
      "edges": [],
    },
  }
  with patch("api.backtests.route.run_universe_backtest_task", _mock_batch_task()):
    client.post("/backtests", json=universe_mode_payload, headers=auth_headers)

  resp = client.get("/backtests", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()
  assert len(data) == 1
  assert data[0]["symbol"] is None


def test_submit_universe_resolves_symbols(client: TestClient, verified_user, auth_headers):
  """Submitting with a universe key fans out to the universe's symbol list."""
  universe_payload = {
    "version": 0,
    "settings": {
      "timeframe": "1D",
      "initial_capital": 10000.0,
      "fees_bps": 0.0,
      "slippage_bps": 0.0,
    },
    "universe": "mag7",
    "graph": {
      "nodes": [{"id": "1", "type": "Data", "position": {"x": 0, "y": 0}, "data": {}}],
      "edges": [],
    },
  }
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    resp = client.post("/backtests", json=universe_payload, headers=auth_headers)

  assert resp.status_code == 201
  data = resp.json()
  assert len(data["run_ids"]) == 7  # mag7 has 7 symbols


def test_submit_invalid_universe_returns_400(client: TestClient, verified_user, auth_headers):
  """Unknown universe key returns HTTP 400."""
  bad_payload = {
    "version": 0,
    "settings": {"timeframe": "1D", "initial_capital": 10000.0, "fees_bps": 0.0, "slippage_bps": 0.0},
    "universe": "nonexistent_universe",
    "graph": {"nodes": [], "edges": []},
  }
  with patch("api.backtests.route.run_backtest_batch_task", _mock_batch_task()):
    resp = client.post("/backtests", json=bad_payload, headers=auth_headers)

  assert resp.status_code == 400


def test_submit_no_symbol_source_returns_422(client: TestClient, verified_user, auth_headers):
  """Payload with no symbol/symbols/universe returns 422 validation error."""
  bad_payload = {
    "version": 0,
    "settings": {"timeframe": "1D", "initial_capital": 10000.0, "fees_bps": 0.0, "slippage_bps": 0.0},
    "graph": {"nodes": [], "edges": []},
  }
  resp = client.post("/backtests", json=bad_payload, headers=auth_headers)
  assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Results payload wiring (Sharpe / Sortino / drawdown / Calmar / metadata)
# ---------------------------------------------------------------------------

def test_results_exposes_full_performance_metrics(
  client: TestClient, verified_user, auth_headers, db_session
):
  """A completed run with seeded RunMetrics returns the full metric set.

  Regression: before Task 3, Sharpe / Sortino / drawdown were always null
  because metrics came from the engine's `TradingMetrics` (which leaves
  them `None`). We now compute them from the equity curve, and this test
  pins that the full set is surfaced through the API.
  """
  from datetime import datetime, timezone

  from database.models import BacktestRun, RunMetrics, Strategy

  strategy = Strategy(
    id=uuid.uuid4(),
    user_id=verified_user.id,
    name="Test DCA Strategy",
    graph_json=json.dumps({"nodes": [], "edges": []}),
  )
  db_session.add(strategy)

  settings_payload = {
    "settings": {
      "symbol": "AAPL",
      "timeframe": "1D",
      "start_date": "2020-01-01",
      "end_date": "2021-01-01",
      "initial_capital": 10000.0,
      "fees_bps": 0.0,
      "slippage_bps": 0.0,
    },
    "graph": {"nodes": [], "edges": []},
  }
  run = BacktestRun(
    id=uuid.uuid4(),
    user_id=verified_user.id,
    strategy_id=strategy.id,
    status="completed",
    settings_json=json.dumps(settings_payload),
    started_at=datetime.now(timezone.utc),
    ended_at=datetime.now(timezone.utc),
  )
  db_session.add(run)
  db_session.flush()

  db_session.add(
    RunMetrics(
      run_id=run.id,
      initial_capital=10000.0,
      final_nav=12500.0,
      total_return=0.25,
      annualized_return=0.18,
      max_drawdown=-0.08,
      volatility=0.15,
      sharpe=1.2,
      sortino=1.65,
      calmar=2.25,
      total_trades=24,
      win_rate=0.62,
      fees=0.0,
      slippage=0.0,
    )
  )
  db_session.flush()

  resp = client.get(f"/backtests/{run.id}/results", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()

  assert data["status"] == "completed"
  assert data["symbol"] == "AAPL"
  assert data["timeframe"] == "1D"
  assert data["start_date"] == "2020-01-01"
  assert data["end_date"] == "2021-01-01"
  assert data["strategy_name"] == "Test DCA Strategy"

  summary = data["summary"]
  assert summary is not None
  # Ratios and drawdown — none of these may silently drop to null.
  assert summary["sharpe"] == 1.2
  assert summary["sortino"] == 1.65
  assert summary["calmar"] == 2.25
  assert summary["max_drawdown"] == -0.08
  assert summary["volatility"] == 0.15
  assert summary["annualized_return"] == 0.18
  assert summary["total_return"] == 0.25
