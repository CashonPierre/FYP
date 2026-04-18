import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from database.make_db import Base


class BacktestBatch(Base):
  """
  Parent entity for a multi-asset backtest run.

  One BacktestBatch → N BacktestRun children (one per symbol).
  Single-symbol runs also get a batch (N=1) so the polling API is uniform.

  Status lifecycle:
    queued → running → completed | failed | partial
  'partial' = at least one symbol succeeded and at least one failed.
  """

  __tablename__ = "backtest_batches"

  id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  user_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
  )
  strategy_id: Mapped[uuid.UUID | None] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("strategies.id"), nullable=True
  )
  # queued | running | completed | failed | partial
  status: Mapped[str] = mapped_column(
    String(20), nullable=False, default="queued", index=True
  )
  # JSON-encoded list of symbols, e.g. '["AAPL","MSFT"]'
  symbols_json: Mapped[str] = mapped_column(Text, nullable=False)
  # Full strategy JSON (graph + common settings minus per-symbol overrides)
  settings_json: Mapped[str] = mapped_column(Text, nullable=False)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=datetime.utcnow, nullable=False
  )
  started_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
  )
  ended_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
  )
