# STL
import uuid
from datetime import datetime

# External
from sqlalchemy import String, DateTime, Float, Integer, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

# Custom
from database.make_db import Base


class Trade(Base):
  __tablename__ = "trades"

  id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  run_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("backtest_runs.id"), nullable=False, index=True
  )
  time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  symbol: Mapped[str] = mapped_column(String(20), nullable=False)
  side: Mapped[str] = mapped_column(String(4), nullable=False)   # buy | sell
  price: Mapped[float] = mapped_column(Float, nullable=False)
  quantity: Mapped[float] = mapped_column(Float, nullable=False)
  fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
  slippage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
