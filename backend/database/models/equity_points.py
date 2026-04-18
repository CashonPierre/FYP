# STL
import uuid
from datetime import datetime

# External
from sqlalchemy import Float, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

# Custom
from database.make_db import Base


class EquityPoint(Base):
  __tablename__ = "equity_points"

  id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  run_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("backtest_runs.id"), nullable=False, index=True
  )
  time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  equity: Mapped[float] = mapped_column(Float, nullable=False)
