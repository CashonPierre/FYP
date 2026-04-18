# STL
import uuid
from datetime import datetime

# External
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

# Custom
from database.make_db import Base


class UserDataset(Base):
  """User-uploaded OHLCV dataset (one logical container per CSV upload)."""
  __tablename__ = "user_datasets"
  __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_datasets_user_name"),)

  id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  user_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
  )
  name: Mapped[str] = mapped_column(String(64), nullable=False)
  symbol: Mapped[str] = mapped_column(String(32), nullable=False)
  timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
  rows_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  first_bar: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  last_bar: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )


class UserOhlcBar(Base):
  """Bars for user-uploaded datasets. Separate hypertable from ohlc_bars."""
  __tablename__ = "user_ohlc_bars"

  dataset_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True),
    ForeignKey("user_datasets.id", ondelete="CASCADE"),
    primary_key=True,
  )
  time: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), primary_key=True, index=True
  )

  open: Mapped[float] = mapped_column(Float, nullable=False)
  high: Mapped[float] = mapped_column(Float, nullable=False)
  low: Mapped[float] = mapped_column(Float, nullable=False)
  close: Mapped[float] = mapped_column(Float, nullable=False)
  volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
