"""
BYOD (bring-your-own-data) dataset endpoints.

Users upload OHLCV CSVs that become logical `UserDataset` rows plus bulk-inserted
`UserOhlcBar` rows.  Strategies backtest against uploaded datasets by passing
`settings.dataset_id` instead of a preset `symbol`.

CSV format expected from the client (documented in frontend):
  header row (required, case-insensitive): date, open, high, low, close [, volume]
  date: ISO 8601 (YYYY-MM-DD or YYYY-MM-DD[ T]HH:MM[:SS][Z])
  limits: 10 MB file size, 100 000 rows per upload
  rejects rows with: missing OHLC, invalid date, OHLC inconsistency
  (high < max(open,close) or low > min(open,close)), or duplicate timestamps.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.auth.dependencies import get_current_user
from api.auth.repositories import get_user_by_email
from api.auth.schemas import CurrentUser
from database.make_db import get_session
from database.models import User, UserDataset, UserOhlcBar

dataset_router = APIRouter(prefix="/user/datasets", tags=["User datasets"])


# ---------------------------------------------------------------------------
# Limits + allowed timeframes
# ---------------------------------------------------------------------------

MAX_FILE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_ROWS = 100_000
ALLOWED_TIMEFRAMES = frozenset({"1min", "5min", "15min", "30min", "1H", "4H", "1D", "1W", "1M"})


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DatasetSummary(BaseModel):
  id: uuid.UUID
  name: str
  symbol: str
  timeframe: str
  rows_count: int
  first_bar: datetime | None = None
  last_bar: datetime | None = None
  created_at: datetime


class RejectedRow(BaseModel):
  row: int           # 1-based row number within the CSV body (header is row 0)
  reason: str


class UploadResult(BaseModel):
  dataset: DatasetSummary
  rows_inserted: int
  rejected_rows: list[RejectedRow] = []


class PreviewBar(BaseModel):
  time: datetime
  open: float
  high: float
  low: float
  close: float
  volume: int | None = None


# ---------------------------------------------------------------------------
# CSV parsing + validation
# ---------------------------------------------------------------------------

def _parse_csv(content: bytes) -> tuple[list[dict], list[RejectedRow]]:
  """
  Parse a CSV blob into a list of valid row dicts and a list of rejection records.

  Returns
  -------
  (clean_rows, rejected_rows)
    clean_rows is already deduplicated on `time` (last wins) and sorted ascending.
    rejected_rows gives the original 1-based row number plus the reason so the UI
    can surface actionable error messages.
  """
  import pandas as pd

  try:
    df = pd.read_csv(io.BytesIO(content))
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"Could not parse CSV: {e}",
    )

  if len(df) == 0:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV contains no data rows")
  if len(df) > MAX_ROWS:
    raise HTTPException(
      status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
      f"CSV exceeds {MAX_ROWS} rows (got {len(df)})",
    )

  df.columns = [c.strip().lower() for c in df.columns]

  required = {"date", "open", "high", "low", "close"}
  missing = required - set(df.columns)
  if missing:
    raise HTTPException(
      status.HTTP_400_BAD_REQUEST,
      f"Missing required columns: {sorted(missing)}. Required: date, open, high, low, close",
    )

  # Coerce dtypes up-front so validation is vectorised.
  parsed_time = pd.to_datetime(df["date"], errors="coerce", utc=True)
  for col in ("open", "high", "low", "close"):
    df[col] = pd.to_numeric(df[col], errors="coerce")
  if "volume" in df.columns:
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

  rejected: list[RejectedRow] = []
  clean: list[dict] = []
  seen: set[datetime] = set()

  for i, row in df.iterrows():
    csv_row = int(i) + 2   # +2: 0-based pandas index, +1 for header row
    t = parsed_time.iloc[int(i)]
    if pd.isna(t):
      rejected.append(RejectedRow(row=csv_row, reason="invalid date"))
      continue
    bar_time = t.to_pydatetime()
    if bar_time.tzinfo is None:
      bar_time = bar_time.replace(tzinfo=timezone.utc)

    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    if any(pd.isna(v) for v in (o, h, l, c)):
      rejected.append(RejectedRow(row=csv_row, reason="missing OHLC value"))
      continue
    if h < max(o, c) or l > min(o, c):
      rejected.append(
        RejectedRow(
          row=csv_row,
          reason=f"OHLC inconsistent (high={h}, low={l}, open={o}, close={c})",
        )
      )
      continue

    if bar_time in seen:
      rejected.append(RejectedRow(row=csv_row, reason="duplicate timestamp"))
      continue
    seen.add(bar_time)

    vol = row["volume"] if "volume" in df.columns else None
    clean.append(
      {
        "time": bar_time,
        "open": float(o),
        "high": float(h),
        "low": float(l),
        "close": float(c),
        "volume": int(vol) if not pd.isna(vol) else None,
      }
    )

  if not clean:
    raise HTTPException(
      status.HTTP_400_BAD_REQUEST,
      "No valid rows found. Check the CSV format and try again.",
    )

  clean.sort(key=lambda r: r["time"])
  return clean, rejected


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _resolve_user(session: Session, current: CurrentUser) -> User:
  user = get_user_by_email(session=session, email=current.email)
  if not user:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
  return user


@dataset_router.post("/upload", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
  name: str = Form(..., min_length=1, max_length=64),
  symbol: str = Form(..., min_length=1, max_length=32),
  timeframe: str = Form(...),
  file: UploadFile = File(...),
  current: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> UploadResult:
  if timeframe not in ALLOWED_TIMEFRAMES:
    raise HTTPException(
      status.HTTP_400_BAD_REQUEST,
      f"Unsupported timeframe {timeframe!r}. Allowed: {sorted(ALLOWED_TIMEFRAMES)}",
    )

  content = await file.read()
  if len(content) == 0:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
  if len(content) > MAX_FILE_BYTES:
    raise HTTPException(
      status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
      f"File exceeds {MAX_FILE_BYTES // (1024*1024)} MB",
    )

  user = _resolve_user(session, current)

  clean, rejected = _parse_csv(content)

  existing = session.execute(
    select(UserDataset).where(UserDataset.user_id == user.id, UserDataset.name == name.strip())
  ).scalar_one_or_none()
  if existing:
    raise HTTPException(
      status.HTTP_409_CONFLICT,
      f"Dataset named {name!r} already exists. Pick another name or delete the old one first.",
    )

  dataset = UserDataset(
    user_id=user.id,
    name=name.strip(),
    symbol=symbol.strip().upper(),
    timeframe=timeframe,
    rows_count=len(clean),
    first_bar=clean[0]["time"],
    last_bar=clean[-1]["time"],
  )
  session.add(dataset)
  session.flush()   # assigns dataset.id without committing

  session.bulk_insert_mappings(
    UserOhlcBar,
    [{"dataset_id": dataset.id, **row} for row in clean],
  )
  session.commit()

  return UploadResult(
    dataset=_summarize(dataset),
    rows_inserted=len(clean),
    rejected_rows=rejected[:20],
  )


@dataset_router.get("", response_model=list[DatasetSummary])
def list_datasets(
  current: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> list[DatasetSummary]:
  user = _resolve_user(session, current)
  rows = session.execute(
    select(UserDataset)
    .where(UserDataset.user_id == user.id)
    .order_by(UserDataset.created_at.desc())
  ).scalars().all()
  return [_summarize(r) for r in rows]


@dataset_router.get("/{dataset_id}/preview", response_model=list[PreviewBar])
def preview_dataset(
  dataset_id: uuid.UUID,
  limit: int = 100,
  current: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> list[PreviewBar]:
  user = _resolve_user(session, current)
  dataset = session.get(UserDataset, dataset_id)
  if not dataset or dataset.user_id != user.id:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")

  limit = max(1, min(limit, 500))
  rows = session.execute(
    select(UserOhlcBar)
    .where(UserOhlcBar.dataset_id == dataset.id)
    .order_by(UserOhlcBar.time)
    .limit(limit)
  ).scalars().all()
  return [
    PreviewBar(time=r.time, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume)
    for r in rows
  ]


@dataset_router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
  dataset_id: uuid.UUID,
  current: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> None:
  user = _resolve_user(session, current)
  dataset = session.get(UserDataset, dataset_id)
  if not dataset or dataset.user_id != user.id:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")

  # Delete bars explicitly — SQLite (used in tests) doesn't enforce
  # ON DELETE CASCADE unless foreign keys are enabled per-connection.
  session.execute(delete(UserOhlcBar).where(UserOhlcBar.dataset_id == dataset.id))
  session.delete(dataset)
  session.commit()


def _summarize(d: UserDataset) -> DatasetSummary:
  return DatasetSummary(
    id=d.id, name=d.name, symbol=d.symbol, timeframe=d.timeframe,
    rows_count=d.rows_count, first_bar=d.first_bar, last_bar=d.last_bar,
    created_at=d.created_at,
  )
