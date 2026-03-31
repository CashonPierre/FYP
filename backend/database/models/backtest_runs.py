# STL
import uuid
from datetime import datetime

# External
from sqlalchemy import String, Text, DateTime, ForeignKey, Uuid, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

# Custom
from database.make_db import Base


class BacktestRun(Base):
  __tablename__ = "backtest_runs"

  id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  user_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
  )
  strategy_id: Mapped[uuid.UUID | None] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("strategies.id"), nullable=True
  )
  # queued | running | completed | failed
  status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
  # JSON: { symbol, timeframe, startDate, endDate, initialCapital, feesBps, slippageBps, graph }
  settings_json: Mapped[str] = mapped_column(Text, nullable=False)
  error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
  started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=datetime.utcnow, nullable=False
  )
