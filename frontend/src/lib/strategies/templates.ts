export type TemplatePayload = {
  version: 0;
  settings: {
    symbol: string;
    timeframe: string;
    startDate: string;
    endDate: string;
    initialCapital: number;
    feesBps: number;
    slippageBps: number;
  };
  graph: {
    nodes: Array<{
      id: string;
      type: string;
      x: number;
      y: number;
      label: string;
      params: Record<string, number | string | boolean>;
    }>;
    edges: Array<{
      id: string;
      source: string;
      target: string;
      sourceHandle?: string;
      targetHandle?: string;
    }>;
  };
};

export type TemplateMode = 'single' | 'multi' | 'universe' | 'dataset';

export type TemplateDefinition = {
  id: string;
  name: string;
  description: string;
  /** Asset modes the template is valid in.  The picker filters by this. */
  modes: TemplateMode[];
  payload: TemplatePayload;
};

const baseSettings: TemplatePayload['settings'] = {
  symbol: 'AAPL',
  timeframe: '1D',
  startDate: '2013-01-01',
  endDate: '2018-12-31',
  initialCapital: 10000,
  feesBps: 0,
  slippageBps: 0,
};

const simpleDca: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      {
        id: 'trig',
        type: 'OnBar',
        x: 80,
        y: 80,
        label: 'On Bar',
        params: { timeframe: '1D' },
      },
      {
        id: 'buy',
        type: 'Buy',
        x: 420,
        y: 80,
        label: 'Buy',
        params: { size_type: 'units', amount: 100 },
      },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'buy', sourceHandle: 'out', targetHandle: 'in' },
    ],
  },
};

const goldenCross: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60, y: 140, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'fast', type: 'SMA', x: 340, y: 60, label: 'SMA 50', params: { period: 50 } },
      { id: 'slow', type: 'SMA', x: 340, y: 220, label: 'SMA 200', params: { period: 200 } },
      { id: 'xup', type: 'IfCrossAbove', x: 640, y: 60, label: 'Cross Above', params: {} },
      { id: 'xdn', type: 'IfCrossBelow', x: 640, y: 220, label: 'Cross Below', params: {} },
      { id: 'buy', type: 'Buy', x: 940, y: 60, label: 'Buy', params: { amount: 100 } },
      { id: 'sell', type: 'Sell', x: 940, y: 220, label: 'Sell', params: {} },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'fast', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'slow', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'xup', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'trig', target: 'xdn', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e5', source: 'fast', target: 'xup', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e6', source: 'slow', target: 'xup', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e7', source: 'fast', target: 'xdn', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e8', source: 'slow', target: 'xdn', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e9', source: 'xup', target: 'buy', sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e10', source: 'xdn', target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

const rsiMeanReversion: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60, y: 140, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'rsi', type: 'RSI', x: 340, y: 140, label: 'RSI 14', params: { period: 14, overbought: 70, oversold: 30 } },
      { id: 'k30', type: 'Constant', x: 340, y: 20, label: 'Oversold 30', params: { value: 30 } },
      { id: 'k70', type: 'Constant', x: 340, y: 280, label: 'Overbought 70', params: { value: 70 } },
      { id: 'lt', type: 'IfBelow', x: 640, y: 60, label: 'RSI < 30', params: {} },
      { id: 'gt', type: 'IfAbove', x: 640, y: 240, label: 'RSI > 70', params: {} },
      { id: 'buy', type: 'Buy', x: 940, y: 60, label: 'Buy', params: { amount: 100 } },
      { id: 'sell', type: 'Sell', x: 940, y: 240, label: 'Sell', params: {} },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'rsi', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'lt', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'gt', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'rsi', target: 'lt', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e5', source: 'k30', target: 'lt', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e6', source: 'rsi', target: 'gt', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e7', source: 'k70', target: 'gt', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e8', source: 'lt', target: 'buy', sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e9', source: 'gt', target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// MACD signal-line cross — demonstrates multi-handle indicator outputs.
