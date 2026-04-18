"""
Tests for /user/datasets endpoints (BYOD feature).

Covers:
  - upload: happy path, auth, size/row limits, bad CSV, OHLC sanity rejection,
    duplicate-timestamp rejection, duplicate-name conflict, timeframe validation
  - list, preview, delete
  - BacktestCreate dataset_id validation (mutual exclusion with symbol/symbols)
"""
import io
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from database.models import UserDataset, UserOhlcBar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _csv(rows: list[str], header: str = "date,open,high,low,close,volume") -> bytes:
  return ("\n".join([header, *rows]) + "\n").encode("utf-8")


def _good_csv(n: int = 3) -> bytes:
  """N valid rows starting at 2020-01-01."""
  rows = []
  for i in range(n):
    day = 1 + i
    rows.append(f"2020-01-{day:02d},100.0,101.0,99.0,100.5,1000")
  return _csv(rows)


def _upload(
  client: TestClient, headers: dict, csv_bytes: bytes,
  *, name: str = "my-ds", symbol: str = "FOO", timeframe: str = "1D",
):
  return client.post(
    "/user/datasets/upload",
    headers=headers,
    data={"name": name, "symbol": symbol, "timeframe": timeframe},
    files={"file": ("bars.csv", csv_bytes, "text/csv")},
  )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_upload_requires_auth(client: TestClient):
  resp = _upload(client, {}, _good_csv())
  assert resp.status_code == 401


def test_list_requires_auth(client: TestClient):
  assert client.get("/user/datasets").status_code == 401


def test_preview_requires_auth(client: TestClient):
  assert client.get(f"/user/datasets/{uuid.uuid4()}/preview").status_code == 401


def test_delete_requires_auth(client: TestClient):
  assert client.delete(f"/user/datasets/{uuid.uuid4()}").status_code == 401


# ---------------------------------------------------------------------------
# Upload: happy path
# ---------------------------------------------------------------------------

def test_upload_happy_path(
  client: TestClient, auth_headers: dict, db_session, verified_user,
):
  resp = _upload(client, auth_headers, _good_csv(3))
  assert resp.status_code == 201, resp.text
  body = resp.json()
  assert body["rows_inserted"] == 3
  assert body["rejected_rows"] == []
  assert body["dataset"]["name"] == "my-ds"
  assert body["dataset"]["symbol"] == "FOO"
  assert body["dataset"]["timeframe"] == "1D"
  assert body["dataset"]["rows_count"] == 3

  # Verify DB side-effects
  dataset_id = uuid.UUID(body["dataset"]["id"])
  bars = db_session.execute(
    select(UserOhlcBar).where(UserOhlcBar.dataset_id == dataset_id)
  ).scalars().all()
  assert len(bars) == 3


def test_upload_symbol_uppercased_name_trimmed(
  client: TestClient, auth_headers: dict,
):
  resp = _upload(
    client, auth_headers, _good_csv(),
    name="  spaced  ", symbol="foo",
  )
  assert resp.status_code == 201
  body = resp.json()
  assert body["dataset"]["name"] == "spaced"
  assert body["dataset"]["symbol"] == "FOO"


def test_upload_without_volume_column(client: TestClient, auth_headers: dict):
  csv = _csv(
    ["2020-01-01,10.0,11.0,9.0,10.5"],
    header="date,open,high,low,close",
  )
  resp = _upload(client, auth_headers, csv)
  assert resp.status_code == 201
  assert resp.json()["rows_inserted"] == 1


# ---------------------------------------------------------------------------
# Upload: validation + rejection
# ---------------------------------------------------------------------------

def test_upload_rejects_empty_file(client: TestClient, auth_headers: dict):
  resp = _upload(client, auth_headers, b"")
  assert resp.status_code == 400
  assert "empty" in resp.json()["detail"].lower()


def test_upload_rejects_missing_columns(client: TestClient, auth_headers: dict):
  csv = _csv(["2020-01-01,10,9,10"], header="date,open,low,close")  # no high
  resp = _upload(client, auth_headers, csv)
  assert resp.status_code == 400
  assert "high" in resp.json()["detail"].lower()


def test_upload_rejects_unknown_timeframe(client: TestClient, auth_headers: dict):
  resp = _upload(client, auth_headers, _good_csv(), timeframe="13min")
  assert resp.status_code == 400
  assert "timeframe" in resp.json()["detail"].lower()


