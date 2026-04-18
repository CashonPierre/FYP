"""
Tests for /backtests endpoints.
"""
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
