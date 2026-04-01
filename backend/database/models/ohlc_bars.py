# External
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Float
from sqlalchemy.orm import Mapped, mapped_column

# Custom
from database.make_db import Base


class OhlcBar(Base):
    __tablename__ = "ohlc_bars"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    timeframe: Mapped[str] = mapped_column(String, primary_key=True)
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, index=True
    )

    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

