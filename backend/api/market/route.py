from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth.dependencies import get_current_user
from database.make_db import get_session
from database.models import OhlcBar

from .schemas import (
    OhlcBarOut,
    RefreshRequest,
    RefreshResponse,
    RefreshTaskOut,
    UniverseOut,
    UniversesResponse,
)
from .universes import UNIVERSES, get_universe_symbols

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


@market_router.post("/refresh", response_model=RefreshResponse, status_code=status.HTTP_202_ACCEPTED)
def refresh_market_data(
    payload: RefreshRequest,
    _user=Depends(get_current_user),
) -> RefreshResponse:
    """
    Enqueue market data refresh jobs for the requested symbols / universe.

    - Provide `symbols`, `universe`, or both.
    - Each symbol gets its own Celery task (incremental — only fetches bars
      newer than what's already in DB, unless `start` is provided).
    - Returns 202 immediately with task IDs.
    """
    from background.tasks.market_refresh import refresh_symbol_ohlc

    # Collect symbols from explicit list + universe
    symbols: list[str] = list(payload.symbols)
    if payload.universe:
        try:
            symbols += get_universe_symbols(payload.universe)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown universe '{payload.universe}'. Available: {list(UNIVERSES.keys())}",
            )

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_symbols: list[str] = []
    for s in symbols:
        s = s.upper().strip()
        if s and s not in seen:
            seen.add(s)
            unique_symbols.append(s)

    if not unique_symbols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No symbols specified. Provide 'symbols' list or a 'universe' key.",
        )

    tasks: list[RefreshTaskOut] = []
    for symbol in unique_symbols:
        task = refresh_symbol_ohlc.delay(symbol, payload.timeframe, payload.start)
        tasks.append(RefreshTaskOut(symbol=symbol, task_id=task.id))

    return RefreshResponse(enqueued=len(tasks), tasks=tasks)


@market_router.get("/universes", response_model=UniversesResponse)
def get_universes() -> UniversesResponse:
    """Return all available universe definitions with symbol lists."""
    return UniversesResponse(
        universes=[
            UniverseOut(
                key=key,
                name=meta["name"],
                description=meta["description"],
                count=len(meta["symbols"]),
                symbols=meta["symbols"],
            )
            for key, meta in UNIVERSES.items()
        ]
    )
