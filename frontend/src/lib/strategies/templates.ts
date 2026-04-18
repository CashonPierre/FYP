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

export type TemplateDefinition = {
  id: string;
  name: string;
  description: string;
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
        params: { amount: 100 },
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

export const STRATEGY_TEMPLATES: TemplateDefinition[] = [
  {
    id: 'dca',
    name: 'Simple DCA',
    description: 'Buy a fixed dollar amount every bar. The classic dollar-cost-averaging baseline.',
    payload: simpleDca,
  },
  {
    id: 'golden-cross',
    name: 'Golden Cross (50/200)',
    description: 'Buy when the 50-day SMA crosses above the 200-day SMA, sell on the inverse cross.',
    payload: goldenCross,
  },
  {
    id: 'rsi-mr',
    name: 'RSI Mean Reversion',
    description: 'Buy when RSI(14) drops below 30 (oversold); sell when it rises above 70 (overbought).',
    payload: rsiMeanReversion,
  },
];
