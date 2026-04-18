# External
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

# Custom
from database.make_db import Base


class FundamentalSnapshot(Base):
  """
  Company fundamentals for a single reporting period.

  Point-in-time: `available_from` = period_end + 45 days approximates the SEC
  10-Q filing window. Strategies must filter by `available_from <= bar_time`
  to avoid look-ahead bias.

  Price-dependent ratios (P/E, P/B, dividend yield) are NOT stored here —
  they need the bar's close price and are computed at strategy-time.
  """
  __tablename__ = "fundamental_snapshots"

  symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
  period_end: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), primary_key=True
  )
  available_from: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, index=True
  )

  # --- Raw metrics from yfinance quarterly financials ---
  revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
  net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
  diluted_eps: Mapped[float | None] = mapped_column(Float, nullable=True)

  # --- Raw metrics from yfinance quarterly balance sheet ---
  total_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
  total_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
  total_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
  shares_outstanding: Mapped[int | None] = mapped_column(
    BigInteger, nullable=True
  )

  # --- Dividends paid in the quarter (per share) ---
  dividend_per_share: Mapped[float | None] = mapped_column(Float, nullable=True)

  # --- Derived scalars (computed once at ingest) ---
  roe: Mapped[float | None] = mapped_column(Float, nullable=True)
  debt_to_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
  profit_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
