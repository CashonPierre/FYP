# STL
from typing import Literal

# External
from pydantic import BaseModel, Field, field_validator, model_validator

# Node types the builder canvas understands. Kept in sync with the palette
# in frontend/src/routes/app/backtests/new/+page.svelte and with the
# evaluator in backend/background/tasks/graph_strategy.py.
NodeType = Literal[
  # Triggers & data
  "OnBar",
  "Data",
  "Constant",
  # Technical indicators
  "SMA",
  "EMA",
  "RSI",
  "MACD",
  "BollingerBands",
  "ATR",
  "Volume",
  "Stochastic",
  "ROC",
  "WilliamsR",
  "CCI",
  "KDJ",
  "MFI",
  "OBV",
  "KST",
  # Fundamental indicators
  "PE",
  "EPS",
  "ROE",
  "DividendYield",
  # Math
  "Add",
  "Subtract",
  "Multiply",
  "Divide",
  # Conditions / combinators
  "IfAbove",
  "IfBelow",
  "IfCrossAbove",
  "IfCrossBelow",
  "And",
  "Or",
  "Not",
  "TimeWindow",
  "Position",
  # Actions / risk
  "Buy",
  "Sell",
  "StopLoss",
  "TakeProfit",
  "TrailingStop",
  # Universe / factor mode
  "Momentum",
  "Reversal",
  "LowVol",
  "Liquidity",
  "Value",
  "Rank",
]


ParamValue = float | int | str | bool


# Valid output/input handle names per node type. Kept in sync with
# `getNodeSpec` in frontend/src/routes/app/backtests/new/+page.svelte.
# An empty tuple means the node has no ports of that direction.
_NO_INPUT: tuple[str, ...] = ()
_EVENT_IN: tuple[str, ...] = ("in",)

OUTPUT_HANDLES: dict[str, tuple[str, ...]] = {
  "OnBar": ("out",),
  "Data": ("out",),
  "Constant": ("out",),
  "SMA": ("out",),
  "EMA": ("out",),
  "RSI": ("out",),
  "ROC": ("out",),
  "ATR": ("out",),
  "Volume": ("out",),
  "WilliamsR": ("out",),
  "CCI": ("out",),
  "MFI": ("out",),
  "OBV": ("out",),
  "MACD": ("macd", "signal", "histogram"),
  "BollingerBands": ("upper", "middle", "lower"),
  "Stochastic": ("k", "d"),
  "KDJ": ("k", "d", "j"),
  "KST": ("kst", "signal"),
  "PE": ("out",),
  "EPS": ("out",),
  "ROE": ("out",),
  "DividendYield": ("out",),
  "Add": ("out",),
  "Subtract": ("out",),
  "Multiply": ("out",),
  "Divide": ("out",),
  "IfAbove": ("true", "false"),
  "IfBelow": ("true", "false"),
  "IfCrossAbove": ("true", "false"),
  "IfCrossBelow": ("true", "false"),
  "And": ("true", "false"),
  "Or": ("true", "false"),
  "Not": ("true", "false"),
  "TimeWindow": ("true", "false"),
  "Position": ("flat", "holding"),
  "Buy": (),
  "Sell": (),
  "StopLoss": (),
  "TakeProfit": (),
  "TrailingStop": (),
  "Momentum": ("out",),
  "Reversal": ("out",),
  "LowVol": ("out",),
  "Liquidity": ("out",),
  "Value": ("out",),
  "Rank": (),
}

