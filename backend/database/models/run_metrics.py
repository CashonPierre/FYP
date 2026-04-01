# STL
import uuid

# External
from sqlalchemy import Float, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

# Custom
from database.make_db import Base


class RunMetrics(Base):
  __tablename__ = "run_metrics"

  run_id: Mapped[uuid.UUID] = mapped_column(
    Uuid(as_uuid=True), ForeignKey("backtest_runs.id"), primary_key=True
  )
  initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
  final_nav: Mapped[float] = mapped_column(Float, nullable=False)
  total_return: Mapped[float] = mapped_column(Float, nullable=False)
  annualized_return: Mapped[float | None] = mapped_column(Float, nullable=True)
  max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
  volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
  sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
  total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
  fees: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
  slippage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