def test_upload_rejects_ohlc_inconsistent_row(
  client: TestClient, auth_headers: dict,
):
  # Valid, then high < max(open,close)
  rows = [
    "2020-01-01,100,101,99,100.5,1000",
    "2020-01-02,100,99,99,100,1000",   # high=99 but close=100 → reject
  ]
  resp = _upload(client, auth_headers, _csv(rows))
  assert resp.status_code == 201
  body = resp.json()
  assert body["rows_inserted"] == 1
  assert len(body["rejected_rows"]) == 1
  # csv row numbering: header=1, first data row=2 → second data row = 3
  assert body["rejected_rows"][0]["row"] == 3
  assert "OHLC inconsistent" in body["rejected_rows"][0]["reason"]


def test_upload_rejects_duplicate_timestamps(
  client: TestClient, auth_headers: dict,
):
  rows = [
    "2020-01-01,100,101,99,100.5,1000",
    "2020-01-01,100,101,99,100.5,1000",   # duplicate
    "2020-01-02,100,101,99,100.5,1000",
  ]
  resp = _upload(client, auth_headers, _csv(rows))
  assert resp.status_code == 201
  body = resp.json()
  assert body["rows_inserted"] == 2
  assert len(body["rejected_rows"]) == 1
  assert body["rejected_rows"][0]["reason"] == "duplicate timestamp"


def test_upload_rejects_invalid_date(client: TestClient, auth_headers: dict):
  rows = [
    "2020-01-01,100,101,99,100.5,1000",
    "notadate,100,101,99,100.5,1000",
  ]
  resp = _upload(client, auth_headers, _csv(rows))
  assert resp.status_code == 201
  body = resp.json()
  assert body["rows_inserted"] == 1
  assert body["rejected_rows"][0]["reason"] == "invalid date"


def test_upload_rejects_all_bad_rows(client: TestClient, auth_headers: dict):
  rows = ["notadate,1,2,0,1,1", "also-bad,1,2,0,1,1"]
  resp = _upload(client, auth_headers, _csv(rows))
  assert resp.status_code == 400
  assert "valid rows" in resp.json()["detail"].lower()


def test_upload_duplicate_name_conflicts(
  client: TestClient, auth_headers: dict,
):
  assert _upload(client, auth_headers, _good_csv(), name="same").status_code == 201
  resp = _upload(client, auth_headers, _good_csv(), name="same")
  assert resp.status_code == 409


# ---------------------------------------------------------------------------
# List + preview + delete
# ---------------------------------------------------------------------------

def test_list_datasets_returns_user_uploads(
  client: TestClient, auth_headers: dict,
):
  _upload(client, auth_headers, _good_csv(), name="ds-a")
  _upload(client, auth_headers, _good_csv(), name="ds-b")
  resp = client.get("/user/datasets", headers=auth_headers)
  assert resp.status_code == 200
  names = {row["name"] for row in resp.json()}
  assert names == {"ds-a", "ds-b"}


def test_preview_returns_bars_in_order(
  client: TestClient, auth_headers: dict,
):
  upload = _upload(client, auth_headers, _good_csv(5)).json()
  dataset_id = upload["dataset"]["id"]
  resp = client.get(
    f"/user/datasets/{dataset_id}/preview?limit=3",
    headers=auth_headers,
  )
  assert resp.status_code == 200
  bars = resp.json()
  assert len(bars) == 3
  times = [b["time"] for b in bars]
  assert times == sorted(times)


def test_preview_404_for_other_users_dataset(
  client: TestClient, auth_headers: dict, db_session,
):
  # Insert a dataset owned by a *different* user
  from database.models import User
  import bcrypt
  other = User(
    id=uuid.uuid4(), username="other", email="other@example.com",
    hashed_password=bcrypt.hashpw(b"x", bcrypt.gensalt()).decode(),
    is_verified=True,
  )
  db_session.add(other)
  ds = UserDataset(
    user_id=other.id, name="other-ds", symbol="X", timeframe="1D", rows_count=0,
  )
  db_session.add(ds)
  db_session.flush()

  resp = client.get(f"/user/datasets/{ds.id}/preview", headers=auth_headers)
  assert resp.status_code == 404