INPUT_HANDLES: dict[str, tuple[str, ...]] = {
  "OnBar": _NO_INPUT,
  "Data": _NO_INPUT,
  "Constant": _NO_INPUT,
  "SMA": _EVENT_IN,
  "EMA": _EVENT_IN,
  "RSI": _EVENT_IN,
  "ROC": _EVENT_IN,
  "MACD": _EVENT_IN,
  "BollingerBands": _EVENT_IN,
  "ATR": _NO_INPUT,
  "Volume": _NO_INPUT,
  "Stochastic": _NO_INPUT,
  "WilliamsR": _NO_INPUT,
  "CCI": _NO_INPUT,
  "KDJ": _NO_INPUT,
  "MFI": _NO_INPUT,
  "OBV": _NO_INPUT,
  "KST": _NO_INPUT,
  "PE": _NO_INPUT,
  "EPS": _NO_INPUT,
  "ROE": _NO_INPUT,
  "DividendYield": _NO_INPUT,
  "Add": ("a", "b"),
  "Subtract": ("a", "b"),
  "Multiply": ("a", "b"),
  "Divide": ("a", "b"),
  "IfAbove": ("in", "a", "b"),
  "IfBelow": ("in", "a", "b"),
  "IfCrossAbove": ("in", "a", "b"),
  "IfCrossBelow": ("in", "a", "b"),
  "And": ("a", "b"),
  "Or": ("a", "b"),
  "Not": _EVENT_IN,
  "TimeWindow": _EVENT_IN,
  "Position": _EVENT_IN,
  "Buy": _EVENT_IN,
  "Sell": _EVENT_IN,
  "StopLoss": _EVENT_IN,
  "TakeProfit": _EVENT_IN,
  "TrailingStop": _EVENT_IN,
  "Momentum": _NO_INPUT,
  "Reversal": _NO_INPUT,
  "LowVol": _NO_INPUT,
  "Liquidity": _NO_INPUT,
  "Value": _NO_INPUT,
  "Rank": _EVENT_IN,
}


class GraphNode(BaseModel):
  id: str = Field(min_length=1, max_length=64)
  type: NodeType
  x: float = 0
  y: float = 0
  label: str = ""
  params: dict[str, ParamValue] = Field(default_factory=dict)


class GraphEdge(BaseModel):
  id: str = Field(min_length=1, max_length=64)
  source: str = Field(min_length=1, max_length=64)
  target: str = Field(min_length=1, max_length=64)
  sourceHandle: str | None = None
  targetHandle: str | None = None


class BuiltGraph(BaseModel):
  """The graph payload that the LLM must return. Mirrors the
  `{nodes, edges}` shape the builder canvas loads from a template."""

  nodes: list[GraphNode]
  edges: list[GraphEdge]

  @field_validator("nodes")
  @classmethod
  def _nonempty_nodes(cls, v: list[GraphNode]) -> list[GraphNode]:
    if not v:
      raise ValueError("graph must contain at least one node")
    ids = [n.id for n in v]
    if len(ids) != len(set(ids)):
      raise ValueError("node ids must be unique")
    return v

  @model_validator(mode="after")
  def _edges_reference_existing_nodes(self) -> "BuiltGraph":
    by_id = {n.id: n for n in self.nodes}
    for e in self.edges:
      src = by_id.get(e.source)
      tgt = by_id.get(e.target)
      if src is None:
        raise ValueError(f"edge {e.id} source '{e.source}' is not a node id")
      if tgt is None:
        raise ValueError(f"edge {e.id} target '{e.target}' is not a node id")
      valid_out = OUTPUT_HANDLES.get(src.type, ())
      valid_in = INPUT_HANDLES.get(tgt.type, ())
      if e.sourceHandle and e.sourceHandle not in valid_out:
        raise ValueError(
          f"edge {e.id}: {src.type} has no output handle "
          f"'{e.sourceHandle}' (valid: {list(valid_out)})"
        )
      if e.targetHandle and e.targetHandle not in valid_in:
        raise ValueError(
          f"edge {e.id}: {tgt.type} has no input handle "
          f"'{e.targetHandle}' (valid: {list(valid_in)})"
        )
    edge_ids = [e.id for e in self.edges]
    if len(edge_ids) != len(set(edge_ids)):
      raise ValueError("edge ids must be unique")
    return self


class BuildGraphRequest(BaseModel):
  prompt: str = Field(min_length=4, max_length=2000)


class BuildGraphResponse(BaseModel):
  graph: BuiltGraph
  notes: str = ""
  """Free-text explanation from the LLM, shown above the preview."""
