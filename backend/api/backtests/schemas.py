# STL
import uuid
from datetime import datetime

# External
from pydantic import BaseModel, model_validator


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class BacktestSettings(BaseModel):
  symbol: str | None = None      # single-symbol (optional when symbols/universe given)
  timeframe: str = "1D"
  start_date: str | None = None
  end_date: str | None = None
  initial_capital: float = 10000.0
  fees_bps: float = 0.0
  slippage_bps: float = 0.0
  # "single"   → one symbol per run (single or multi-symbol fan-out)
  # "universe" → one run ranks a universe cross-sectionally (factor strategy)
  execution_mode: str = "single"
  # BYOD: when set, backtest pulls bars from user_ohlc_bars for this dataset
  # instead of the preset OhlcBar universe. Mutually exclusive with symbols/universe.
  dataset_id: uuid.UUID | None = None


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
  # Multi-asset extensions — at least one of symbol/symbols/universe must be present
  symbols: list[str] | None = None   # explicit symbol list
  universe: str | None = None        # named universe key

  @model_validator(mode="after")
  def require_symbol_source(self):
    has_single = bool(self.settings.symbol)
    has_multi = bool(self.symbols) or bool(self.universe)
    has_dataset = bool(self.settings.dataset_id)
    if not has_single and not has_multi and not has_dataset:
      raise ValueError("Provide settings.symbol, settings.dataset_id, symbols list, or universe key")
    if has_dataset and (has_multi or has_single):
      raise ValueError("dataset_id cannot be combined with symbol / symbols / universe")
    return self


# ---------------------------------------------------------------------------
# Single-run response (backward-compat)
# ---------------------------------------------------------------------------

class BacktestSubmitted(BaseModel):
  id: uuid.UUID          # run_id for single-symbol; batch_id for multi
  status: str
  batch_id: uuid.UUID | None = None   # set when a batch was created
  run_ids: list[uuid.UUID] = []       # populated for multi-symbol batches


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
  sortino: float | None = None
  calmar: float | None = None
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
  symbol: str | None = None          # so the UI can label charts without re-reading settings
  timeframe: str | None = None
  start_date: str | None = None      # as recorded in run settings (may be None)
  end_date: str | None = None
  strategy_name: str | None = None   # from strategies.name when strategy_id set
  summary: ResultSummary | None = None
  series: ResultSeries = ResultSeries()


class BacktestListItem(BaseModel):
  id: uuid.UUID
  status: str
  # None for universe-mode runs whose settings carry `symbols` (plural).
  symbol: str | None = None
  timeframe: str
  created_at: datetime
  total_return: float | None = None
  batch_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Batch response
# ---------------------------------------------------------------------------

class BatchRunSummary(BaseModel):
  """Summary of one symbol's run within a batch."""
  run_id: uuid.UUID
  # None for universe-mode runs (cross-sectional factor run over many symbols)
  # where a single run has no single "symbol"; its settings carry `symbols` instead.
  symbol: str | None = None
  status: str
  total_return: float | None = None
  max_drawdown: float | None = None
  sharpe: float | None = None
  total_trades: int | None = None
  error_message: str | None = None


class BatchAggregate(BaseModel):
  """Aggregate statistics across all runs in the batch."""
  total_symbols: int
  completed: int
  failed: int
  running: int
  queued: int
  best_symbol: str | None = None
  best_return: float | None = None
  worst_symbol: str | None = None
  worst_return: float | None = None
  avg_return: float | None = None


class BatchStatus(BaseModel):
  """Full batch status + per-symbol results."""
  id: uuid.UUID
  status: str
  symbols: list[str]
  runs: list[BatchRunSummary]
  aggregate: BatchAggregate
  created_at: datetime
  started_at: datetime | None = None
  ended_at: datetime | None = None


class BatchCombinedResults(BaseModel):
  """Equal-weight portfolio view of a multi-symbol batch.

  Each completed child run is allocated `initial_capital / N` and the
  per-run equity curves are pooled into a single NAV series. Failed /
  incomplete runs are excluded from N (the combined portfolio represents
  only the symbols that actually ran).
  """
  id: uuid.UUID                  # batch_id
  status: str                    # batch status
  symbols: list[str]             # symbols included in the combination
  skipped_symbols: list[str] = []  # symbols whose runs failed / never completed
  initial_capital: float
  summary: ResultSummary | None = None
  equity: list[EquityPoint] = []
