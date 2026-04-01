from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.make_db import get_session
from database.models import OhlcBar

from .schemas import OhlcBarOut


market_router = APIRouter(prefix="/market", tags=["Market data"])


@market_router.get("/ohlc", response_model=list[OhlcBarOut])
def get_ohlc(
    symbol: str = Query(min_length=1, max_length=16),
    timeframe: str = Query(default="1D", min_length=1, max_length=16),
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(dependency=get_session),
) -> list[OhlcBarOut]:
    stmt = (
        select(OhlcBar)
        .where(OhlcBar.symbol == symbol, OhlcBar.timeframe == timeframe)
        .order_by(OhlcBar.time.asc())
        .limit(limit)
    )

    if start is not None:
        stmt = stmt.where(OhlcBar.time >= start)
    if end is not None:
        stmt = stmt.where(OhlcBar.time <= end)

    rows = session.execute(stmt).scalars().all()
    return rows