// The MACD node exposes three ports (macd / signal / histogram); here we
// wire `macd` vs `signal` through cross-detectors to time entries/exits.
const macdSignalCross: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60,  y: 160, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'macd', type: 'MACD',  x: 340, y: 160, label: 'MACD 12/26/9', params: { fast: 12, slow: 26, signal: 9 } },
      { id: 'xup', type: 'IfCrossAbove', x: 660, y: 60,  label: 'MACD > Signal', params: {} },
      { id: 'xdn', type: 'IfCrossBelow', x: 660, y: 260, label: 'MACD < Signal', params: {} },
      { id: 'buy',  type: 'Buy',  x: 960, y: 60,  label: 'Buy',  params: { size_type: 'units', amount: 100 } },
      { id: 'sell', type: 'Sell', x: 960, y: 260, label: 'Sell', params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1',  source: 'trig', target: 'macd', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2',  source: 'trig', target: 'xup',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3',  source: 'trig', target: 'xdn',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4',  source: 'macd', target: 'xup',  sourceHandle: 'macd',   targetHandle: 'a' },
      { id: 'e5',  source: 'macd', target: 'xup',  sourceHandle: 'signal', targetHandle: 'b' },
      { id: 'e6',  source: 'macd', target: 'xdn',  sourceHandle: 'macd',   targetHandle: 'a' },
      { id: 'e7',  source: 'macd', target: 'xdn',  sourceHandle: 'signal', targetHandle: 'b' },
      { id: 'e8',  source: 'xup',  target: 'buy',  sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e9',  source: 'xdn',  target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// Bollinger-band breakout with a hard stop-loss — exposes the Data node
// (live close as a number), the BollingerBands multi-handle indicator, and
// the StopLoss risk node alongside a discretionary exit on the middle band.
const bollingerBreakout: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig',  type: 'OnBar',          x: 60,  y: 200, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'price', type: 'Data',           x: 60,  y: 340, label: 'Close',  params: { timeframe: '1D' } },
      { id: 'bb',    type: 'BollingerBands', x: 340, y: 200, label: 'BB 20/2', params: { period: 20, std: 2 } },
      { id: 'xup', type: 'IfCrossAbove', x: 660, y: 80,  label: 'Close > Upper',  params: {} },
      { id: 'xdn', type: 'IfCrossBelow', x: 660, y: 320, label: 'Close < Middle', params: {} },
      { id: 'buy',  type: 'Buy',      x: 980, y: 80,  label: 'Buy',        params: { size_type: 'pct_equity', amount: 10 } },
      { id: 'stop', type: 'StopLoss', x: 980, y: 200, label: 'Stop −3%',   params: { pct: 3.0 } },
      { id: 'sell', type: 'Sell',     x: 980, y: 320, label: 'Sell',       params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1', source: 'trig',  target: 'bb',   sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig',  target: 'xup',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig',  target: 'xdn',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'trig',  target: 'stop', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e5', source: 'price', target: 'xup',  sourceHandle: 'out',    targetHandle: 'a' },
      { id: 'e6', source: 'bb',    target: 'xup',  sourceHandle: 'upper',  targetHandle: 'b' },
      { id: 'e7', source: 'price', target: 'xdn',  sourceHandle: 'out',    targetHandle: 'a' },
      { id: 'e8', source: 'bb',    target: 'xdn',  sourceHandle: 'middle', targetHandle: 'b' },
      { id: 'e9',  source: 'xup',  target: 'buy',  sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e10', source: 'xdn',  target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// EMA trend-following with the full risk-management stack.  Demonstrates
// EMA indicators plus StopLoss, TakeProfit, and TrailingStop firing in
// parallel — the first exit to trigger wins (engine evaluates exits before
// entries each bar).
const emaTrendRisk: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig',   type: 'OnBar', x: 60,  y: 240, label: 'On Bar',  params: { timeframe: '1D' } },
      { id: 'fast',   type: 'EMA',   x: 340, y: 120, label: 'EMA 12',  params: { period: 12 } },
      { id: 'slow',   type: 'EMA',   x: 340, y: 340, label: 'EMA 26',  params: { period: 26 } },
      { id: 'xup',    type: 'IfCrossAbove', x: 660, y: 240, label: 'Fast > Slow', params: {} },
      { id: 'buy',    type: 'Buy',          x: 980, y: 120, label: 'Buy',          params: { size_type: 'pct_equity', amount: 20 } },
      { id: 'stop',   type: 'StopLoss',     x: 980, y: 240, label: 'Stop −2%',     params: { pct: 2.0 } },
      { id: 'tp',     type: 'TakeProfit',   x: 980, y: 340, label: 'TP +6%',       params: { pct: 6.0 } },
      { id: 'trail',  type: 'TrailingStop', x: 980, y: 440, label: 'Trail −3%',    params: { pct: 3.0 } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'fast',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'slow',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'xup',   sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'trig', target: 'stop',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e5', source: 'trig', target: 'tp',    sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e6', source: 'trig', target: 'trail', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e7', source: 'fast', target: 'xup',   sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e8', source: 'slow', target: 'xup',   sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e9', source: 'xup',  target: 'buy',   sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// Stochastic oscillator confirmed by an RSI trend filter.  Demonstrates the
// Stochastic multi-handle output (%K/%D) and the `And` combinator — both
// the fast/slow cross AND the regime filter must fire on the same bar.
const stochRsiConfirm: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig',  type: 'OnBar',      x: 40,  y: 260, label: 'On Bar',  params: { timeframe: '1D' } },
      { id: 'stoch', type: 'Stochastic', x: 320, y: 100, label: 'Stoch 14/3', params: { k: 14, d: 3 } },
      { id: 'rsi',   type: 'RSI',        x: 320, y: 320, label: 'RSI 14',     params: { period: 14, overbought: 70, oversold: 30 } },
      { id: 'k50',   type: 'Constant',   x: 320, y: 460, label: 'Threshold 50', params: { value: 50 } },
      { id: 'xup',     type: 'IfCrossAbove', x: 620, y: 80,  label: '%K > %D', params: {} },
      { id: 'rsiUp',   type: 'IfAbove',      x: 620, y: 260, label: 'RSI > 50', params: {} },
      { id: 'xdn',     type: 'IfCrossBelow', x: 620, y: 440, label: '%K < %D', params: {} },
      { id: 'and',  type: 'And',  x: 860,  y: 160, label: 'Cross AND Trend', params: {} },
      { id: 'buy',  type: 'Buy',  x: 1120, y: 160, label: 'Buy',  params: { size_type: 'pct_equity', amount: 15 } },
      { id: 'sell', type: 'Sell', x: 1120, y: 440, label: 'Sell', params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1',  source: 'trig',  target: 'rsi',    sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2',  source: 'trig',  target: 'xup',    sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3',  source: 'trig',  target: 'rsiUp',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4',  source: 'trig',  target: 'xdn',    sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e5',  source: 'stoch', target: 'xup',    sourceHandle: 'k', targetHandle: 'a' },
      { id: 'e6',  source: 'stoch', target: 'xup',    sourceHandle: 'd', targetHandle: 'b' },
      { id: 'e7',  source: 'stoch', target: 'xdn',    sourceHandle: 'k', targetHandle: 'a' },
      { id: 'e8',  source: 'stoch', target: 'xdn',    sourceHandle: 'd', targetHandle: 'b' },
      { id: 'e9',  source: 'rsi',   target: 'rsiUp',  sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e10', source: 'k50',   target: 'rsiUp',  sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e11', source: 'xup',   target: 'and',    sourceHandle: 'true', targetHandle: 'a' },
      { id: 'e12', source: 'rsiUp', target: 'and',    sourceHandle: 'true', targetHandle: 'b' },
      { id: 'e13', source: 'and',   target: 'buy',    sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e14', source: 'xdn',   target: 'sell',   sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// Time-boxed dollar-cost averaging at 5% of initial capital per bar.
// Demonstrates the TimeWindow gate, the Position node (flat vs holding
// branching), and the pct_equity Buy sizing mode.  The campaign
// accumulates during [start, end] and unwinds once the window closes.
const timeBoxedDca: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig',     type: 'OnBar',      x: 60,   y: 200, label: 'On Bar',       params: { timeframe: '1D' } },
      { id: 'window',   type: 'TimeWindow', x: 320,  y: 200, label: '2015–2017',    params: { start: '2015-01-01', end: '2017-12-31' } },
      { id: 'posIn',    type: 'Position',   x: 620,  y: 80,  label: 'In window',    params: {} },
      { id: 'posOut',   type: 'Position',   x: 620,  y: 340, label: 'Out of window', params: {} },
      { id: 'buy',      type: 'Buy',        x: 920,  y: 80,  label: 'DCA 5% equity', params: { size_type: 'pct_equity', amount: 5 } },
      { id: 'sell',     type: 'Sell',       x: 920,  y: 340, label: 'Unwind',        params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1', source: 'trig',   target: 'window', sourceHandle: 'out',   targetHandle: 'in' },
      { id: 'e2', source: 'window', target: 'posIn',  sourceHandle: 'true',  targetHandle: 'in' },
      { id: 'e3', source: 'window', target: 'posOut', sourceHandle: 'false', targetHandle: 'in' },
      { id: 'e4', source: 'posIn',  target: 'buy',    sourceHandle: 'flat',    targetHandle: 'in' },
      { id: 'e5', source: 'posOut', target: 'sell',   sourceHandle: 'holding', targetHandle: 'in' },
    ],
  },
};

// Dual-oscillator entry via the `Or` combinator.  Buy when *either*
// Williams %R signals oversold (< −80) OR CCI signals oversold (< −100),
// and unload when CCI rolls into the overbought zone (> 100).  Good
// introduction to OHLCV-derived indicators (no `event` input needed) and
// to the Or gate with two independent entry triggers.
const wrCciOrOversold: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60,  y: 300, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'wr',    type: 'WilliamsR', x: 340, y: 60,  label: '%R 14',   params: { period: 14 } },
      { id: 'k_m80', type: 'Constant',  x: 340, y: 200, label: '−80',     params: { value: -80 } },
      { id: 'cci',   type: 'CCI',       x: 340, y: 340, label: 'CCI 20',  params: { period: 20 } },
      { id: 'k_m100',type: 'Constant',  x: 340, y: 480, label: '−100',    params: { value: -100 } },
      { id: 'k_100', type: 'Constant',  x: 340, y: 620, label: '100',     params: { value: 100 } },
      { id: 'wrLow',  type: 'IfBelow', x: 640, y: 80,  label: '%R < −80',  params: {} },
      { id: 'cciLow', type: 'IfBelow', x: 640, y: 340, label: 'CCI < −100', params: {} },
      { id: 'cciHi',  type: 'IfAbove', x: 640, y: 620, label: 'CCI > 100',  params: {} },
      { id: 'or',   type: 'Or',   x: 900,  y: 200, label: 'Either Oversold', params: {} },
      { id: 'buy',  type: 'Buy',  x: 1160, y: 200, label: 'Buy',   params: { size_type: 'pct_equity', amount: 10 } },
      { id: 'sell', type: 'Sell', x: 1160, y: 620, label: 'Sell',  params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'wrLow',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'cciLow', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'cciHi',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'wr',    target: 'wrLow',  sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e5', source: 'k_m80', target: 'wrLow',  sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e6', source: 'cci',   target: 'cciLow', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e7', source: 'k_m100',target: 'cciLow', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e8', source: 'cci',   target: 'cciHi',  sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e9', source: 'k_100', target: 'cciHi',  sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e10', source: 'wrLow',  target: 'or',  sourceHandle: 'true', targetHandle: 'a' },
      { id: 'e11', source: 'cciLow', target: 'or',  sourceHandle: 'true', targetHandle: 'b' },
      { id: 'e12', source: 'or',     target: 'buy',  sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e13', source: 'cciHi',  target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// Volume-weighted momentum combo.  The Money-Flow Index (MFI — RSI weighted
// by dollar volume) must be oversold AND the Rate-of-Change (ROC) must be
// positive before buying — the `And` combinator requires both on the same
// bar.  Unwind when MFI reaches overbought.
const mfiRocMomentum: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60,  y: 320, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'mfi',  type: 'MFI', x: 340, y: 80,  label: 'MFI 14',  params: { period: 14 } },
      { id: 'k30',  type: 'Constant', x: 340, y: 220, label: 'Oversold 30',   params: { value: 30 } },
      { id: 'roc',  type: 'ROC', x: 340, y: 360, label: 'ROC 10',  params: { period: 10 } },
      { id: 'k0',   type: 'Constant', x: 340, y: 500, label: 'Zero line',     params: { value: 0 } },
      { id: 'k70',  type: 'Constant', x: 340, y: 620, label: 'Overbought 70', params: { value: 70 } },
      { id: 'mfiLo', type: 'IfBelow', x: 640, y: 80,  label: 'MFI < 30',  params: {} },
      { id: 'rocUp', type: 'IfAbove', x: 640, y: 360, label: 'ROC > 0',   params: {} },
      { id: 'mfiHi', type: 'IfAbove', x: 640, y: 620, label: 'MFI > 70',  params: {} },
      { id: 'and',  type: 'And',  x: 900,  y: 220, label: 'Both fire',   params: {} },
      { id: 'buy',  type: 'Buy',  x: 1160, y: 220, label: 'Buy',  params: { size_type: 'pct_equity', amount: 15 } },
      { id: 'sell', type: 'Sell', x: 1160, y: 620, label: 'Sell', params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'roc',   sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'mfiLo', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'rocUp', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'trig', target: 'mfiHi', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e5', source: 'mfi',  target: 'mfiLo', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e6', source: 'k30',  target: 'mfiLo', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e7', source: 'roc',  target: 'rocUp', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e8', source: 'k0',   target: 'rocUp', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e9', source: 'mfi',  target: 'mfiHi', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e10', source: 'k70', target: 'mfiHi', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e11', source: 'mfiLo', target: 'and', sourceHandle: 'true', targetHandle: 'a' },
      { id: 'e12', source: 'rocUp', target: 'and', sourceHandle: 'true', targetHandle: 'b' },
      { id: 'e13', source: 'and',   target: 'buy',  sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e14', source: 'mfiHi', target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// KDJ + KST regime-filtered entry (popular on Futu/Moomoo).  The KST signal
// line acts as a long-term regime filter (only buy while KST > its signal),
// and within that regime the KDJ K/D cross times the entry.  Exits on the
// KDJ cross-down.  Demonstrates both multi-handle indicators simultaneously.
const kdjKstAsian: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60,  y: 280, label: 'On Bar',    params: { timeframe: '1D' } },
      { id: 'kdj',  type: 'KDJ',   x: 340, y: 80,  label: 'KDJ 9/3',   params: { length: 9, signal: 3 } },
      { id: 'kst',  type: 'KST',   x: 340, y: 420, label: 'KST',        params: {} },
      { id: 'kdjUp',   type: 'IfCrossAbove', x: 640, y: 80,  label: 'KDJ K × D up',   params: {} },
      { id: 'kdjDn',   type: 'IfCrossBelow', x: 640, y: 260, label: 'KDJ K × D down', params: {} },
      { id: 'kstTrend',type: 'IfAbove',      x: 640, y: 440, label: 'KST > signal',   params: {} },
      { id: 'and',  type: 'And',  x: 900,  y: 220, label: 'Cross AND regime', params: {} },
      { id: 'buy',  type: 'Buy',  x: 1160, y: 220, label: 'Buy',  params: { size_type: 'pct_equity', amount: 10 } },
      { id: 'sell', type: 'Sell', x: 1160, y: 440, label: 'Sell', params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'kdjUp',    sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'kdjDn',    sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'kstTrend', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'kdj',  target: 'kdjUp', sourceHandle: 'k', targetHandle: 'a' },
      { id: 'e5', source: 'kdj',  target: 'kdjUp', sourceHandle: 'd', targetHandle: 'b' },
      { id: 'e6', source: 'kdj',  target: 'kdjDn', sourceHandle: 'k', targetHandle: 'a' },
      { id: 'e7', source: 'kdj',  target: 'kdjDn', sourceHandle: 'd', targetHandle: 'b' },
      { id: 'e8', source: 'kst',  target: 'kstTrend', sourceHandle: 'kst',    targetHandle: 'a' },
      { id: 'e9', source: 'kst',  target: 'kstTrend', sourceHandle: 'signal', targetHandle: 'b' },
      { id: 'e10', source: 'kdjUp',    target: 'and', sourceHandle: 'true', targetHandle: 'a' },
      { id: 'e11', source: 'kstTrend', target: 'and', sourceHandle: 'true', targetHandle: 'b' },
      { id: 'e12', source: 'and',   target: 'buy',  sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e13', source: 'kdjDn', target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// Volume-surge DCA that pauses during a "blackout" window (e.g. earnings).
// Demonstrates the `Volume` indicator, the `Not` combinator (used to invert
// the TimeWindow's in-window signal), `And`, and `TrailingStop` as the exit.
const volumeBlackoutDca: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60,  y: 320, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'vol',  type: 'Volume',     x: 340, y: 80,  label: 'Volume',    params: {} },
      { id: 'kVol', type: 'Constant',   x: 340, y: 220, label: '30M shares', params: { value: 30000000 } },
      { id: 'win',  type: 'TimeWindow', x: 340, y: 420, label: 'Blackout 2017-H2', params: { start: '2017-07-01', end: '2017-12-31' } },
      { id: 'volHi', type: 'IfAbove', x: 640, y: 120, label: 'Volume > 30M', params: {} },
      { id: 'not',   type: 'Not',     x: 640, y: 420, label: 'NOT in blackout', params: {} },
      { id: 'and',   type: 'And',     x: 900,  y: 260, label: 'Surge AND open', params: {} },
      { id: 'buy',   type: 'Buy',     x: 1160, y: 260, label: 'Buy',  params: { size_type: 'pct_equity', amount: 3 } },
      { id: 'trail', type: 'TrailingStop', x: 1160, y: 460, label: 'Trail −5%', params: { pct: 5.0 } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'volHi', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'win',   sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'trail', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'vol',  target: 'volHi', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e5', source: 'kVol', target: 'volHi', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e6', source: 'win',  target: 'not',   sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e7', source: 'volHi', target: 'and', sourceHandle: 'true', targetHandle: 'a' },
      { id: 'e8', source: 'not',   target: 'and', sourceHandle: 'true', targetHandle: 'b' },
      { id: 'e9', source: 'and',   target: 'buy', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// ATR volatility regime filter gating an EMA-cross trend entry.  ATR > 2.0
// (dollars on price-per-share, roughly ≥1% daily range for ~$150 stocks)
// means enough movement is happening to make the cross worth trading.
// Demonstrates ATR (no-input OHLCV indicator), regime filtering, and `And`.
const atrVolatilityTrend: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60,  y: 260, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'fast', type: 'EMA',   x: 340, y: 80,  label: 'EMA 10', params: { period: 10 } },
      { id: 'slow', type: 'EMA',   x: 340, y: 240, label: 'EMA 30', params: { period: 30 } },
      { id: 'atr',  type: 'ATR',   x: 340, y: 420, label: 'ATR 14', params: { period: 14 } },
      { id: 'kAtr', type: 'Constant', x: 340, y: 560, label: 'ATR ≥ 2.0', params: { value: 2.0 } },
      { id: 'xup',    type: 'IfCrossAbove', x: 640, y: 160, label: 'Fast > Slow',    params: {} },
      { id: 'atrHi',  type: 'IfAbove',      x: 640, y: 440, label: 'ATR ≥ threshold', params: {} },
      { id: 'and',   type: 'And',          x: 900,  y: 280, label: 'Trend AND vol',  params: {} },
      { id: 'buy',   type: 'Buy',          x: 1160, y: 280, label: 'Buy',  params: { size_type: 'pct_equity', amount: 20 } },
      { id: 'trail', type: 'TrailingStop', x: 1160, y: 460, label: 'Trail −4%', params: { pct: 4.0 } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'fast',   sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'slow',   sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'xup',    sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'trig', target: 'atrHi',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e5', source: 'trig', target: 'trail',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e6', source: 'fast', target: 'xup',    sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e7', source: 'slow', target: 'xup',    sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e8', source: 'atr',  target: 'atrHi',  sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e9', source: 'kAtr', target: 'atrHi',  sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e10', source: 'xup',   target: 'and',  sourceHandle: 'true', targetHandle: 'a' },
      { id: 'e11', source: 'atrHi', target: 'and',  sourceHandle: 'true', targetHandle: 'b' },
      { id: 'e12', source: 'and',   target: 'buy',  sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// Scale-out exit ladder that exercises every sizing mode the builder
// supports: Buy with `dollar` sizing (fixed cash per trigger), and three
// Sell nodes — `pct_position` (half out), `units` (shave a fixed share
// count), and `all` (close the remainder).  Entry is an RSI cross below 35;
// the exit legs fire on RSI levels 60 / 75 / 85 as the position recovers.
const scaleOutLadder: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 60,  y: 340, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'rsi',  type: 'RSI',     x: 320, y: 340, label: 'RSI 14', params: { period: 14, overbought: 70, oversold: 30 } },
      { id: 'k35',  type: 'Constant',x: 320, y: 80,  label: 'Entry 35', params: { value: 35 } },
      { id: 'k60',  type: 'Constant',x: 320, y: 220, label: 'Scale 60', params: { value: 60 } },
      { id: 'k75',  type: 'Constant',x: 320, y: 460, label: 'Scale 75', params: { value: 75 } },
      { id: 'k85',  type: 'Constant',x: 320, y: 600, label: 'Scale 85', params: { value: 85 } },
      { id: 'c35', type: 'IfCrossBelow', x: 620, y: 80,  label: 'RSI × 35 down', params: {} },
      { id: 'c60', type: 'IfCrossAbove', x: 620, y: 220, label: 'RSI × 60 up',  params: {} },
      { id: 'c75', type: 'IfCrossAbove', x: 620, y: 460, label: 'RSI × 75 up',  params: {} },
      { id: 'c85', type: 'IfCrossAbove', x: 620, y: 600, label: 'RSI × 85 up',  params: {} },
      { id: 'buy',   type: 'Buy',  x: 940, y: 80,  label: 'Buy $5,000',         params: { size_type: 'dollar',       amount: 5000 } },
      { id: 'sell1', type: 'Sell', x: 940, y: 220, label: 'Sell 50% (scale)',   params: { size_type: 'pct_position', amount: 50 } },
      { id: 'sell2', type: 'Sell', x: 940, y: 460, label: 'Sell 3 shares',      params: { size_type: 'units',        amount: 3 } },
      { id: 'sell3', type: 'Sell', x: 940, y: 600, label: 'Sell remainder',     params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'rsi', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig', target: 'c35', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig', target: 'c60', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'trig', target: 'c75', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e5', source: 'trig', target: 'c85', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e6', source: 'rsi', target: 'c35', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e7', source: 'k35', target: 'c35', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e8', source: 'rsi', target: 'c60', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e9', source: 'k60', target: 'c60', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e10', source: 'rsi', target: 'c75', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e11', source: 'k75', target: 'c75', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e12', source: 'rsi', target: 'c85', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e13', source: 'k85', target: 'c85', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e14', source: 'c35', target: 'buy',   sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e15', source: 'c60', target: 'sell1', sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e16', source: 'c75', target: 'sell2', sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e17', source: 'c85', target: 'sell3', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// OBV trend filter combined with a close-vs-SMA breakout.  OBV is a
// cumulative on-balance-volume line that typically swings sign over long
// regimes; comparing OBV against 0 acts as a coarse volume-trend filter.
// Demonstrates the OBV node alongside the Data node for a direct close read.
const obvBreakout: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig',  type: 'OnBar', x: 60,  y: 260, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'price', type: 'Data',  x: 60,  y: 420, label: 'Close',  params: { timeframe: '1D' } },
      { id: 'sma',   type: 'SMA',   x: 340, y: 80,  label: 'SMA 20',  params: { period: 20 } },
      { id: 'obv',   type: 'OBV',   x: 340, y: 260, label: 'OBV',      params: {} },
      { id: 'k0',    type: 'Constant', x: 340, y: 400, label: 'OBV ≥ 0', params: { value: 0 } },
      { id: 'xup',   type: 'IfCrossAbove', x: 640, y: 80,  label: 'Close × SMA up', params: {} },
      { id: 'obvHi', type: 'IfAbove',      x: 640, y: 320, label: 'OBV ≥ 0',        params: {} },
      { id: 'and',   type: 'And',  x: 900,  y: 200, label: 'Both bullish', params: {} },
      { id: 'buy',   type: 'Buy',  x: 1160, y: 200, label: 'Buy',  params: { size_type: 'pct_equity', amount: 12 } },
      { id: 'stop',  type: 'StopLoss',  x: 1160, y: 380, label: 'Stop −3%', params: { pct: 3.0 } },
    ],
    edges: [
      { id: 'e1', source: 'trig',  target: 'sma',   sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'trig',  target: 'xup',   sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e3', source: 'trig',  target: 'obvHi', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e4', source: 'trig',  target: 'stop',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e5', source: 'price', target: 'xup',   sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e6', source: 'sma',   target: 'xup',   sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e7', source: 'obv',   target: 'obvHi', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e8', source: 'k0',    target: 'obvHi', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e9', source: 'xup',   target: 'and',  sourceHandle: 'true', targetHandle: 'a' },
      { id: 'e10', source: 'obvHi', target: 'and', sourceHandle: 'true', targetHandle: 'b' },
      { id: 'e11', source: 'and',  target: 'buy',  sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// ---------------------------------------------------------------------------
// Universe-mode templates (cross-sectional factor strategies)
// ---------------------------------------------------------------------------
// Universe mode imposes a strict graph: exactly one factor node wired to
// exactly one Rank node, nothing else.  The factor emits a per-name score;
// Rank converts the scores into long (and optionally short) weights
// rebalanced every N bars.  These templates differ only in which factor
// and which Rank parameters they use.

const buildUniverseTemplate = (
  factorType: 'Momentum' | 'Reversal' | 'LowVol' | 'Liquidity' | 'Value',
  factorParams: Record<string, number | string>,
  factorLabel: string,
  rankParams: { top_pct: number; bottom_pct: number; rebalance_days: number; mode: 'long_only' | 'long_short' },
  rankLabel: string,
): TemplatePayload => ({
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'factor', type: factorType, x: 200, y: 180, label: factorLabel, params: factorParams },
      { id: 'rank',   type: 'Rank',     x: 560, y: 180, label: rankLabel,   params: rankParams },
    ],
    edges: [
      { id: 'e1', source: 'factor', target: 'rank', sourceHandle: 'out', targetHandle: 'in' },
    ],
  },
});

// Classic 12-1 momentum — trailing 252-bar return skipping the most recent
// month (standard in academic literature to avoid 1-month reversal).
const universeMomentum121 = buildUniverseTemplate(
  'Momentum',
  { lookback: 252, skip: 21 },
  'Momentum 12−1',
  { top_pct: 0.2, bottom_pct: 0.2, rebalance_days: 21, mode: 'long_only' },
  'Rank top 20% · monthly',
);

// Dollar-neutral long/short momentum at higher turnover.
const universeMomentumLS = buildUniverseTemplate(
  'Momentum',
  { lookback: 126, skip: 21 },
  'Momentum 6−1',
  { top_pct: 0.1, bottom_pct: 0.1, rebalance_days: 21, mode: 'long_short' },
  'Rank ±10% · L/S',
);

// Short-term reversal — buy the prior-month losers, rebalance weekly.
const universeReversal = buildUniverseTemplate(
  'Reversal',
  { period: 21 },
  'Reversal 21',
  { top_pct: 0.2, bottom_pct: 0.2, rebalance_days: 5, mode: 'long_only' },
  'Rank top 20% · weekly',
);

// Low-volatility anomaly — negated 63-bar realized vol.
const universeLowVol = buildUniverseTemplate(
  'LowVol',
  { period: 63 },
  'Low Vol 63',
  { top_pct: 0.2, bottom_pct: 0.2, rebalance_days: 21, mode: 'long_only' },
  'Rank top 20% · monthly',
);

// Liquidity tilt — mean dollar volume; long most-liquid names.
const universeLiquidity = buildUniverseTemplate(
  'Liquidity',
  { period: 60 },
  'Liquidity 60',
  { top_pct: 0.3, bottom_pct: 0.3, rebalance_days: 21, mode: 'long_only' },
  'Rank top 30% · monthly',
);

// Value factor — earnings yield (TTM EPS / price). Long cheapest quintile,
// quarterly rebalance.
const universeValue = buildUniverseTemplate(
  'Value',
  {},
  'Value (E/P)',
  { top_pct: 0.2, bottom_pct: 0.2, rebalance_days: 63, mode: 'long_only' },
  'Rank top 20% · quarterly',
);

// Fundamental P/E screen — regular-mode template. Buy when the PE ratio
// drops into value territory (< 15) and sell once it re-rates above 25.
const peScreen: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 80, y: 80, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'pe',   type: 'PE',    x: 80, y: 200, label: 'P/E', params: {} },
      { id: 'low',  type: 'Constant', x: 80, y: 320, label: 'PE < 15', params: { value: 15 } },
      { id: 'high', type: 'Constant', x: 80, y: 440, label: 'PE > 25', params: { value: 25 } },
      { id: 'ifBuy',  type: 'IfBelow', x: 420, y: 160, label: 'PE < 15?', params: {} },
      { id: 'ifSell', type: 'IfAbove', x: 420, y: 360, label: 'PE > 25?', params: {} },
      { id: 'buy',  type: 'Buy',  x: 760, y: 160, label: 'Buy 10% equity', params: { size_type: 'pct_equity', amount: 10 } },
      { id: 'sell', type: 'Sell', x: 760, y: 360, label: 'Sell all', params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'ifBuy',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'pe',   target: 'ifBuy',  sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e3', source: 'low',  target: 'ifBuy',  sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e4', source: 'ifBuy', target: 'buy',   sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e5', source: 'trig', target: 'ifSell', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e6', source: 'pe',   target: 'ifSell', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e7', source: 'high', target: 'ifSell', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e8', source: 'ifSell', target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// Dividend yield screen — buy high-yielders, sell when yield compresses.
const dividendScreen: TemplatePayload = {
  version: 0,
  settings: baseSettings,
  graph: {
    nodes: [
      { id: 'trig', type: 'OnBar', x: 80, y: 80, label: 'On Bar', params: { timeframe: '1D' } },
      { id: 'dy',   type: 'DividendYield', x: 80, y: 200, label: 'Div Yield', params: {} },
      { id: 'high', type: 'Constant', x: 80, y: 320, label: 'Yield > 4%', params: { value: 4 } },
      { id: 'low',  type: 'Constant', x: 80, y: 440, label: 'Yield < 2%', params: { value: 2 } },
      { id: 'ifBuy',  type: 'IfAbove', x: 420, y: 160, label: 'Yield > 4?', params: {} },
      { id: 'ifSell', type: 'IfBelow', x: 420, y: 360, label: 'Yield < 2?', params: {} },
      { id: 'buy',  type: 'Buy',  x: 760, y: 160, label: 'Buy 10% equity', params: { size_type: 'pct_equity', amount: 10 } },
      { id: 'sell', type: 'Sell', x: 760, y: 360, label: 'Sell all', params: { size_type: 'all' } },
    ],
    edges: [
      { id: 'e1', source: 'trig', target: 'ifBuy',  sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e2', source: 'dy',   target: 'ifBuy',  sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e3', source: 'high', target: 'ifBuy',  sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e4', source: 'ifBuy', target: 'buy',   sourceHandle: 'true', targetHandle: 'in' },
      { id: 'e5', source: 'trig', target: 'ifSell', sourceHandle: 'out', targetHandle: 'in' },
      { id: 'e6', source: 'dy',   target: 'ifSell', sourceHandle: 'out', targetHandle: 'a' },
      { id: 'e7', source: 'low',  target: 'ifSell', sourceHandle: 'out', targetHandle: 'b' },
      { id: 'e8', source: 'ifSell', target: 'sell', sourceHandle: 'true', targetHandle: 'in' },
    ],
  },
};

// Template mode defaults — single/multi/dataset share the regular palette.
const REGULAR_MODES: TemplateMode[] = ['single', 'multi', 'dataset'];
const UNIVERSE_MODES: TemplateMode[] = ['universe'];

export const STRATEGY_TEMPLATES: TemplateDefinition[] = [
  {
    id: 'dca',
    name: 'Simple DCA',
    description: 'Buy a fixed quantity every bar. The classic dollar-cost-averaging baseline.',
    modes: REGULAR_MODES,
    payload: simpleDca,
  },
  {
    id: 'golden-cross',
    name: 'Golden Cross (50/200)',
    description: 'Buy when the 50-day SMA crosses above the 200-day SMA, sell on the inverse cross.',
    modes: REGULAR_MODES,
    payload: goldenCross,
  },
  {
    id: 'rsi-mr',
    name: 'RSI Mean Reversion',
    description: 'Buy when RSI(14) drops below 30 (oversold); sell when it rises above 70 (overbought).',
    modes: REGULAR_MODES,
    payload: rsiMeanReversion,
  },
  {
    id: 'macd-cross',
    name: 'MACD Signal Cross',
    description: 'Buy when the MACD line crosses above its signal line; sell on the inverse. Demonstrates multi-handle indicator outputs.',
    modes: REGULAR_MODES,
    payload: macdSignalCross,
  },
  {
    id: 'bb-breakout',
    name: 'Bollinger Breakout + Stop',
    description: 'Buy when close breaks above the upper band; exit on a cross back through the middle band or a 3% stop-loss.',
    modes: REGULAR_MODES,
    payload: bollingerBreakout,
  },
  {
    id: 'ema-trend-risk',
    name: 'EMA Trend + Full Risk Stack',
    description: 'Enter on an EMA 12/26 crossover, then let StopLoss, TakeProfit, and TrailingStop race to exit — whichever fires first wins.',
    modes: REGULAR_MODES,
    payload: emaTrendRisk,
  },
  {
    id: 'stoch-rsi-confirm',
    name: 'Stochastic + RSI Filter',
    description: 'Buy on a Stochastic %K/%D cross only when RSI(14) confirms the trend is above 50. Exit on the inverse cross.',
    modes: REGULAR_MODES,
    payload: stochRsiConfirm,
  },
  {
    id: 'timeboxed-dca',
    name: 'Time-Boxed % Equity DCA',
    description: 'Accumulate 5% of initial capital each bar during 2015–2017; auto-unwind once the window closes. Showcases TimeWindow + Position gates.',
    modes: REGULAR_MODES,
    payload: timeBoxedDca,
  },
  {
    id: 'wr-cci-or',
    name: 'Williams %R / CCI Oversold (Or)',
    description: 'Buy on either Williams %R < −80 OR CCI < −100. Demonstrates the Or combinator with two independent oscillator triggers.',
    modes: REGULAR_MODES,
    payload: wrCciOrOversold,
  },
  {
    id: 'mfi-roc-momentum',
    name: 'MFI + ROC Volume-Momentum',
    description: 'Buy when MFI is oversold AND ROC is positive — volume-weighted RSI plus rate-of-change, combined with the And gate.',
    modes: REGULAR_MODES,
    payload: mfiRocMomentum,
  },
  {
    id: 'kdj-kst-asian',
    name: 'KDJ + KST Regime Filter',
    description: 'Popular Asian-market combo: buy on KDJ K×D cross up, but only while the KST line is above its signal. Two multi-handle indicators in one graph.',
    modes: REGULAR_MODES,
    payload: kdjKstAsian,
  },
  {
    id: 'volume-blackout-dca',
    name: 'Volume Surge + Blackout Window',
    description: 'DCA on volume spikes (>30M shares) but pause during a 2017-H2 blackout window. Showcases Volume, Not, TimeWindow, and TrailingStop.',
    modes: REGULAR_MODES,
    payload: volumeBlackoutDca,
  },
  {
    id: 'atr-volatility-trend',
    name: 'ATR Volatility-Filtered Trend',
    description: 'EMA 10/30 cross entry, but only when ATR ≥ 2.0 indicates enough volatility for the move to matter. Trailing stop exits.',
    modes: REGULAR_MODES,
    payload: atrVolatilityTrend,
  },
  {
    id: 'scale-out-ladder',
    name: 'Scale-Out Exit Ladder',
    description: 'Buy $5,000 worth on RSI cross-down, then exit in three legs: 50% at RSI 60, −3 shares at 75, rest at 85. Every Buy/Sell sizing mode in one template.',
    modes: REGULAR_MODES,
    payload: scaleOutLadder,
  },
  {
    id: 'obv-breakout',
    name: 'OBV Trend + SMA Breakout',
    description: 'Buy when close crosses above SMA 20 AND OBV is positive (cumulative volume bullish). Demonstrates the OBV node and Data (close) readout.',
    modes: REGULAR_MODES,
    payload: obvBreakout,
  },
  // ── Universe (factor) mode templates ────────────────────────────────
  {
    id: 'universe-momentum-121',
    name: 'Cross-Sectional Momentum (12−1)',
    description: 'Classic academic momentum: trailing 252-bar return skipping the most recent month. Long the top 20%, rebalance monthly.',
    modes: UNIVERSE_MODES,
    payload: universeMomentum121,
  },
  {
    id: 'universe-momentum-ls',
    name: 'Long/Short Momentum (Dollar-Neutral)',
    description: '6−1 momentum with an equal-dollar short on the bottom decile. Dollar-neutral exposure, monthly rebalance.',
    modes: UNIVERSE_MODES,
    payload: universeMomentumLS,
  },
  {
    id: 'universe-reversal',
    name: 'Short-Term Reversal',
    description: 'Buy prior-month losers (inverse 21-bar return), weekly rebalance. Harvests short-term mean-reversion.',
    modes: UNIVERSE_MODES,
    payload: universeReversal,
  },
  {
    id: 'universe-lowvol',
    name: 'Low-Volatility Anomaly',
    description: 'Long the top 20% lowest-realized-volatility names over 63 bars. Rebalance monthly. Captures the low-vol anomaly.',
    modes: UNIVERSE_MODES,
    payload: universeLowVol,
  },
  {
    id: 'universe-liquidity',
    name: 'Liquidity Tilt',
    description: 'Long the top 30% most-liquid names by mean dollar volume. A sanity baseline for universe backtests.',
    modes: UNIVERSE_MODES,
    payload: universeLiquidity,
  },
  {
    id: 'universe-value',
    name: 'Value (Earnings Yield)',
    description: 'Long the cheapest 20% by TTM earnings yield (EPS / price). Quarterly rebalance. Requires fundamentals data.',
    modes: UNIVERSE_MODES,
    payload: universeValue,
  },
  {
    id: 'pe-screen',
    name: 'P/E Value Screen',
    description: 'Buy when P/E drops below 15 (value territory); exit when it re-rates above 25. Single-stock fundamentals demo.',
    modes: REGULAR_MODES,
    payload: peScreen,
  },
  {
    id: 'dividend-screen',
    name: 'High-Yield Dividend Screen',
    description: 'Buy when TTM dividend yield is above 4%; sell once it compresses below 2%. Demonstrates the DividendYield node.',
    modes: REGULAR_MODES,
    payload: dividendScreen,
  },
];
