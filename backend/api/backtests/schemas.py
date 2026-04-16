# STL
import uuid
from datetime import datetime

# External
from pydantic import BaseModel


# --- Request ---

class BacktestSettings(BaseModel):
  symbol: str
  timeframe: str = "1D"
  start_date: str | None = None
  end_date: str | None = None
  initial_capital: float = 10000.0
  fees_bps: float = 0.0
  slippage_bps: float = 0.0


class GraphNode(BaseModel):
  id: str
  type: str
  position: dict
  data: dict = {}


class GraphEdge(BaseModel):
  id: str
  source: str
  target: str
  source_handle: str | None = None
  target_handle: str | None = None


class StrategyGraph(BaseModel):
  nodes: list[GraphNode]
  edges: list[GraphEdge]


class BacktestCreate(BaseModel):
  version: int = 0
  settings: BacktestSettings
  graph: StrategyGraph


# --- Response ---

class BacktestSubmitted(BaseModel):
  id: uuid.UUID
  status: str


class BacktestStatus(BaseModel):
  id: uuid.UUID
  status: str
  started_at: datetime | None = None
  ended_at: datetime | None = None
  error_message: str | None = None


class OhlcPoint(BaseModel):
  time: str
  open: float
  high: float
  low: float
  close: float
  volume: int | None = None


class EquityPoint(BaseModel):
  time: str
  equity: float


class TradePoint(BaseModel):
  id: str
  time: str
  side: str
  price: float
  quantity: float
  symbol: str


class ResultSummary(BaseModel):
  initial_capital: float
  final_nav: float
  total_return: float
  annualized_return: float | None = None
  max_drawdown: float | None = None
  volatility: float | None = None
  sharpe: float | None = None
  total_trades: int
  win_rate: float | None = None
  fees: float
  slippage: float


class ResultSeries(BaseModel):
  ohlc: list[OhlcPoint] = []
  equity: list[EquityPoint] = []
  trades: list[TradePoint] = []


class BacktestResults(BaseModel):
  id: uuid.UUID
  status: str
  summary: ResultSummary | None = None
  series: ResultSeries = ResultSeries()


class BacktestListItem(BaseModel):
  id: uuid.UUID
  status: str
  symbol: str
  timeframe: str
  created_at: datetime
  total_return: float | None = None
