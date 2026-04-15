"""
Tests for /backtests endpoints.
"""
import uuid
from unittest.mock import patch

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


def test_submit_backtest_unauthenticated(client: TestClient):
  """No token returns 401."""
  resp = client.post("/backtests", json=VALID_PAYLOAD)
  assert resp.status_code == 401


def test_submit_backtest_success(client: TestClient, verified_user, auth_headers):
  """Authenticated user can submit a backtest, gets id + queued status."""
  with patch("api.backtests.route.run_backtest_task") as mock_task:
    mock_task.delay = lambda run_id: None  # don't actually run Celery
    resp = client.post("/backtests", json=VALID_PAYLOAD, headers=auth_headers)

  assert resp.status_code == 201
  data = resp.json()
  assert "id" in data
  assert data["status"] == "queued"


def test_list_backtests_empty(client: TestClient, verified_user, auth_headers):
  """New user has no backtest runs."""
  resp = client.get("/backtests", headers=auth_headers)
  assert resp.status_code == 200
  assert resp.json() == []


def test_list_backtests_after_submit(client: TestClient, verified_user, auth_headers):
  """After submitting, the run appears in the list."""
  with patch("api.backtests.route.run_backtest_task") as mock_task:
    mock_task.delay = lambda run_id: None
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
  with patch("api.backtests.route.run_backtest_task") as mock_task:
    mock_task.delay = lambda run_id: None
    submit_resp = client.post("/backtests", json=VALID_PAYLOAD, headers=auth_headers)

  run_id = submit_resp.json()["id"]
  resp = client.get(f"/backtests/{run_id}/status", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()
  assert data["id"] == run_id
  assert data["status"] == "queued"


def test_get_results_not_completed(client: TestClient, verified_user, auth_headers):
  """Results for a queued run returns id + status with no summary."""
  with patch("api.backtests.route.run_backtest_task") as mock_task:
    mock_task.delay = lambda run_id: None
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
