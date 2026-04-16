"""
End-to-end tests for the full backtest pipeline.

Requires:
  - TimescaleDB running:  docker start timescaledb
  - Valkey running:       docker start valkey
  - Celery worker:        uv run celery -A background.celery_app.celery_worker worker --loglevel=info

Run separately from the fast unit/integration tests:
  uv run pytest tests/test_e2e.py -v -m e2e
"""
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.make_db import SessionLocal
from database.models import User


# ── fixtures that use the REAL DB (PostgreSQL), not SQLite ──────────────────

@pytest.fixture(scope="module")
def real_db() -> Session:
  session = SessionLocal()
  yield session
  session.close()


@pytest.fixture(scope="module")
def real_client():
  """TestClient wired to the real PostgreSQL DB (no override)."""
  from server import create_app
  app = create_app()
  with TestClient(app, raise_server_exceptions=False) as c:
    yield c


@pytest.fixture(scope="module")
def e2e_user(real_db: Session):
  """Create (or reuse) a verified test user in the real DB."""
  import bcrypt
  from database.models import User

  email = "e2e_test@example.com"
  existing = real_db.query(User).filter_by(email=email).first()
  if existing:
    return existing

  hashed = bcrypt.hashpw(b"e2etestpass", bcrypt.gensalt()).decode()
  user = User(
    id=uuid.uuid4(),
    username="e2e_testuser",
    email=email,
    hashed_password=hashed,
    is_verified=True,
  )
  real_db.add(user)
  real_db.commit()
  real_db.refresh(user)
  return user


@pytest.fixture(scope="module")
def e2e_token(e2e_user: User) -> str:
  from api.auth.service import create_jwt_token, get_time_tuple
  from api.auth.schemas import JwtToken
  from app_common.enums import PayloadEnum

  now, exp = get_time_tuple(rememberMe=False)
  token_data = JwtToken(
    sub=str(e2e_user.id),
    what=PayloadEnum.LOGIN,
    exp=exp,
    iat=now,
  )
  return create_jwt_token(data=token_data)


@pytest.fixture(scope="module")
def e2e_headers(e2e_token: str) -> dict:
  return {"Authorization": f"Bearer {e2e_token}"}


# ── helpers ─────────────────────────────────────────────────────────────────

BACKTEST_PAYLOAD = {
  "version": 0,
  "settings": {
    "symbol": "AAPL",
    "timeframe": "1D",
    "start_date": "2013-01-01",
    "end_date": "2014-01-01",  # 1 year — fast enough for a test
    "initial_capital": 10000.0,
    "fees_bps": 0.0,
    "slippage_bps": 0.0,
  },
  "graph": {
    "nodes": [{"id": "1", "type": "Data", "position": {"x": 0, "y": 0}, "data": {}}],
    "edges": [],
  },
}

POLL_INTERVAL = 2   # seconds between status checks
TIMEOUT = 60        # seconds before giving up


def wait_for_completion(client: TestClient, run_id: str, headers: dict) -> str:
  """Poll status endpoint until completed/failed or timeout. Returns final status."""
  deadline = time.time() + TIMEOUT
  while time.time() < deadline:
    resp = client.get(f"/backtests/{run_id}/status", headers=headers)
    assert resp.status_code == 200
    current = resp.json()["status"]
    if current in ("completed", "failed"):
      return current
    time.sleep(POLL_INTERVAL)
  return "timeout"


# ── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.e2e
def test_e2e_full_backtest(real_client: TestClient, e2e_user, e2e_headers: dict):
  """Submit a real backtest and wait for it to complete with valid results."""
  # 1. Submit
  resp = real_client.post("/backtests", json=BACKTEST_PAYLOAD, headers=e2e_headers)
  assert resp.status_code == 201, resp.text
  data = resp.json()
  run_id = data["id"]
  assert data["status"] == "queued"

  # 2. Poll until done
  final_status = wait_for_completion(real_client, run_id, e2e_headers)
  assert final_status == "completed", f"Backtest ended with status: {final_status}"

  # 3. Fetch results
  resp = real_client.get(f"/backtests/{run_id}/results", headers=e2e_headers)
  assert resp.status_code == 200
  results = resp.json()

  assert results["status"] == "completed"
  assert results["summary"] is not None

  summary = results["summary"]
  assert summary["initial_capital"] == 10000.0
  assert summary["final_nav"] > 0
  assert isinstance(summary["total_trades"], int)
  assert summary["total_trades"] >= 0
  assert isinstance(summary["total_return"], float)

  # OHLC data should be present (AAPL 2013 data exists in DB)
  assert len(results["series"]["ohlc"]) > 0, "Expected OHLC bars in results"


@pytest.mark.e2e
def test_e2e_backtest_appears_in_list(real_client: TestClient, e2e_user, e2e_headers: dict):
  """After submitting, the run appears in the user's backtest list."""
  # Submit a run
  resp = real_client.post("/backtests", json=BACKTEST_PAYLOAD, headers=e2e_headers)
  assert resp.status_code == 201
  run_id = resp.json()["id"]

  # Check it appears in the list immediately (queued state)
  resp = real_client.get("/backtests", headers=e2e_headers)
  assert resp.status_code == 200
  ids = [item["id"] for item in resp.json()]
  assert run_id in ids


@pytest.mark.e2e
def test_e2e_failed_run_marked_correctly(real_client: TestClient, e2e_user, e2e_headers: dict):
  """A backtest for a symbol with no data should fail gracefully."""
  bad_payload = {
    **BACKTEST_PAYLOAD,
    "settings": {**BACKTEST_PAYLOAD["settings"], "symbol": "DOESNOTEXIST"},
  }
  resp = real_client.post("/backtests", json=bad_payload, headers=e2e_headers)
  assert resp.status_code == 201
  run_id = resp.json()["id"]

  final_status = wait_for_completion(real_client, run_id, e2e_headers)
  assert final_status == "failed"

  # Error message should be recorded
  resp = real_client.get(f"/backtests/{run_id}/status", headers=e2e_headers)
  assert resp.json()["error_message"] is not None