def test_delete_removes_dataset_and_bars(
  client: TestClient, auth_headers: dict, db_session,
):
  upload = _upload(client, auth_headers, _good_csv(3)).json()
  dataset_id = uuid.UUID(upload["dataset"]["id"])

  resp = client.delete(
    f"/user/datasets/{dataset_id}", headers=auth_headers,
  )
  assert resp.status_code == 204

  # Follow-up GET returns 404; bars are gone too
  assert client.get(
    f"/user/datasets/{dataset_id}/preview", headers=auth_headers,
  ).status_code == 404
  bars = db_session.execute(
    select(UserOhlcBar).where(UserOhlcBar.dataset_id == dataset_id)
  ).scalars().all()
  assert bars == []


def test_delete_404_for_unknown_dataset(
  client: TestClient, auth_headers: dict,
):
  resp = client.delete(
    f"/user/datasets/{uuid.uuid4()}", headers=auth_headers,
  )
  assert resp.status_code == 404


# ---------------------------------------------------------------------------
# BacktestCreate: dataset_id validation
# ---------------------------------------------------------------------------

def test_backtest_create_accepts_dataset_only():
  from api.backtests.schemas import BacktestCreate
  b = BacktestCreate.model_validate({
    "settings": {"dataset_id": str(uuid.uuid4())},
    "graph": {"nodes": [], "edges": []},
  })
  assert b.settings.dataset_id is not None


def test_backtest_create_rejects_dataset_plus_symbol():
  from pydantic import ValidationError
  from api.backtests.schemas import BacktestCreate
  import pytest
  with pytest.raises(ValidationError) as exc:
    BacktestCreate.model_validate({
      "settings": {"symbol": "AAPL", "dataset_id": str(uuid.uuid4())},
      "graph": {"nodes": [], "edges": []},
    })
  assert "dataset_id cannot be combined" in str(exc.value)


def test_backtest_create_requires_some_symbol_source():
  from pydantic import ValidationError
  from api.backtests.schemas import BacktestCreate
  import pytest
  with pytest.raises(ValidationError):
    BacktestCreate.model_validate({
      "settings": {},
      "graph": {"nodes": [], "edges": []},
    })


# ---------------------------------------------------------------------------
# Submit backtest against an uploaded dataset (end-to-end wiring)
# ---------------------------------------------------------------------------

def test_submit_backtest_against_dataset(
  client: TestClient, auth_headers: dict, db_session,
):
  """Uploading a CSV and submitting a backtest with its dataset_id should
  create one BacktestRun (no batch fan-out) whose settings_json carries the
  dataset_id and inherits the dataset's symbol/timeframe."""
  from unittest.mock import patch, MagicMock
  import json
  from database.models import BacktestRun

  upload = _upload(client, auth_headers, _good_csv(5)).json()
  dataset_id = upload["dataset"]["id"]

  mock_task = MagicMock()
  mock_task.delay = MagicMock(return_value=None)
  with patch("api.backtests.route.run_backtest_task", mock_task, create=True), \
       patch("background.tasks.run_backtest_task", mock_task):
    resp = client.post(
      "/backtests",
      headers=auth_headers,
      json={
        "settings": {
          "dataset_id": dataset_id,
          "initial_capital": 10000.0,
        },
        "graph": {"nodes": [], "edges": []},
      },
    )

  assert resp.status_code == 201, resp.text
  body = resp.json()
  assert body["status"] == "queued"
  assert body["batch_id"] is None

  run = db_session.execute(
    select(BacktestRun).where(BacktestRun.id == uuid.UUID(body["id"]))
  ).scalar_one()
  saved = json.loads(run.settings_json)
  assert saved["settings"]["dataset_id"] == dataset_id
  assert saved["settings"]["symbol"] == "FOO"
  assert saved["settings"]["timeframe"] == "1D"
  mock_task.delay.assert_called_once_with(str(run.id))


def test_submit_backtest_rejects_other_users_dataset(
  client: TestClient, auth_headers: dict, db_session,
):
  """A user cannot run a backtest against someone else's dataset."""
  from database.models import User
  import bcrypt
  other = User(
    id=uuid.uuid4(), username="other2", email="other2@example.com",
    hashed_password=bcrypt.hashpw(b"x", bcrypt.gensalt()).decode(),
    is_verified=True,
  )
  db_session.add(other)
  ds = UserDataset(
    user_id=other.id, name="theirs", symbol="X", timeframe="1D", rows_count=0,
  )
  db_session.add(ds)
  db_session.flush()

  resp = client.post(
    "/backtests",
    headers=auth_headers,
    json={
      "settings": {"dataset_id": str(ds.id)},
      "graph": {"nodes": [], "edges": []},
    },
  )
  assert resp.status_code == 404
