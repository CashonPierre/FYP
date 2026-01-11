from datetime import datetime

from pydantic import BaseModel, ConfigDict


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

