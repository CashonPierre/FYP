from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OhlcBarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

class RefreshRequest(BaseModel):
    """
    Trigger a market data refresh.

    Provide either `symbols` (explicit list) or `universe` (named group).
    At least one must be set.  If both are set, symbols from both are merged.
    """
    symbols: list[str] = Field(default_factory=list, description="Explicit ticker list, e.g. ['AAPL', 'MSFT']")
    universe: str | None = Field(default=None, description="Universe key, e.g. 'mag7'")
    timeframe: str = Field(default="1D", description="Bar timeframe: '1D', '1W', '1M'")
    start: str | None = Field(
        default=None,
        description="Force fetch from this ISO date (YYYY-MM-DD). If omitted, resumes from last bar in DB.",
    )


class RefreshTaskOut(BaseModel):
    symbol: str
    task_id: str


class RefreshResponse(BaseModel):
    enqueued: int
    tasks: list[RefreshTaskOut]


# ---------------------------------------------------------------------------
# Universes
# ---------------------------------------------------------------------------

class UniverseOut(BaseModel):
    key: str
    name: str
    description: str
    count: int
    symbols: list[str]


class UniversesResponse(BaseModel):
    universes: list[UniverseOut]
