<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { startTourIfUnseen } from '$lib/onboarding/tour.js';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { Textarea } from '$lib/components/ui/textarea/index.js';
  import * as Alert from '$lib/components/ui/alert/index.js';
  import { cn } from '$lib/utils.js';
  import { toast } from 'svelte-sonner';
  import { BACKEND } from '$lib/config.js';
  import { STRATEGY_TEMPLATES } from '$lib/strategies/templates.js';

  type NodeType =
    | 'OnBar'
    | 'Data'
    | 'SMA'
    | 'EMA'
    | 'RSI'
    | 'MACD'
    | 'BollingerBands'
    | 'ATR'
    | 'Volume'
    | 'Stochastic'
    | 'ROC'
    | 'WilliamsR'
    | 'CCI'
    | 'KDJ'
    | 'MFI'
    | 'OBV'
    | 'KST'
    | 'And'
    | 'Or'
    | 'Not'
    | 'TimeWindow'
    | 'Position'
    | 'StopLoss'
    | 'TakeProfit'
    | 'TrailingStop'
    | 'IfAbove'
    | 'IfBelow'
    | 'IfCrossAbove'
    | 'IfCrossBelow'
    | 'Constant'
    // Math
    | 'Add'
    | 'Subtract'
    | 'Multiply'
    | 'Divide'
    | 'Buy'
    | 'Sell'
    // Fundamental indicators (require FundamentalSnapshot data)
    | 'PE'
    | 'EPS'
    | 'ROE'
    | 'DividendYield'
    // Universe-mode factor nodes
    | 'Momentum'
    | 'Reversal'
    | 'LowVol'
    | 'Liquidity'
    | 'Value'
    | 'Rank';

  type BuilderNode = {
    id: string;
    type: NodeType;
    x: number;
    y: number;
    label: string;
    params: Record<string, number | string | boolean>;
  };

  type BuilderEdge = {
    id: string;
    source: string;
    target: string;
    sourceHandle?: string;
    targetHandle?: string;
  };

  type PortType = 'event' | 'number' | 'score';

  type NodePort = {
    handle: string;
    label: string;
    type: PortType;
    y: number;
  };

  type NodeSpec = {
    inputs: NodePort[];
    outputs: NodePort[];
  };

  const palette: Array<{ type: NodeType; title: string; hint: string }> = [
    // Triggers
    { type: 'OnBar', title: 'On Bar', hint: 'Trigger per bar' },
    // Data sources
    { type: 'Data', title: 'Price Bars', hint: 'OHLCV input' },
    { type: 'Constant', title: 'Constant', hint: 'Fixed numeric value (e.g. 30, 70)' },
    // Indicators
    { type: 'SMA', title: 'SMA', hint: 'Simple moving average' },
    { type: 'EMA', title: 'EMA', hint: 'Exponential moving average' },
    { type: 'RSI', title: 'RSI', hint: 'Relative strength index (0–100)' },
    { type: 'MACD', title: 'MACD', hint: 'MACD line, signal, and histogram' },
    { type: 'BollingerBands', title: 'Bollinger Bands', hint: 'Upper, middle, lower bands' },
    { type: 'ATR', title: 'ATR', hint: 'Average True Range (volatility)' },
    { type: 'Volume', title: 'Volume', hint: 'Bar volume as a number' },
    { type: 'Stochastic', title: 'Stochastic', hint: 'Stochastic %K and %D oscillator' },
    { type: 'ROC', title: 'ROC', hint: 'Rate of Change (% over N bars)' },
    { type: 'WilliamsR', title: 'Williams %R', hint: 'Momentum oscillator (-100 to 0)' },
    { type: 'CCI', title: 'CCI', hint: 'Commodity Channel Index' },
    { type: 'KDJ', title: 'KDJ', hint: 'Stochastic K/D/J (popular on Futu/Moomoo)' },
    { type: 'MFI', title: 'MFI', hint: 'Money Flow Index (volume-weighted RSI)' },
    { type: 'OBV', title: 'OBV', hint: 'On-Balance Volume (cumulative)' },
    { type: 'KST', title: 'KST', hint: 'Know Sure Thing — long-term momentum' },
    // Fundamentals
    { type: 'PE', title: 'P/E Ratio', hint: 'Price ÷ TTM EPS (from quarterly filings)' },
    { type: 'EPS', title: 'EPS (TTM)', hint: 'Trailing twelve-month diluted EPS' },
    { type: 'ROE', title: 'ROE', hint: 'Return on equity (latest filing)' },
    { type: 'DividendYield', title: 'Dividend Yield', hint: 'TTM dividend ÷ price (%)' },
    // Math
    { type: 'Add',      title: 'Add (A + B)',      hint: 'Numeric sum of two inputs' },
    { type: 'Subtract', title: 'Subtract (A − B)', hint: 'Numeric difference (A minus B)' },
    { type: 'Multiply', title: 'Multiply (A × B)', hint: 'Numeric product' },
    { type: 'Divide',   title: 'Divide (A ÷ B)',   hint: 'Numeric ratio; None when B ≈ 0' },
    // Conditions
    { type: 'IfAbove', title: 'If A > B', hint: 'True while A is above B' },
    { type: 'IfBelow', title: 'If A < B', hint: 'True while A is below B' },
    { type: 'IfCrossAbove', title: 'Cross Above', hint: 'Fires once when A crosses above B' },
    { type: 'IfCrossBelow', title: 'Cross Below', hint: 'Fires once when A crosses below B' },
    { type: 'And', title: 'And', hint: 'True when both inputs fire' },
    { type: 'Or',  title: 'Or',  hint: 'True when either input fires' },
    { type: 'Not', title: 'Not', hint: 'Invert a condition' },
    { type: 'TimeWindow', title: 'Time Window', hint: 'True while date is within [start, end]' },
    { type: 'Position',   title: 'Position',    hint: 'Branch on flat vs. holding state' },
    // Actions
    { type: 'Buy', title: 'Buy', hint: 'Enter position' },
    { type: 'Sell', title: 'Sell', hint: 'Exit position' },
    { type: 'StopLoss',     title: 'Stop Loss',     hint: 'Exit if price drops N% below entry' },
    { type: 'TakeProfit',   title: 'Take Profit',   hint: 'Exit if price rises N% above entry' },
    { type: 'TrailingStop', title: 'Trailing Stop', hint: 'Exit if price drops N% below high since entry' },
  ];

  // Universe-mode palette (factor strategy: cross-sectional rank of a universe)
  const universePalette: Array<{ type: NodeType; title: string; hint: string }> = [
    { type: 'Momentum',  title: 'Momentum',  hint: 'Trailing return (lookback − skip)' },
    { type: 'Reversal',  title: 'Reversal',  hint: 'Inverse short-term return (buy losers)' },
    { type: 'LowVol',    title: 'Low Vol',   hint: 'Negated realized volatility' },
    { type: 'Liquidity', title: 'Liquidity', hint: 'Average dollar volume' },
    { type: 'Value',     title: 'Value',     hint: 'Earnings yield (TTM EPS / price)' },
    { type: 'Rank',      title: 'Rank',      hint: 'Long top decile / short bottom decile' },
  ];

  let nodes = $state<BuilderNode[]>([]);
  let edges = $state<BuilderEdge[]>([]);
  let selectedId = $state<string | null>(null);
  let isDragging = $state(false);
  let dragNodeId = $state<string | null>(null);
  let dragOffset = $state({ x: 0, y: 0 });
  let isCanvasDragOver = $state(false);
  let pendingSourceId = $state<string | null>(null);
  let pendingSourceHandle = $state<string | null>(null);
  let viewport = $state({ x: 0, y: 0, scale: 1 });
  let isPanning = $state(false);
  let panWasStarted = $state(false);
  let panStart = $state({ x: 0, y: 0 });
  let panOrigin = $state({ x: 0, y: 0 });
  let didPan = $state(false);
  let showExport = $state(false);
  let showImport = $state(false);
  let showTemplates = $state(false);
  let showAiBuilder = $state(false);
  let exportJson = $state('');
  let importJson = $state('');

  // AI graph builder — prompts LLM to generate a graph from free-text idea.
  let aiPrompt = $state('');
  let aiLoading = $state(false);
  let aiError = $state<string | null>(null);
  type AiSettings = {
    mode?: 'single' | 'multi' | 'universe' | 'dataset' | null;
    symbol?: string | null;
    symbols?: string[] | null;
    universe?: string | null;
    startDate?: string | null;
    endDate?: string | null;
  };
  let aiResult = $state<{
    graph: { nodes: unknown[]; edges: unknown[] };
    notes: string;
    settings?: AiSettings;
  } | null>(null);
  let targetSymbol = $state('AAPL');
  let periodStart = $state('2013-01-01'); // YYYY-MM-DD — dense S&P 500 data starts here
  let periodEnd = $state('2018-12-31');   // YYYY-MM-DD — dense data ends here; clear for full range

  // Multi-symbol mode
  type UniverseMeta = { key: string; name: string; description: string; count: number; symbols: string[] };
  let assetMode = $state<'single' | 'multi' | 'universe' | 'dataset'>('single');

  // BYOD — user-uploaded datasets
  type UserDatasetSummary = {
    id: string;
    name: string;
    symbol: string;
    timeframe: string;
    rows_count: number;
    first_bar: string | null;
    last_bar: string | null;
  };
  let userDatasets = $state<UserDatasetSummary[]>([]);
  let selectedDatasetId = $state<string>('');
  let multiSymbolsText = $state('');        // comma-separated free text
  let selectedUniverse = $state<string>('');
  let universes = $state<UniverseMeta[]>([]);
  const importPlaceholder =
    '{\n' +
    '  "version": 0,\n' +
    '  "settings": { "symbol": "AAPL", "timeframe": "1D", "startDate": "2022-11-04", "endDate": "2023-03-04", "initialCapital": 10000 },\n' +
    '  "graph": { "nodes": [...], "edges": [...] }\n' +
    '}';

  const DRAFT_KEY = 'backtest:draft:v0';
  const IMPORT_KEY = 'backtest:import:v0';

  const selected = $derived(nodes.find((n) => n.id === selectedId) ?? null);

  // Seed missing params when a node is selected so the inspector always has defaults
  $effect(() => {
    if (selected?.type === 'Buy' && selected.params.amount == null) {
      updateNodeParam(selected.id, 'amount', 10);
    }
  });
  const nodeMap = $derived(new Map(nodes.map((n) => [n.id, n] as const)));
  const selectedEdges = $derived({
    incoming: selectedId ? edges.filter((e) => e.target === selectedId) : [],
    outgoing: selectedId ? edges.filter((e) => e.source === selectedId) : [],
  });

  const NODE_W = 224;
  const NODE_DEFAULT_PORT_Y = 26;

  const clamp = (value: number, min: number, max: number) =>
    Math.max(min, Math.min(max, value));

  const getCanvasRect = () =>
    document.getElementById('builder-canvas')?.getBoundingClientRect() ?? null;

  const focusNode = (nodeId: string) => {
    const node = nodeMap.get(nodeId);
    const rect = getCanvasRect();
    if (!node || !rect) return;
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const nextX = cx - (node.x + NODE_W / 2) * viewport.scale;
    const nextY = cy - (node.y + 34) * viewport.scale;
    viewport = { ...viewport, x: nextX, y: nextY };
  };

  const screenToWorld = (clientX: number, clientY: number) => {
    const rect = getCanvasRect();
    if (!rect) return { x: 0, y: 0 };
    const sx = clientX - rect.left;
    const sy = clientY - rect.top;
    return {
      x: (sx - viewport.x) / viewport.scale,
      y: (sy - viewport.y) / viewport.scale,
    };
  };

  const getNodeSpec = (type: NodeType): NodeSpec => {
    switch (type) {
      case 'OnBar':
        return {
          inputs: [],
          outputs: [{ handle: 'out', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'SMA':
      case 'EMA':
      case 'RSI':
      case 'ROC':
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [{ handle: 'out', label: 'value', type: 'number', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'ATR':
      case 'WilliamsR':
      case 'CCI':
      case 'MFI':
      case 'OBV':
        // H/L/C/V-based indicators — consume OHLCV from the DataFrame, no wirable input
        return {
          inputs: [],
          outputs: [{ handle: 'out', label: 'value', type: 'number', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'Volume':
        return {
          inputs: [],
          outputs: [{ handle: 'out', label: 'volume', type: 'number', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'MACD':
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [
            { handle: 'macd',      label: 'MACD',      type: 'number', y: 18 },
            { handle: 'signal',    label: 'Signal',    type: 'number', y: 38 },
            { handle: 'histogram', label: 'Histogram', type: 'number', y: 58 },
          ],
        };
      case 'BollingerBands':
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [
            { handle: 'upper',  label: 'Upper',  type: 'number', y: 18 },
            { handle: 'middle', label: 'Middle', type: 'number', y: 38 },
            { handle: 'lower',  label: 'Lower',  type: 'number', y: 58 },
          ],
        };
      case 'Stochastic':
        return {
          inputs: [],
          outputs: [
            { handle: 'k', label: '%K', type: 'number', y: 24 },
            { handle: 'd', label: '%D', type: 'number', y: 52 },
          ],
        };
      case 'KDJ':
        return {
          inputs: [],
          outputs: [
            { handle: 'k', label: 'K', type: 'number', y: 18 },
            { handle: 'd', label: 'D', type: 'number', y: 38 },
            { handle: 'j', label: 'J', type: 'number', y: 58 },
          ],
        };
      case 'KST':
        return {
          inputs: [],
          outputs: [
            { handle: 'kst',    label: 'KST',    type: 'number', y: 24 },
            { handle: 'signal', label: 'Signal', type: 'number', y: 52 },
          ],
        };
      case 'IfAbove':
      case 'IfBelow':
      case 'IfCrossAbove':
      case 'IfCrossBelow':
        return {
          inputs: [
            { handle: 'in', label: 'event', type: 'event', y: 18 },
            { handle: 'a', label: 'A', type: 'number', y: 38 },
            { handle: 'b', label: 'B', type: 'number', y: 58 },
          ],
          outputs: [
            { handle: 'true', label: 'true', type: 'event', y: 24 },
            { handle: 'false', label: 'false', type: 'event', y: 52 },
          ],
        };
      case 'And':
      case 'Or':
        return {
          inputs: [
            { handle: 'a', label: 'A', type: 'event', y: 18 },
            { handle: 'b', label: 'B', type: 'event', y: 38 },
          ],
          outputs: [
            { handle: 'true',  label: 'true',  type: 'event', y: 18 },
            { handle: 'false', label: 'false', type: 'event', y: 38 },
          ],
        };
      case 'Not':
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [
            { handle: 'true',  label: 'true',  type: 'event', y: 18 },
            { handle: 'false', label: 'false', type: 'event', y: 38 },
          ],
        };
      case 'TimeWindow':
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [
            { handle: 'true',  label: 'in',  type: 'event', y: 18 },
            { handle: 'false', label: 'out', type: 'event', y: 38 },
          ],
        };
      case 'Position':
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [
            { handle: 'flat',    label: 'flat',    type: 'event', y: 18 },
            { handle: 'holding', label: 'holding', type: 'event', y: 38 },
          ],
        };
      case 'StopLoss':
      case 'TakeProfit':
      case 'TrailingStop':
        // Event in → no output (they emit exit signals internally)
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [],
        };
      case 'Constant':
        return {
          inputs: [],
          outputs: [{ handle: 'out', label: 'value', type: 'number', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'Add':
      case 'Subtract':
      case 'Multiply':
      case 'Divide':
        return {
          inputs: [
            { handle: 'a', label: 'A', type: 'number', y: 18 },
            { handle: 'b', label: 'B', type: 'number', y: 38 },
          ],
          outputs: [{ handle: 'out', label: 'value', type: 'number', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'Buy':
      case 'Sell':
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [],
        };
      case 'PE':
      case 'EPS':
      case 'ROE':
      case 'DividendYield':
        // Fundamental indicators — no wirable input, a single numeric output
        return {
          inputs: [],
          outputs: [{ handle: 'out', label: 'value', type: 'number', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'Momentum':
      case 'Reversal':
      case 'LowVol':
      case 'Liquidity':
      case 'Value':
        // Factor nodes — compute a cross-sectional score from OHLCV, no wirable input
        return {
          inputs: [],
          outputs: [{ handle: 'out', label: 'score', type: 'score', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'Rank':
        return {
          inputs: [{ handle: 'in', label: 'score', type: 'score', y: NODE_DEFAULT_PORT_Y }],
          outputs: [],
        };
      case 'Data':
        // Live close of the current bar — emits every bar like Volume/OHLCV
        // indicators, so no event input is required.
        return {
          inputs: [],
          outputs: [{ handle: 'out', label: 'close', type: 'number', y: NODE_DEFAULT_PORT_Y }],
        };
      default:
        return { inputs: [], outputs: [] };
    }
  };

  const getDefaultOutputHandle = (type: NodeType) =>
    getNodeSpec(type).outputs[0]?.handle ?? null;

  const getOutputPort = (type: NodeType, handle?: string | null) => {
    const spec = getNodeSpec(type);
    if (spec.outputs.length === 0) return null;
    return (
      spec.outputs.find((p) => p.handle === handle) ??
      spec.outputs[0] ??
      null
    );
  };

  const getInputPort = (type: NodeType, handle?: string | null) => {
    const spec = getNodeSpec(type);
    if (spec.inputs.length === 0) return null;
    return (
      spec.inputs.find((p) => p.handle === handle) ?? spec.inputs[0] ?? null
    );
  };

  const pickTargetHandle = (targetId: string, outType: PortType) => {
    const target = nodeMap.get(targetId);
    if (!target) return null;
    const spec = getNodeSpec(target.type);
    const used = new Set(
      edges
        .filter((e) => e.target === targetId)
        .map((e) => e.targetHandle)
        .filter((h): h is string => Boolean(h))
    );
    return spec.inputs.find((p) => p.type === outType && !used.has(p.handle))
      ?.handle ?? null;
  };

  const defaultParamsFor = (type: NodeType): BuilderNode['params'] => {
    switch (type) {
      case 'OnBar':
        return { timeframe: '1D' };
      case 'SMA':
      case 'EMA':
        return { period: 20 };
      case 'RSI':
        return { period: 14, overbought: 70, oversold: 30 };
      case 'MACD':
        return { fast: 12, slow: 26, signal: 9 };
      case 'BollingerBands':
        return { period: 20, std: 2 };
      case 'ATR':
        return { period: 14 };
      case 'Stochastic':
        return { k: 14, d: 3 };
      case 'ROC':
        return { period: 10 };
      case 'WilliamsR':
        return { period: 14 };
      case 'CCI':
        return { period: 20 };
      case 'KDJ':
        return { length: 9, signal: 3 };
      case 'MFI':
        return { period: 14 };
      case 'OBV':
        return {};
      case 'KST':
        return {};
      case 'And':
      case 'Or':
      case 'Not':
        return {};
      case 'TimeWindow':
        return { start: '2015-01-01', end: '2020-12-31' };
      case 'Position':
        return {};
      case 'StopLoss':
        return { pct: 2.0 };
      case 'TakeProfit':
        return { pct: 5.0 };
      case 'TrailingStop':
        return { pct: 3.0 };
      case 'Momentum':
        return { lookback: 252, skip: 21 };
      case 'Reversal':
        return { period: 21 };
      case 'LowVol':
        return { period: 63 };
      case 'Liquidity':
        return { period: 60 };
      case 'Value':
        return {};
      case 'PE':
      case 'EPS':
      case 'ROE':
      case 'DividendYield':
        return {};
      case 'Rank':
        return { top_pct: 0.2, bottom_pct: 0.2, rebalance_days: 21, mode: 'long_only' };
      case 'Buy':
        return { size_type: 'units', amount: 10 };
      case 'Sell':
        return { size_type: 'all' };
      case 'Constant':
        return { value: 30 };
      case 'Add':
      case 'Subtract':
      case 'Multiply':
      case 'Divide':
        return {};
      case 'Data':
        return { timeframe: '1D' };
      default:
        return {};
    }
  };

  const newId = (prefix: string) =>
    globalThis.crypto?.randomUUID?.() ?? `${prefix}_${Date.now()}_${Math.random()}`;

  const addNode = (type: NodeType, position?: { x: number; y: number }, params?: BuilderNode['params']) => {
    const id = newId('node');
    const newNode: BuilderNode = {
      id,
      type,
      x: position?.x ?? 80 + nodes.length * 18,
      y: position?.y ?? 60 + nodes.length * 18,
      label: type,
      params: params ?? defaultParamsFor(type),
    };
    nodes = [...nodes, newNode];
    selectedId = id;
    return id;
  };

  const deleteSelected = () => {
    if (!selectedId) return;
    nodes = nodes.filter((n) => n.id !== selectedId);
    edges = edges.filter(
      (e) => e.source !== selectedId && e.target !== selectedId
    );
    if (pendingSourceId === selectedId) {
      pendingSourceId = null;
      pendingSourceHandle = null;
    }
    selectedId = null;
  };

  const deleteEdge = (edgeId: string) => {
    edges = edges.filter((e) => e.id !== edgeId);
  };

  const updateNode = (id: string, patch: Partial<BuilderNode>) => {
    nodes = nodes.map((n) => (n.id === id ? { ...n, ...patch } : n));
  };

  const updateNodeParam = (id: string, key: string, value: BuilderNode['params'][string]) => {
    nodes = nodes.map((n) =>
      n.id === id ? { ...n, params: { ...n.params, [key]: value } } : n
    );
  };

  const onCanvasPointerMove = (event: PointerEvent) => {
    if (isPanning) {
      const dx = event.clientX - panStart.x;
      const dy = event.clientY - panStart.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) didPan = true;
      viewport = { ...viewport, x: panOrigin.x + dx, y: panOrigin.y + dy };
      return;
    }

    if (!isDragging || !dragNodeId) return;
    const pt = screenToWorld(event.clientX, event.clientY);
    const x = Math.max(0, pt.x - dragOffset.x);
    const y = Math.max(0, pt.y - dragOffset.y);
    updateNode(dragNodeId, { x, y });
  };

  const stopDragging = () => {
    isDragging = false;
    dragNodeId = null;
    isPanning = false;
    panWasStarted = false;
  };

  const connectNodes = (sourceId: string, sourceHandle: string, targetId: string, targetHandle: string) => {
    if (sourceId === targetId) return;
    const hasNodes = nodeMap.has(sourceId) && nodeMap.has(targetId);
    if (!hasNodes) return;
    const exists = edges.some(
      (e) =>
        e.source === sourceId &&
        e.target === targetId &&
        e.sourceHandle === sourceHandle &&
        e.targetHandle === targetHandle
    );
    if (exists) return;
    const id = newId('edge');
    edges = [...edges, { id, source: sourceId, target: targetId, sourceHandle, targetHandle }];
  };

  const onNodePointerDown = (event: PointerEvent, nodeId: string) => {
    selectedId = nodeId;

    if (pendingSourceId) {
      if (pendingSourceId === nodeId) {
        pendingSourceId = null;
        pendingSourceHandle = null;
        return;
      }
      const sourceNode = nodeMap.get(pendingSourceId);
      const targetNode = nodeMap.get(nodeId);
      if (!sourceNode || !targetNode) return;

      const resolvedSourceHandle =
        pendingSourceHandle ?? getDefaultOutputHandle(sourceNode.type);
      if (!resolvedSourceHandle) return;

      const outPort = getOutputPort(sourceNode.type, resolvedSourceHandle);
      if (!outPort) return;

      const resolvedTargetHandle = pickTargetHandle(nodeId, outPort.type);
      if (!resolvedTargetHandle) return;

      connectNodes(
        pendingSourceId,
        resolvedSourceHandle,
        nodeId,
        resolvedTargetHandle
      );

      pendingSourceId = null;
      pendingSourceHandle = null;
      return;
    }

    isDragging = true;
    dragNodeId = nodeId;
    const pt = screenToWorld(event.clientX, event.clientY);
    const node = nodeMap.get(nodeId);
    dragOffset = node ? { x: pt.x - node.x, y: pt.y - node.y } : { x: 0, y: 0 };
  };

  const getEdgePath = (edge: BuilderEdge) => {
    const s = nodeMap.get(edge.source);
    const t = nodeMap.get(edge.target);
    if (!s || !t) return null;
    const outPort = getOutputPort(s.type, edge.sourceHandle);
    const inPort = getInputPort(t.type, edge.targetHandle);
    const x1 = s.x + NODE_W;
    const y1 = s.y + (outPort?.y ?? NODE_DEFAULT_PORT_Y);
    const x2 = t.x;
    const y2 = t.y + (inPort?.y ?? NODE_DEFAULT_PORT_Y);
    const dx = Math.max(60, Math.min(160, (x2 - x1) / 2));
    const c1x = x1 + dx;
    const c2x = x2 - dx;
    const d = `M ${x1} ${y1} C ${c1x} ${y1} ${c2x} ${y2} ${x2} ${y2}`;
    return { d };
  };

  type ValidationIssue = {
    level: 'error' | 'warning';
    message: string;
    nodeId?: string;
    edgeId?: string;
  };

  const FACTOR_TYPES: readonly NodeType[] = ['Momentum', 'Reversal', 'LowVol', 'Liquidity', 'Value'];

  const validateUniverse = (
    currentNodes: BuilderNode[],
    currentEdges: BuilderEdge[]
  ): ValidationIssue[] => {
    const issues: ValidationIssue[] = [];
    const factors = currentNodes.filter((n) => (FACTOR_TYPES as string[]).includes(n.type));
    const ranks = currentNodes.filter((n) => n.type === 'Rank');
    const stragglers = currentNodes.filter(
      (n) => !(FACTOR_TYPES as string[]).includes(n.type) && n.type !== 'Rank'
    );

    for (const n of stragglers) {
      issues.push({
        level: 'error',
        nodeId: n.id,
        message: `Universe mode only supports factor + Rank blocks (remove ${n.type}).`,
      });
    }

    if (factors.length === 0) {
      issues.push({ level: 'error', message: 'Add a factor block (Momentum, Reversal, Low Vol, or Liquidity).' });
    } else if (factors.length > 1) {
      issues.push({ level: 'error', message: 'Universe mode supports only one factor block.' });
    }
    if (ranks.length === 0) {
      issues.push({ level: 'error', message: 'Add a Rank block to convert scores into long/short weights.' });
    } else if (ranks.length > 1) {
      issues.push({ level: 'error', message: 'Universe mode supports only one Rank block.' });
    }

    if (factors.length === 1 && ranks.length === 1) {
      const wired = currentEdges.some(
        (e) => e.source === factors[0].id && e.target === ranks[0].id
      );
      if (!wired) {
        issues.push({
          level: 'error',
          message: 'Wire the factor block\'s score output to the Rank block\'s input.',
        });
      }
    }

    // Rank param sanity
    for (const r of ranks) {
      const top = Number(r.params.top_pct ?? 0.2);
      const bot = Number(r.params.bottom_pct ?? 0.2);
      if (!(top > 0 && top <= 1)) {
        issues.push({ level: 'error', nodeId: r.id, message: 'Rank top_pct must be in (0, 1].' });
      }
      if (!(bot > 0 && bot <= 1)) {
        issues.push({ level: 'error', nodeId: r.id, message: 'Rank bottom_pct must be in (0, 1].' });
      }
      if (Number(r.params.rebalance_days ?? 21) < 1) {
        issues.push({ level: 'error', nodeId: r.id, message: 'Rank rebalance_days must be at least 1.' });
      }
    }

    return issues;
  };

  const validate = (
    currentNodes: BuilderNode[],
    currentEdges: BuilderEdge[]
  ): ValidationIssue[] => {
    if (assetMode === 'universe') return validateUniverse(currentNodes, currentEdges);

    const issues: ValidationIssue[] = [];
    const map = new Map(currentNodes.map((n) => [n.id, n] as const));

    for (const edge of currentEdges) {
      const s = map.get(edge.source);
      const t = map.get(edge.target);
      if (!s || !t) {
        issues.push({
          level: 'error',
          edgeId: edge.id,
          message: 'A connection points to a missing block.',
        });
        continue;
      }
      const outPort = getOutputPort(s.type, edge.sourceHandle ?? null);
      const inPort = getInputPort(t.type, edge.targetHandle ?? null);
      if (!outPort || !inPort) {
        issues.push({
          level: 'error',
          edgeId: edge.id,
          message: 'A connection uses an invalid handle.',
        });
        continue;
      }
      if (outPort.type !== inPort.type) {
        issues.push({
          level: 'error',
          edgeId: edge.id,
          message: `Type mismatch: ${outPort.type} → ${inPort.type}.`,
        });
      }
    }

    const triggers = currentNodes.filter((n) => n.type === 'OnBar');
    if (triggers.length === 0) {
      issues.push({
        level: 'error',
        message: 'Add a Trigger (e.g. OnBar) to start the flow.',
      });
    }

    const requiredInputsFor = (node: BuilderNode) => getNodeSpec(node.type).inputs;
    const incomingByTarget = new Map<string, BuilderEdge[]>();
    for (const e of currentEdges) {
      const arr = incomingByTarget.get(e.target) ?? [];
      arr.push(e);
      incomingByTarget.set(e.target, arr);
    }

    for (const node of currentNodes) {
      const requiredInputs = requiredInputsFor(node);
      if (requiredInputs.length === 0) continue;

      const incoming = incomingByTarget.get(node.id) ?? [];
      for (const input of requiredInputs) {
        const has = incoming.some((e) => e.targetHandle === input.handle);
        if (!has) {
          issues.push({
            level: 'error',
            nodeId: node.id,
            message: `Missing input: ${node.label} · ${input.label}`,
          });
        }
      }

      if (node.type === 'Constant' && (typeof node.params.value !== 'number' || isNaN(Number(node.params.value)))) {
        issues.push({
          level: 'error',
          nodeId: node.id,
          message: 'Constant value must be a number.',
        });
      }

      if (['SMA', 'EMA', 'RSI', 'BollingerBands', 'ATR', 'ROC', 'WilliamsR', 'CCI', 'MFI'].includes(node.type) && typeof node.params.period !== 'number') {
        issues.push({
          level: 'error',
          nodeId: node.id,
          message: 'Period must be a number.',
        });
      }
      if (['SMA', 'EMA', 'RSI', 'BollingerBands', 'ATR', 'ROC', 'WilliamsR', 'CCI', 'MFI'].includes(node.type) && Number(node.params.period) <= 0) {
        issues.push({
          level: 'error',
          nodeId: node.id,
          message: 'Period must be greater than 0.',
        });
      }
      if (node.type === 'KDJ') {
        if (!Number(node.params.length) || Number(node.params.length) <= 0) {
          issues.push({ level: 'error', nodeId: node.id, message: 'KDJ length must be a positive number.' });
        }
        if (!Number(node.params.signal) || Number(node.params.signal) <= 0) {
          issues.push({ level: 'error', nodeId: node.id, message: 'KDJ signal must be a positive number.' });
        }
      }
      if (['StopLoss', 'TakeProfit', 'TrailingStop'].includes(node.type)) {
        const pct = Number(node.params.pct);
        if (!pct || pct <= 0) {
          issues.push({ level: 'error', nodeId: node.id, message: `${node.type} percentage must be > 0.` });
        }
      }
      if (node.type === 'TimeWindow') {
        const start = String(node.params.start ?? '');
        const end   = String(node.params.end ?? '');
        const dateRe = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRe.test(start) || !dateRe.test(end)) {
          issues.push({ level: 'error', nodeId: node.id, message: 'TimeWindow start/end must be YYYY-MM-DD.' });
        } else if (start > end) {
          issues.push({ level: 'error', nodeId: node.id, message: 'TimeWindow start must be ≤ end.' });
        }
      }
      if (node.type === 'MACD') {
        const fast = Number(node.params.fast), slow = Number(node.params.slow);
        if (!fast || !slow || fast <= 0 || slow <= 0) {
          issues.push({ level: 'error', nodeId: node.id, message: 'MACD fast and slow periods must be positive numbers.' });
        } else if (fast >= slow) {
          issues.push({ level: 'error', nodeId: node.id, message: 'MACD fast period must be less than slow period.' });
        }
      }
      if (node.type === 'Stochastic') {
        if (!Number(node.params.k) || Number(node.params.k) <= 0) {
          issues.push({ level: 'error', nodeId: node.id, message: 'Stochastic K period must be a positive number.' });
        }
        if (!Number(node.params.d) || Number(node.params.d) <= 0) {
          issues.push({ level: 'error', nodeId: node.id, message: 'Stochastic D period must be a positive number.' });
        }
      }
      if (node.type === 'OnBar' && typeof node.params.timeframe !== 'string') {
        issues.push({
          level: 'error',
          nodeId: node.id,
          message: 'Timeframe must be a string (e.g. 1D, 1H).',
        });
      }
      if (node.type === 'OnBar' && String(node.params.timeframe ?? '').trim().length === 0) {
        issues.push({
          level: 'error',
          nodeId: node.id,
          message: 'Timeframe cannot be empty.',
        });
      }
    }

    // Reachability: ensure at least one Action is reachable via event edges from a Trigger.
    const outEventEdges = (sourceId: string) =>
      currentEdges.filter((e) => e.source === sourceId);

    const eventReachable = new Set<string>();
    const queue: string[] = [];

    for (const trigger of triggers) {
      eventReachable.add(trigger.id);
      queue.push(trigger.id);
    }

    while (queue.length > 0) {
      const srcId = queue.shift()!;
      const src = map.get(srcId);
      if (!src) continue;
      for (const e of outEventEdges(srcId)) {
        const outPort = getOutputPort(src.type, e.sourceHandle ?? null);
        const tgt = map.get(e.target);
        if (!outPort || !tgt) continue;
        const inPort = getInputPort(tgt.type, e.targetHandle ?? null);
        if (!inPort) continue;
        if (outPort.type !== 'event' || inPort.type !== 'event') continue;
        if (!eventReachable.has(e.target)) {
          eventReachable.add(e.target);
          queue.push(e.target);
        }
      }
    }

    const actions = currentNodes.filter((n) => n.type === 'Buy' || n.type === 'Sell');
    const reachableActions = actions.filter((a) => eventReachable.has(a.id));

    if (actions.length === 0) {
      issues.push({
        level: 'error',
        message: 'Add at least one Action (Buy/Sell).',
      });
    } else if (reachableActions.length === 0) {
      issues.push({
        level: 'error',
        message: 'No action is reachable from a Trigger. Connect the flow so an event reaches Buy/Sell.',
      });
    }

    return issues;
  };

  const issues = $derived(validate(nodes, edges));
  const errors = $derived(issues.filter((i) => i.level === 'error'));
  const hasErrors = $derived(errors.length > 0);

  // Maximum warm-up bars required by any indicator node in the graph.
  // SMA/EMA/RSI need `period` bars before they can produce a value.
  const maxWarmupBars = $derived(
    nodes.reduce((max, n) => {
      let needed = 0;
      if (n.type === 'SMA' || n.type === 'EMA') needed = Number(n.params.period) || 0;
      else if (n.type === 'RSI') needed = (Number(n.params.period) || 0) + 1;
      else if (n.type === 'ATR' || n.type === 'BollingerBands') needed = Number(n.params.period) || 0;
      else if (n.type === 'MACD') needed = (Number(n.params.slow) || 26) + (Number(n.params.signal) || 9) - 1;
      else if (n.type === 'Stochastic') needed = (Number(n.params.k) || 14) + (Number(n.params.d) || 3);
      else if (n.type === 'ROC') needed = (Number(n.params.period) || 0) + 1;
      else if (n.type === 'WilliamsR') needed = Number(n.params.period) || 0;
      else if (n.type === 'CCI') needed = Number(n.params.period) || 0;
      else if (n.type === 'MFI') needed = Number(n.params.period) || 0;
      else if (n.type === 'KDJ') needed = (Number(n.params.length) || 9) + (Number(n.params.signal) || 3);
      else if (n.type === 'KST') needed = 30 + 9; // roc4=30 + signal=9 default warm-up
      return Math.max(max, needed);
    }, 0)
  );

  const issueForSelected = $derived(
    selectedId ? issues.filter((i) => i.nodeId === selectedId) : []
  );

  const getCanvasDropPosition = (event: DragEvent) => {
    const pt = screenToWorld(event.clientX, event.clientY);
    return { x: Math.max(0, pt.x - NODE_W / 2), y: Math.max(0, pt.y - 28) };
  };

  const onPaletteDragStart = (event: DragEvent, type: NodeType) => {
    if (!event.dataTransfer) return;
    event.dataTransfer.setData('application/x-backtest-node-type', type);
    event.dataTransfer.effectAllowed = 'copy';
  };

  const onCanvasDragOver = (event: DragEvent) => {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
    isCanvasDragOver = true;
  };

  const onCanvasDrop = (event: DragEvent) => {
    event.preventDefault();
    isCanvasDragOver = false;
    const type = event.dataTransfer?.getData('application/x-backtest-node-type') as
      | NodeType
      | '';
    if (!type) return;
    addNode(type, getCanvasDropPosition(event));
  };

  const onCanvasDragLeave = (event: DragEvent) => {
    if (event.currentTarget === event.target) isCanvasDragOver = false;
  };

  const onCanvasWheel = (event: WheelEvent) => {
    event.preventDefault();
    const rect = getCanvasRect();
    if (!rect) return;

    const sx = event.clientX - rect.left;
    const sy = event.clientY - rect.top;
    const worldX = (sx - viewport.x) / viewport.scale;
    const worldY = (sy - viewport.y) / viewport.scale;

    const factor = event.deltaY > 0 ? 0.9 : 1.1;
    const nextScale = clamp(viewport.scale * factor, 0.3, 2.5);
    const nextX = sx - worldX * nextScale;
    const nextY = sy - worldY * nextScale;
    viewport = { x: nextX, y: nextY, scale: nextScale };
  };

  const resetView = () => {
    viewport = { x: 0, y: 0, scale: 1 };
  };

  type StrategyPayloadV0 = {
    version: 0;
    settings: {
      symbol?: string;
      timeframe?: string;
      startDate?: string;
      endDate?: string;
      initialCapital?: number;
      feesBps?: number;
      slippageBps?: number;
    };
    graph: {
      nodes: BuilderNode[];
      edges: BuilderEdge[];
    };
  };

  const buildExportPayload = (): StrategyPayloadV0 => {
    const trigger = nodes.find((n) => n.type === 'OnBar');
    const timeframe =
      trigger && typeof trigger.params.timeframe === 'string'
        ? trigger.params.timeframe
        : undefined;
    return {
      version: 0,
      settings: {
        symbol: targetSymbol.trim() ? targetSymbol.trim().toUpperCase() : undefined,
        timeframe,
        startDate: periodStart.trim() ? periodStart.trim() : undefined,
        endDate: periodEnd.trim() ? periodEnd.trim() : undefined,
        initialCapital: 10000,
        feesBps: 0,
        slippageBps: 0,
      },
      graph: { nodes, edges },
    };
  };

  const openExport = async () => {
    exportJson = JSON.stringify(buildExportPayload(), null, 2);
    showExport = true;
    showImport = false;
  };

  const copyExport = async () => {
    try {
      await navigator.clipboard.writeText(exportJson);
      toast.success('Copied strategy JSON');
    } catch {
      toast.error('Copy failed (clipboard not available)');
    }
  };

  const downloadExport = () => {
    try {
      const blob = new Blob([exportJson], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `strategy_v0_${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success('Downloaded strategy JSON');
    } catch {
      toast.error('Download failed');
    }
  };

  const openImport = () => {
    showImport = true;
    showExport = false;
    showTemplates = false;
    importJson = '';
  };

  const openTemplates = () => {
    showTemplates = true;
    showImport = false;
    showExport = false;
  };

  const openAiBuilder = () => {
    showAiBuilder = true;
    showImport = false;
    showExport = false;
    showTemplates = false;
    aiError = null;
    aiResult = null;
  };

  const submitAiPrompt = async () => {
    if (aiLoading) return;
    const trimmed = aiPrompt.trim();
    if (trimmed.length < 4) {
      aiError = 'Describe your idea in at least a few words.';
      return;
    }
    const token = localStorage.getItem('token');
    if (!token) {
      toast.error('Please log in first.');
      goto('/login');
      return;
    }
    aiLoading = true;
    aiError = null;
    aiResult = null;
    try {
      const res = await fetch(`${BACKEND}/ai/build-graph`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ prompt: trimmed }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const msg = body?.detail ?? `Request failed (${res.status})`;
        aiError = typeof msg === 'string' ? msg : 'Generation failed.';
        return;
      }
      aiResult = await res.json();
    } catch (err) {
      aiError = err instanceof Error ? err.message : 'Could not reach backend.';
    } finally {
      aiLoading = false;
    }
  };

  const applyAiGraph = () => {
    if (!aiResult) return;
    try {
      // Apply asset settings first so the picker reflects the LLM's intent
      // before the graph loads. Only override fields the LLM actually set —
      // unset fields inherit whatever the canvas already has.
      const s = aiResult.settings ?? {};
      if (s.mode) assetMode = s.mode;
      if (s.universe) selectedUniverse = s.universe;
      if (s.symbols && s.symbols.length > 0) {
        multiSymbolsText = s.symbols.join(', ');
      }
      if (s.symbol) targetSymbol = s.symbol;
      if (s.startDate) periodStart = s.startDate;
      if (s.endDate) periodEnd = s.endDate;

      applyImportedPayload(aiResult.graph);
      showAiBuilder = false;
      toast.success('Applied AI-generated graph');
      aiPrompt = '';
      aiResult = null;
    } catch (err) {
      aiError = err instanceof Error ? err.message : 'Failed to apply graph';
    }
  };

  const applyTemplate = (templateId: string) => {
    const template = STRATEGY_TEMPLATES.find((t) => t.id === templateId);
    if (!template) return;
    try {
      // Auto-switch asset mode if the template doesn't belong to the current
      // mode (e.g. opening a universe template from the single-symbol picker).
      // Prevents validation from immediately flagging the imported nodes.
      if (template.modes.length > 0 && !template.modes.includes(assetMode)) {
        assetMode = template.modes[0];
      }
      applyImportedPayload(template.payload);
      showTemplates = false;
      toast.success(`Loaded template: ${template.name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load template');
    }
  };

  // Templates filtered to the currently-selected asset mode.  The picker
  // is mode-scoped so universe mode sees factor/rank templates and
  // single/multi/dataset see the indicator-based palette templates.
  const visibleTemplates = $derived(
    STRATEGY_TEMPLATES.filter((t) => t.modes.includes(assetMode))
  );

  const isRecord = (v: unknown): v is Record<string, unknown> =>
    typeof v === 'object' && v !== null;

  const safeNumber = (v: unknown, fallback: number) =>
    typeof v === 'number' && Number.isFinite(v) ? v : fallback;

  const safeString = (v: unknown, fallback: string) =>
    typeof v === 'string' ? v : fallback;

  const normalizeNode = (raw: unknown): BuilderNode | null => {
    if (!isRecord(raw)) return null;
    const id = safeString(raw.id, newId('node'));
    const type = safeString(raw.type, '') as NodeType;
    const allowedTypes: NodeType[] = [
      'OnBar',
      'Data',
      'SMA',
      'EMA',
      'RSI',
      'MACD',
      'BollingerBands',
      'ATR',
      'Volume',
      'Stochastic',
      'ROC',
      'WilliamsR',
      'CCI',
      'KDJ',
      'MFI',
      'OBV',
      'KST',
      'And',
      'Or',
      'Not',
      'TimeWindow',
      'Position',
      'StopLoss',
      'TakeProfit',
      'TrailingStop',
      'IfAbove',
      'IfBelow',
      'IfCrossAbove',
      'IfCrossBelow',
      'Constant',
      'Buy',
      'Sell',
      'Momentum',
      'Reversal',
      'LowVol',
      'Liquidity',
      'Rank',
    ];
    if (!allowedTypes.includes(type)) return null;
    return {
      id,
      type,
      x: safeNumber(raw.x, safeNumber((raw as any).position?.x, 80)),
      y: safeNumber(raw.y, safeNumber((raw as any).position?.y, 60)),
      label: safeString(raw.label, type),
      params: isRecord(raw.params) ? (raw.params as BuilderNode['params']) : {},
    };
  };

  const normalizeEdge = (raw: unknown): BuilderEdge | null => {
    if (!isRecord(raw)) return null;
    const source = safeString(raw.source, '');
    const target = safeString(raw.target, '');
    if (!source || !target) return null;
    return {
      id: safeString(raw.id, newId('edge')),
      source,
      target,
      sourceHandle: typeof raw.sourceHandle === 'string' ? raw.sourceHandle : undefined,
      targetHandle: typeof raw.targetHandle === 'string' ? raw.targetHandle : undefined,
    };
  };

  const applyImportedPayload = (data: unknown) => {
    if (!isRecord(data)) throw new Error('Invalid JSON root');
    const settings = isRecord((data as any).settings) ? ((data as any).settings as Record<string, unknown>) : null;
    const graph = isRecord(data.graph) ? data.graph : data;
    if (!isRecord(graph)) throw new Error('Missing graph');

    const rawNodes = Array.isArray((graph as any).nodes) ? (graph as any).nodes : [];
    const rawEdges = Array.isArray((graph as any).edges) ? (graph as any).edges : [];

    const nextNodes: BuilderNode[] = rawNodes
      .map(normalizeNode)
      .filter((n: BuilderNode | null): n is BuilderNode => Boolean(n));

    if (nextNodes.length === 0) throw new Error('No valid nodes found');

    const nodeIds = new Set(nextNodes.map((n) => n.id));
    const nextEdges: BuilderEdge[] = rawEdges
      .map(normalizeEdge)
      .filter((e: BuilderEdge | null): e is BuilderEdge => Boolean(e))
      .filter((e: BuilderEdge) => nodeIds.has(e.source) && nodeIds.has(e.target));

    nodes = nextNodes;
    edges = nextEdges;
    selectedId = null;
    pendingSourceId = null;
    pendingSourceHandle = null;
    loadedStrategyId = null;
    loadedStrategyName = '';
    resetView();

    if (settings) {
      targetSymbol = safeString(settings.symbol, targetSymbol);
      const start = settings.startDate;
      const end = settings.endDate;
      periodStart = typeof start === 'string' ? start : '';
      periodEnd = typeof end === 'string' ? end : '';
    }
  };

  const doImport = () => {
    try {
      const parsed = JSON.parse(importJson);
      applyImportedPayload(parsed);
      showImport = false;
      toast.success('Imported strategy JSON');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Import failed');
    }
  };

  const saveDraft = () => {
    try {
      const payload = buildExportPayload();
      localStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
      toast.success('Saved draft');
    } catch {
      toast.error('Save draft failed');
    }
  };

  const loadDraft = () => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) {
        toast.error('No draft found');
        return;
      }
      applyImportedPayload(JSON.parse(raw));
      toast.success('Loaded draft');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Load draft failed');
    }
  };

  const clearDraft = () => {
    localStorage.removeItem(DRAFT_KEY);
    toast.success('Cleared draft');
  };

  onMount(() => {
    // Load available universes (public endpoint — no auth needed)
    fetch(`${BACKEND}/market/universes`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { universes: UniverseMeta[] } | null) => {
        if (data?.universes) universes = data.universes;
      })
      .catch(() => { /* offline/backend down — multi-symbol still usable via free text */ });

    // Fetch user's uploaded datasets (ignore failure — BYOD is optional).
    const token = localStorage.getItem('token');
    if (token) {
      fetch(`${BACKEND}/user/datasets`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => (r.ok ? r.json() : []))
        .then((list: UserDatasetSummary[]) => {
          userDatasets = list;
        })
        .catch(() => { /* offline — dataset picker stays empty */ });
    }

    const params = new URLSearchParams(window.location.search);
    const datasetIdParam = params.get('datasetId');
    if (datasetIdParam) {
      assetMode = 'dataset';
      selectedDatasetId = datasetIdParam;
    }

    const strategyId = params.get('strategyId');
    if (strategyId) {
      loadStrategy(strategyId);
      return;
    }
    try {
      const raw = sessionStorage.getItem(IMPORT_KEY);
      if (raw) {
        applyImportedPayload(JSON.parse(raw));
        sessionStorage.removeItem(IMPORT_KEY);
        toast.success('Duplicated into builder');
      }
    } catch {
      sessionStorage.removeItem(IMPORT_KEY);
    }

    startTourIfUnseen();
  });



  // --- Save / Load strategy ---
  let showSave = $state(false);
  let showLoad = $state(false);
  let saveName = $state('');
  let savedStrategies = $state<{ id: string; name: string; updated_at: string }[]>([]);
  let loadedStrategyId = $state<string | null>(null);
  let loadedStrategyName = $state('');
  let isSaving = $state(false);

  const openSave = () => {
    saveName = loadedStrategyId ? loadedStrategyName : '';
    showSave = true;
    showLoad = false;
    showExport = false;
    showImport = false;
  };

  const openLoad = async () => {
    const token = localStorage.getItem('token');
    if (!token) { toast.error('Not logged in'); goto('/login'); return; }
    try {
      const res = await fetch(`${BACKEND}/strategies`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { toast.error('Could not load strategies'); return; }
      savedStrategies = await res.json();
    } catch {
      toast.error('Could not reach backend');
      return;
    }
    showLoad = true;
    showSave = false;
    showExport = false;
    showImport = false;
  };

  const saveStrategy = async () => {
    if (!saveName.trim()) { toast.error('Enter a strategy name'); return; }
    if (isSaving) return;
    const token = localStorage.getItem('token');
    if (!token) { toast.error('Not logged in'); goto('/login'); return; }

    isSaving = true;
    const payload = buildExportPayload();
    const name = saveName.trim();
    try {
      let res: Response;
      if (loadedStrategyId) {
        res = await fetch(`${BACKEND}/strategies/${loadedStrategyId}`, {
          method: 'PUT',
          headers: { 'content-type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ name, graph_json: payload }),
        });
      } else {
        res = await fetch(`${BACKEND}/strategies`, {
          method: 'POST',
          headers: { 'content-type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ name, graph_json: payload }),
        });
      }
      if (!res.ok) { toast.error('Save failed'); return; }
      const saved = await res.json() as { id: string; name: string };
      loadedStrategyId = saved.id;
      loadedStrategyName = saved.name;
      toast.success(`Strategy "${name}" saved`);
      showSave = false;
    } catch {
      toast.error('Could not reach backend');
    } finally {
      isSaving = false;
    }
  };

  const loadStrategy = async (id: string) => {
    const token = localStorage.getItem('token');
    if (!token) { toast.error('Not logged in'); goto('/login'); return; }
    try {
      const res = await fetch(`${BACKEND}/strategies/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { toast.error('Could not load strategy'); return; }
      const data = await res.json() as { id: string; name: string; graph_json: { version: number; settings: Record<string, unknown>; graph: { nodes: unknown[]; edges: unknown[] } } };
      applyImportedPayload(data.graph_json);
      loadedStrategyId = data.id;
      loadedStrategyName = data.name;
      showLoad = false;
      toast.success('Strategy loaded');
    } catch {
      toast.error('Could not reach backend');
    }
  };

  type ParamOverride = { nodeId: string; paramKey: string; value: number };

  const buildSubmitBody = (override?: ParamOverride): {
    body: Record<string, unknown>;
    symbolsList?: string[];
    universeKey?: string;
  } | null => {
    const exportPayload = buildExportPayload();

    let symbolsList: string[] | undefined;
    let universeKey: string | undefined;

    // BYOD short-circuit — dataset_id supersedes symbol/symbols/universe.
    if (assetMode === 'dataset') {
      if (!selectedDatasetId) {
        toast.error('Pick an uploaded dataset');
        return null;
      }
      const nodesOut = exportPayload.graph.nodes.map((n) => {
        const data: Record<string, unknown> = { ...(n.params ?? {}) };
        if (override && override.nodeId === n.id) data[override.paramKey] = override.value;
        return { id: n.id, type: n.type, position: { x: n.x, y: n.y }, data };
      });
      const body: Record<string, unknown> = {
        version: exportPayload.version,
        settings: {
          dataset_id: selectedDatasetId,
          start_date: exportPayload.settings.startDate ?? null,
          end_date: exportPayload.settings.endDate ?? null,
          initial_capital: exportPayload.settings.initialCapital ?? 10000,
          fees_bps: exportPayload.settings.feesBps ?? 0,
          slippage_bps: exportPayload.settings.slippageBps ?? 0,
          execution_mode: 'single',
        },
        graph: {
          nodes: nodesOut,
          edges: exportPayload.graph.edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            source_handle: e.sourceHandle ?? null,
            target_handle: e.targetHandle ?? null,
          })),
        },
      };
      return { body };
    }

    if (assetMode === 'multi' || assetMode === 'universe') {
      if (selectedUniverse) {
        universeKey = selectedUniverse;
      } else {
        symbolsList = multiSymbolsText
          .split(/[,\s]+/)
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean);
        if (symbolsList.length === 0) {
          toast.error('Enter symbols or pick a universe');
          return null;
        }
      }
      if (assetMode === 'universe') {
        const total = (universeKey ? (universes.find((u) => u.key === universeKey)?.count ?? 0) : symbolsList?.length ?? 0);
        if (total < 2) {
          toast.error('Universe mode needs at least 2 symbols');
          return null;
        }
      }
    }

    const nodesOut = exportPayload.graph.nodes.map((n) => {
      const data: Record<string, unknown> = { ...(n.params ?? {}) };
      if (override && override.nodeId === n.id) data[override.paramKey] = override.value;
      return {
        id: n.id,
        type: n.type,
        position: { x: n.x, y: n.y },
        data,
      };
    });

    const body: Record<string, unknown> = {
      version: exportPayload.version,
      settings: {
        symbol: assetMode === 'single' ? (exportPayload.settings.symbol ?? 'AAPL') : null,
        timeframe: exportPayload.settings.timeframe ?? '1D',
        start_date: exportPayload.settings.startDate ?? null,
        end_date: exportPayload.settings.endDate ?? null,
        initial_capital: exportPayload.settings.initialCapital ?? 10000,
        fees_bps: exportPayload.settings.feesBps ?? 0,
        slippage_bps: exportPayload.settings.slippageBps ?? 0,
        execution_mode: assetMode === 'universe' ? 'universe' : 'single',
      },
      graph: {
        nodes: nodesOut,
        edges: exportPayload.graph.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          source_handle: e.sourceHandle ?? null,
          target_handle: e.targetHandle ?? null,
        })),
      },
    };
    if (symbolsList) body.symbols = symbolsList;
    if (universeKey) body.universe = universeKey;
    return { body, symbolsList, universeKey };
  };

  const runBacktest = async () => {
    if (hasErrors) return;

    const token = localStorage.getItem('token');
    if (!token) {
      toast.error('Not logged in');
      goto('/login');
      return;
    }

    const built = buildSubmitBody();
    if (!built) return;
    const { body } = built;

    let resp: Response;
    try {
      resp = await fetch(`${BACKEND}/backtests`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
    } catch {
      toast.error('Could not reach backend — is it running?');
      return;
    }

    if (!resp.ok) {
      const text = await resp.text();
      let msg = 'Submit failed';
      try {
        const json = JSON.parse(text) as { detail?: string };
        msg = json.detail ?? msg;
      } catch { /* ignore */ }
      toast.error(msg);
      return;
    }

    const data = (await resp.json()) as {
      id: string;
      status: string;
      batch_id?: string | null;
      run_ids?: string[];
    };
    toast.success('Backtest queued');
    const isBatch = (data.run_ids?.length ?? 0) > 0 && !!data.batch_id;
    goto(isBatch ? `/app/backtests/batch/${data.batch_id}` : `/app/backtests/${data.id}`);
  };

  // ---------------------------------------------------------------------
  // Parameter Sweep
  // ---------------------------------------------------------------------

  let showSweep = $state(false);
  let sweepNodeId = $state<string>('');
  let sweepParamKey = $state<string>('');
  let sweepValuesText = $state('');
  let sweepRunning = $state(false);

  const sweepableNodes = $derived.by(() =>
    nodes.filter((n) => {
      if (!n.params) return false;
      return Object.entries(n.params).some(([, v]) => typeof v === 'number');
    })
  );

  const selectedSweepNode = $derived.by(() =>
    sweepableNodes.find((n) => n.id === sweepNodeId) ?? null
  );

  const sweepParamOptions = $derived.by(() => {
    if (!selectedSweepNode) return [] as string[];
    return Object.entries(selectedSweepNode.params)
      .filter(([, v]) => typeof v === 'number')
      .map(([k]) => k);
  });

  const parsedSweepValues = $derived.by(() => {
    const raw = sweepValuesText
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const out: number[] = [];
    for (const tok of raw) {
      const n = Number(tok);
      if (Number.isFinite(n)) out.push(n);
    }
    return out;
  });

  const openSweep = () => {
    const first = sweepableNodes[0];
    sweepNodeId = first?.id ?? '';
    sweepParamKey = '';
    sweepValuesText = '';
    showSweep = true;
  };

  const runSweep = async () => {
    if (hasErrors) {
      toast.error('Fix builder errors before sweeping');
      return;
    }
    if (assetMode !== 'single') {
      toast.error('Parameter sweep only supports single-symbol mode');
      return;
    }
    if (!sweepNodeId || !sweepParamKey) {
      toast.error('Pick a node and parameter');
      return;
    }
    const values = parsedSweepValues;
    if (values.length < 2) {
      toast.error('Enter at least 2 numeric values');
      return;
    }
    if (values.length > 12) {
      toast.error('Max 12 values per sweep');
      return;
    }

    const token = localStorage.getItem('token');
    if (!token) {
      toast.error('Not logged in');
      goto('/login');
      return;
    }

    const nodeLabel = selectedSweepNode?.label ?? selectedSweepNode?.type ?? sweepNodeId;

    sweepRunning = true;
    const results: { value: number; runId: string }[] = [];
    try {
      for (const value of values) {
        const built = buildSubmitBody({ nodeId: sweepNodeId, paramKey: sweepParamKey, value });
        if (!built) {
          sweepRunning = false;
          return;
        }
        const resp = await fetch(`${BACKEND}/backtests`, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(built.body),
        });
        if (!resp.ok) {
          const text = await resp.text();
          let msg = 'Submit failed';
          try {
            msg = (JSON.parse(text) as { detail?: string }).detail ?? msg;
          } catch { /* ignore */ }
          toast.error(`${nodeLabel} ${sweepParamKey}=${value}: ${msg}`);
          sweepRunning = false;
          return;
        }
        const data = (await resp.json()) as { id: string };
        results.push({ value, runId: data.id });
      }
    } catch {
      toast.error('Could not reach backend — is it running?');
      sweepRunning = false;
      return;
    }

    const sweepId = `sweep_${Date.now()}`;
    sessionStorage.setItem(
      `sweep:${sweepId}`,
      JSON.stringify({
        id: sweepId,
        nodeLabel,
        paramKey: sweepParamKey,
        runs: results,
        createdAt: new Date().toISOString(),
      })
    );
    toast.success(`Sweep queued: ${results.length} runs`);
    sweepRunning = false;
    showSweep = false;
    goto(`/app/backtests/sweep/${sweepId}`);
  };
</script>

<svelte:window onpointermove={onCanvasPointerMove} onpointerup={stopDragging} />

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">New Backtest</h1>
    <p class="text-sm text-muted-foreground">
      Drag blocks onto the canvas, wire an event flow, then run a backtest.
    </p>
  </div>

  <div class="flex flex-wrap items-center justify-end gap-2">
    <Button variant="outline" onclick={openTemplates}>Templates</Button>
    <Button variant="outline" onclick={openAiBuilder}>AI Builder</Button>
    <Button variant="outline" onclick={saveDraft} disabled={nodes.length === 0}>
      Save Draft
    </Button>
    <Button variant="outline" onclick={loadDraft}>Load Draft</Button>
    <Button variant="outline" onclick={openImport}>Import</Button>
    <Button variant="outline" onclick={openExport}>Export</Button>
    <Button variant="outline" onclick={openSave} disabled={nodes.length === 0}>Save Strategy</Button>
    <Button variant="outline" onclick={openLoad}>Load Strategy</Button>
    <Button variant="outline" onclick={deleteSelected} disabled={!selectedId}>
      Delete
    </Button>
    <Button
      variant="outline"
      onclick={openSweep}
      disabled={nodes.length === 0 || hasErrors || sweepableNodes.length === 0}
    >
      Sweep
    </Button>
    <span data-tour="run">
      <Button onclick={runBacktest} disabled={nodes.length === 0 || hasErrors}>Run</Button>
    </span>
  </div>
</div>

<div class="mt-4 rounded-md border bg-muted/20 p-4">
  <div class="flex flex-wrap items-center gap-2 text-sm">
    <span class="text-muted-foreground">Mode:</span>
    <button
      type="button"
      class="rounded-md border px-3 py-1 transition-colors {assetMode === 'single' ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-accent'}"
      onclick={() => { assetMode = 'single'; }}
    >
      Single Symbol
    </button>
    <button
      type="button"
      class="rounded-md border px-3 py-1 transition-colors {assetMode === 'multi' ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-accent'}"
      onclick={() => { assetMode = 'multi'; }}
    >
      Multi-Symbol
    </button>
    <button
      type="button"
      class="rounded-md border px-3 py-1 transition-colors {assetMode === 'universe' ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-accent'}"
      onclick={() => { assetMode = 'universe'; }}
      title="Cross-sectional factor strategy — rank a universe and long top / short bottom"
    >
      Universe (Factor)
    </button>
    <button
      type="button"
      class="rounded-md border px-3 py-1 transition-colors {assetMode === 'dataset' ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-accent'}"
      onclick={() => { assetMode = 'dataset'; }}
      title="Backtest against a CSV you uploaded in My Data"
    >
      Uploaded Data
    </button>
  </div>
  <div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
    {#if assetMode === 'single'}
      <div class="space-y-1 lg:col-span-2">
        <Label for="targetSymbol">Target Asset</Label>
        <Input id="targetSymbol" bind:value={targetSymbol} placeholder="AAPL" />
      </div>
    {:else if assetMode === 'dataset'}
      <div class="space-y-1 lg:col-span-2">
        <Label for="datasetSelect">Uploaded Dataset</Label>
        {#if userDatasets.length === 0}
          <div class="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            No datasets yet —
            <a href="/app/datasets" class="text-primary hover:underline">upload one in My Data</a>.
          </div>
        {:else}
          <select
            id="datasetSelect"
            class="h-9 w-full rounded-md border bg-background px-3 py-1 text-sm"
            bind:value={selectedDatasetId}
          >
            <option value="">— Select a dataset —</option>
            {#each userDatasets as d (d.id)}
              <option value={d.id}>
                {d.name} ({d.symbol} · {d.timeframe} · {d.rows_count.toLocaleString()} bars)
              </option>
            {/each}
          </select>
        {/if}
      </div>
    {:else}
      <div class="space-y-1">
        <Label for="universeSelect">Universe</Label>
        <select
          id="universeSelect"
          class="h-9 w-full rounded-md border bg-background px-3 py-1 text-sm"
          bind:value={selectedUniverse}
        >
          <option value="">— Custom list —</option>
          {#each universes as u (u.key)}
            <option value={u.key}>{u.name} ({u.count})</option>
          {/each}
        </select>
      </div>
      <div class="space-y-1">
        <Label for="multiSymbols">Symbols</Label>
        <Input
          id="multiSymbols"
          bind:value={multiSymbolsText}
          placeholder="AAPL, MSFT, NVDA"
          disabled={!!selectedUniverse}
        />
      </div>
    {/if}
    <div class="space-y-1">
      <Label for="periodStart">Start Date</Label>
      <Input id="periodStart" type="date" bind:value={periodStart} />
    </div>
    <div class="space-y-1">
      <Label for="periodEnd">End Date</Label>
      <Input id="periodEnd" type="date" bind:value={periodEnd} />
    </div>
  </div>
  <div class="mt-2 text-xs text-muted-foreground">
    Leave start/end blank to use the full available period.
    <button
      type="button"
      class="ml-2 text-primary hover:underline"
      onclick={() => {
        periodStart = '';
        periodEnd = '';
      }}
    >
      Clear dates
    </button>
  </div>
  {#if maxWarmupBars > 0}
    <div class="mt-1 text-xs text-amber-600 dark:text-amber-400">
      Warm-up: this strategy needs at least {maxWarmupBars} bars before producing signals.
      Make sure your date range is long enough.
    </div>
  {/if}
</div>

{#if showSweep}
  <div
    class="fixed inset-0 z-50 bg-black/40"
    role="dialog"
    aria-modal="true"
    onpointerdown={(e) => { if (e.currentTarget === e.target) showSweep = false; }}
  >
    <div class="mx-auto mt-16 w-[min(560px,calc(100vw-2rem))] rounded-lg border bg-background shadow-lg">
      <div class="flex items-center justify-between border-b px-4 py-3">
        <div class="font-semibold">Parameter Sweep</div>
        <button
          class="rounded-md px-2 py-1 text-sm hover:bg-accent"
          type="button"
          onclick={() => (showSweep = false)}
        >
          Close
        </button>
      </div>
      <div class="space-y-4 p-4 text-sm">
        <p class="text-muted-foreground">
          Run the same strategy with different values for one numeric parameter.
          Results land on a dedicated sweep page for side-by-side comparison.
        </p>
        <div class="grid gap-3 sm:grid-cols-2">
          <div class="space-y-1">
            <Label for="sweepNode">Node</Label>
            <select
              id="sweepNode"
              class="w-full rounded-md border bg-background px-3 py-2"
              bind:value={sweepNodeId}
              onchange={() => (sweepParamKey = '')}
            >
              <option value="">— Select —</option>
              {#each sweepableNodes as n (n.id)}
                <option value={n.id}>{n.label} ({n.type})</option>
              {/each}
            </select>
          </div>
          <div class="space-y-1">
            <Label for="sweepParam">Parameter</Label>
            <select
              id="sweepParam"
              class="w-full rounded-md border bg-background px-3 py-2"
              bind:value={sweepParamKey}
              disabled={!selectedSweepNode}
            >
              <option value="">— Select —</option>
              {#each sweepParamOptions as k (k)}
                <option value={k}>{k}</option>
              {/each}
            </select>
          </div>
        </div>
        <div class="space-y-1">
          <Label for="sweepValues">Values (comma-separated, 2–12)</Label>
          <Input
            id="sweepValues"
            bind:value={sweepValuesText}
            placeholder="10, 20, 50, 100"
          />
          <div class="text-xs text-muted-foreground">
            {parsedSweepValues.length > 0
              ? `Will run ${parsedSweepValues.length} backtests: ${parsedSweepValues.join(', ')}`
              : 'Each value = one backtest run.'}
          </div>
        </div>
        {#if assetMode !== 'single'}
          <div class="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-600 dark:bg-amber-950 dark:text-amber-200">
            Parameter sweep currently supports single-symbol mode only. Switch to Single Symbol to run a sweep.
          </div>
        {/if}
        <div class="flex justify-end gap-2">
          <Button variant="outline" onclick={() => (showSweep = false)} disabled={sweepRunning}>
            Cancel
          </Button>
          <Button
            onclick={runSweep}
            disabled={sweepRunning || assetMode !== 'single' || parsedSweepValues.length < 2 || !sweepNodeId || !sweepParamKey}
          >
            {sweepRunning ? 'Submitting…' : `Run Sweep (${parsedSweepValues.length})`}
          </Button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if showExport || showImport}
  <div
    class="fixed inset-0 z-50 bg-black/40"
    role="dialog"
    aria-modal="true"
    onpointerdown={(e) => {
      if (e.currentTarget === e.target) {
        showExport = false;
        showImport = false;
      }
    }}
  >
    <div class="mx-auto mt-16 w-[min(900px,calc(100vw-2rem))] rounded-lg border bg-background shadow-lg">
      <div class="flex items-center justify-between border-b px-4 py-3">
        <div class="font-semibold">
          {#if showExport}Export Strategy JSON{:else}Import Strategy JSON{/if}
        </div>
        <button
          class="rounded-md px-2 py-1 text-sm hover:bg-accent"
          type="button"
          onclick={() => {
            showExport = false;
            showImport = false;
          }}
        >
          Close
        </button>
      </div>

      <div class="p-4 space-y-3">
        {#if showExport}
          <div class="flex flex-wrap items-center gap-2">
            <Button variant="outline" onclick={copyExport}>Copy</Button>
            <Button variant="outline" onclick={downloadExport}>Download</Button>
            <Button variant="outline" onclick={saveDraft} disabled={nodes.length === 0}>
              Save Draft
            </Button>
            <div class="text-xs text-muted-foreground">
              Share this JSON with backend or teammates to reproduce the exact graph.
            </div>
          </div>
          <Textarea class="h-[420px] font-mono text-xs" readonly value={exportJson} />
        {:else}
          <div class="text-xs text-muted-foreground">
            Paste a previously exported JSON (we accept objects with keys: version/settings/graph, or nodes/edges).
          </div>
          <Textarea
            class="h-[420px] font-mono text-xs"
            bind:value={importJson}
            placeholder={importPlaceholder}
          />
          <div class="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              onclick={() => {
                showImport = false;
              }}
            >
              Cancel
            </Button>
            <Button variant="outline" onclick={loadDraft}>Load Draft</Button>
            <Button variant="outline" onclick={clearDraft}>Clear Draft</Button>
            <Button onclick={doImport} disabled={importJson.trim().length === 0}>
              Import
            </Button>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

{#if showAiBuilder}
  <div
    class="fixed inset-0 z-50 bg-black/40"
    role="dialog"
    aria-modal="true"
    onpointerdown={(e) => { if (e.currentTarget === e.target) showAiBuilder = false; }}
  >
    <div class="mx-auto mt-16 w-[min(720px,calc(100vw-2rem))] rounded-lg border bg-background shadow-lg">
      <div class="flex items-center justify-between border-b px-4 py-3">
        <div class="font-semibold">AI Builder</div>
        <button
          class="rounded-md px-2 py-1 text-sm hover:bg-accent"
          type="button"
          onclick={() => { showAiBuilder = false; }}
        >
          Close
        </button>
      </div>

      <div class="space-y-3 p-4">
        <div class="space-y-1.5">
          <Label for="ai-prompt">Describe your strategy</Label>
          <Textarea
            id="ai-prompt"
            class="h-[140px] text-sm"
            placeholder={`e.g. "Golden cross on SPY with a 3% stop-loss" or\n"Buy when RSI crosses above 30 AND MACD histogram is positive, exit on 3% trailing stop"`}
            bind:value={aiPrompt}
            disabled={aiLoading}
          />
          <p class="text-xs text-muted-foreground">
            The AI will translate your idea into a runnable node graph. Review before applying.
          </p>
        </div>

        {#if aiError}
          <Alert.Root variant="destructive">
            <Alert.Description class="text-xs">{aiError}</Alert.Description>
          </Alert.Root>
        {/if}

        {#if aiResult}
          <div class="rounded-md border bg-muted/30 p-3 text-sm">
            <div class="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Strategy summary
            </div>
            <p class="mb-2 text-sm">{aiResult.notes || 'No notes provided.'}</p>
            <div class="text-xs text-muted-foreground">
              Generated {aiResult.graph.nodes.length} nodes and {aiResult.graph.edges.length} connections.
              Applying will replace the current canvas.
            </div>
            {#if aiResult.settings && (aiResult.settings.mode || aiResult.settings.universe || aiResult.settings.symbol || (aiResult.settings.symbols && aiResult.settings.symbols.length > 0) || aiResult.settings.startDate || aiResult.settings.endDate)}
              <div class="mt-2 flex flex-wrap gap-1 text-xs">
                {#if aiResult.settings.mode}
                  <span class="rounded border bg-background px-1.5 py-0.5">mode: {aiResult.settings.mode}</span>
                {/if}
                {#if aiResult.settings.universe}
                  <span class="rounded border bg-background px-1.5 py-0.5">universe: {aiResult.settings.universe}</span>
                {/if}
                {#if aiResult.settings.symbol}
                  <span class="rounded border bg-background px-1.5 py-0.5">symbol: {aiResult.settings.symbol}</span>
                {/if}
                {#if aiResult.settings.symbols && aiResult.settings.symbols.length > 0}
                  <span class="rounded border bg-background px-1.5 py-0.5">symbols: {aiResult.settings.symbols.join(', ')}</span>
                {/if}
                {#if aiResult.settings.startDate}
                  <span class="rounded border bg-background px-1.5 py-0.5">start: {aiResult.settings.startDate}</span>
                {/if}
                {#if aiResult.settings.endDate}
                  <span class="rounded border bg-background px-1.5 py-0.5">end: {aiResult.settings.endDate}</span>
                {/if}
              </div>
            {/if}
          </div>
        {/if}

        <div class="flex items-center justify-end gap-2 pt-1">
          <Button
            variant="outline"
            onclick={() => { showAiBuilder = false; }}
            disabled={aiLoading}
          >
            Cancel
          </Button>
          {#if aiResult}
            <Button variant="outline" onclick={submitAiPrompt} disabled={aiLoading}>
              Regenerate
            </Button>
            <Button onclick={applyAiGraph}>Apply to canvas</Button>
          {:else}
            <Button onclick={submitAiPrompt} disabled={aiLoading || aiPrompt.trim().length < 4}>
              {aiLoading ? 'Generating…' : 'Generate'}
            </Button>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}

{#if showTemplates}
  <div
    class="fixed inset-0 z-50 bg-black/40"
    role="dialog"
    aria-modal="true"
    onpointerdown={(e) => { if (e.currentTarget === e.target) showTemplates = false; }}
  >
    <div class="mx-auto mt-24 w-[min(640px,calc(100vw-2rem))] rounded-lg border bg-background shadow-lg">
      <div class="flex items-center justify-between border-b px-4 py-3">
        <div class="font-semibold">Strategy Templates</div>
        <button
          class="rounded-md px-2 py-1 text-sm hover:bg-accent"
          type="button"
          onclick={() => showTemplates = false}
        >
          Close
        </button>
      </div>
      <div class="p-4 space-y-3">
        {#if nodes.length > 0}
          <div class="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-muted-foreground">
            Loading a template will replace the current canvas. Export or save first if you want to keep it.
          </div>
        {/if}
        <ul class="space-y-2 max-h-[480px] overflow-y-auto">
          {#each visibleTemplates as t (t.id)}
            <li class="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm">
              <div class="min-w-0">
                <div class="font-medium">{t.name}</div>
                <div class="text-xs text-muted-foreground">{t.description}</div>
              </div>
              <Button size="sm" onclick={() => applyTemplate(t.id)}>Use</Button>
            </li>
          {:else}
            <li class="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
              No templates available for this mode yet.
            </li>
          {/each}
        </ul>
      </div>
    </div>
  </div>
{/if}

{#if showSave}
  <div
    class="fixed inset-0 z-50 bg-black/40"
    role="dialog"
    aria-modal="true"
    onpointerdown={(e) => { if (e.currentTarget === e.target) showSave = false; }}
  >
    <div class="mx-auto mt-32 w-[min(480px,calc(100vw-2rem))] rounded-lg border bg-background shadow-lg">
      <div class="flex items-center justify-between border-b px-4 py-3">
        <div class="font-semibold">Save Strategy</div>
        <button class="rounded-md px-2 py-1 text-sm hover:bg-accent" type="button" onclick={() => showSave = false}>Close</button>
      </div>
      <div class="p-4 space-y-3">
        {#if loadedStrategyId}
          <p class="text-sm text-muted-foreground">Updating existing strategy. Rename below or keep the current name.</p>
        {/if}
        <div class="space-y-1">
          <Label for="strategyName">Strategy name</Label>
          <Input id="strategyName" bind:value={saveName} placeholder="My DCA Strategy" />
        </div>
        <div class="flex justify-end gap-2">
          <Button variant="outline" onclick={() => showSave = false}>Cancel</Button>
          <Button onclick={saveStrategy} disabled={!saveName.trim() || isSaving}>{isSaving ? 'Saving…' : loadedStrategyId ? 'Update' : 'Save'}</Button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if showLoad}
  <div
    class="fixed inset-0 z-50 bg-black/40"
    role="dialog"
    aria-modal="true"
    onpointerdown={(e) => { if (e.currentTarget === e.target) showLoad = false; }}
  >
    <div class="mx-auto mt-32 w-[min(560px,calc(100vw-2rem))] rounded-lg border bg-background shadow-lg">
      <div class="flex items-center justify-between border-b px-4 py-3">
        <div class="font-semibold">Load Strategy</div>
        <button class="rounded-md px-2 py-1 text-sm hover:bg-accent" type="button" onclick={() => showLoad = false}>Close</button>
      </div>
      <div class="p-4">
        {#if savedStrategies.length === 0}
          <p class="text-sm text-muted-foreground">No saved strategies yet. Build a graph and click Save Strategy.</p>
        {:else}
          <ul class="space-y-2">
            {#each savedStrategies as s (s.id)}
              <li class="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                <div>
                  <div class="font-medium">{s.name}</div>
                  <div class="text-xs text-muted-foreground">{new Date(s.updated_at).toLocaleDateString()}</div>
                </div>
                <Button size="sm" onclick={() => loadStrategy(s.id)}>Load</Button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  </div>
{/if}

{#if hasErrors}
  <Alert.Root class="mt-4 border-destructive/30 bg-destructive/5">
    <Alert.Title>Fix {errors.length} issue(s) to run</Alert.Title>
    <Alert.Description>
      <ul class="mt-2 list-disc pl-5 space-y-1">
        {#each errors.slice(0, 6) as issue, idx (idx)}
          <li>
            {#if issue.nodeId}
              <button
                type="button"
                class="text-primary hover:underline"
                onclick={() => {
                  selectedId = issue.nodeId!;
                  focusNode(issue.nodeId!);
                }}
              >
                {issue.message}
              </button>
            {:else}
              {issue.message}
            {/if}
          </li>
        {/each}
      </ul>
      {#if errors.length > 6}
        <div class="mt-2 text-xs text-muted-foreground">
          And {errors.length - 6} more…
        </div>
      {/if}
    </Alert.Description>
  </Alert.Root>
{/if}

{#if pendingSourceId}
  <div class="mt-3 rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
    Select a target block to connect from
    <span class="mx-1 font-medium text-foreground">#{pendingSourceId.slice(0, 4)}</span>.
    <button
      class="ml-2 text-primary hover:underline"
      onclick={() => {
        pendingSourceId = null;
        pendingSourceHandle = null;
      }}
      type="button"
    >
      Cancel
    </button>
  </div>
{/if}

<div class="mt-6 grid gap-4 lg:grid-cols-[280px_1fr_320px]">
  <!-- Palette -->
  <section data-tour="palette" class="rounded-lg border bg-card">
    <div class="border-b p-4">
      <h2 class="font-semibold">Blocks</h2>
      <p class="text-xs text-muted-foreground">Drag to canvas (or click).</p>
    </div>
    {#if visibleTemplates.length > 0}
      <div class="border-b p-3 space-y-2">
        <div class="flex items-center justify-between">
          <div class="text-xs font-medium text-muted-foreground">Templates</div>
          <div class="text-xs text-muted-foreground">{visibleTemplates.length}</div>
        </div>
        <div class="space-y-1.5 max-h-[360px] overflow-y-auto pr-1">
          {#each visibleTemplates as t (t.id)}
            <button
              type="button"
              class="w-full rounded-md border bg-background px-3 py-2 text-left hover:bg-accent transition-colors"
              onclick={() => applyTemplate(t.id)}
              title={t.description}
            >
              <div class="text-sm font-medium">{t.name}</div>
              <div class="mt-0.5 text-xs text-muted-foreground line-clamp-2 group-hover:line-clamp-none">{t.description}</div>
            </button>
          {/each}
        </div>
      </div>
    {/if}
    <div class="p-3 space-y-2">
      {#each (assetMode === 'universe' ? universePalette : palette) as item (item.type)}
        <div class="group relative">
          <button
            class="w-full rounded-md border bg-background px-3 py-2 pr-8 text-left hover:bg-accent transition-colors"
            onclick={() => addNode(item.type)}
            draggable="true"
            ondragstart={(e) => onPaletteDragStart(e, item.type)}
          >
            <div class="text-sm font-medium">{item.title}</div>
            <div class="text-xs text-muted-foreground">{item.hint}</div>
          </button>
          <a
            href={`/app/docs#node-${item.type}`}
            target="_blank"
            rel="noopener"
            title={`${item.title} — open docs`}
            aria-label={`${item.title} docs`}
            class="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full border bg-background text-[10px] font-semibold text-muted-foreground opacity-0 transition-opacity hover:bg-accent hover:text-foreground group-hover:opacity-100 focus:opacity-100"
          >
            ?
          </a>
        </div>
      {/each}
    </div>
  </section>

  <!-- Canvas -->
  <section data-tour="canvas" class="rounded-lg border bg-card overflow-hidden">
    <div class="border-b p-4 flex items-center justify-between">
      <h2 class="font-semibold">Canvas</h2>
      <div class="text-xs text-muted-foreground">
        {nodes.length} block(s) · {edges.length} connection(s)
      </div>
    </div>
	    <div
	      id="builder-canvas"
	      class={cn(
	        'relative h-[560px] bg-linear-to-br from-muted/30 to-background',
	        isCanvasDragOver && 'ring-2 ring-primary ring-inset'
	      )}
	      role="region"
	      aria-label="Strategy canvas"
	      onpointerdown={(e) => {
	        const target = e.target as Element | null;
	        if (target?.closest?.('[data-node]')) return;
	        isPanning = true;
	        panWasStarted = true;
	        didPan = false;
	        panStart = { x: e.clientX, y: e.clientY };
	        panOrigin = { x: viewport.x, y: viewport.y };
	      }}
	      onpointerup={() => {
	        if (panWasStarted && !didPan) {
	          pendingSourceId = null;
	          pendingSourceHandle = null;
	          selectedId = null;
	        }
	        isPanning = false;
	        panWasStarted = false;
	      }}
	      onwheel={onCanvasWheel}
	      ondragover={onCanvasDragOver}
	      ondrop={onCanvasDrop}
	      ondragleave={onCanvasDragLeave}
	      ondragend={() => (isCanvasDragOver = false)}
    >
      <div
        class="absolute inset-0"
        style={`transform: translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.scale}); transform-origin: 0 0;`}
      >
	        <svg
	          class="absolute inset-0 h-full w-full pointer-events-none overflow-visible"
	          overflow="visible"
	          aria-hidden="true"
	        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--muted-foreground)" />
            </marker>
          </defs>
          {#each edges as edge (edge.id)}
            {@const path = getEdgePath(edge)}
            {#if path}
              <path
                d={path.d}
                fill="none"
                stroke="var(--muted-foreground)"
                stroke-width="2"
                marker-end="url(#arrow)"
                opacity={
                  selectedId &&
                  (edge.source === selectedId || edge.target === selectedId)
                    ? 0.9
                    : 0.55
                }
              />
            {/if}
          {/each}
        </svg>

        {#if nodes.length === 0}
          <div class="pointer-events-none absolute inset-0 grid place-items-center p-6">
            <div class="space-y-1 text-center">
              <div class="text-sm font-medium">Drop your first block</div>
              <div class="text-xs text-muted-foreground">
                Drag from the palette or pick a template on the left.
              </div>
            </div>
          </div>
        {/if}

	        {#each nodes as node (node.id)}
	          {@const spec = getNodeSpec(node.type)}
	          <div
	            data-node
	            class={cn(
	              'group absolute w-56 cursor-grab select-none rounded-md border bg-background p-3 shadow-sm',
	              node.id === selectedId ? 'ring-2 ring-primary' : 'hover:border-foreground/30',
	              pendingSourceId === node.id && 'ring-2 ring-primary ring-offset-2'
	            )}
            style={`left:${node.x}px;top:${node.y}px;`}
            role="button"
            tabindex="0"
            onpointerdown={(event) => onNodePointerDown(event, node.id)}
          >
            {#if spec.outputs.length > 0}
              <div class="absolute -right-3 top-0">
                {#each spec.outputs as out (out.handle)}
                  <button
                    type="button"
                    class={cn(
                      'absolute grid size-6 -translate-y-1/2 place-items-center rounded-full border bg-background text-xs font-semibold shadow-sm transition-opacity',
                      'opacity-0 group-hover:opacity-100',
                      pendingSourceId && 'opacity-100',
                      pendingSourceId === node.id &&
                        pendingSourceHandle === out.handle &&
                        'text-primary border-primary',
                      pendingSourceId && pendingSourceId !== node.id && 'text-primary border-primary/60',
                      !pendingSourceId && 'text-muted-foreground'
                    )}
                    style={`top:${out.y}px;`}
                    aria-label={`Connect from ${out.label}`}
                    onclick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      if (pendingSourceId === node.id && pendingSourceHandle === out.handle) {
                        pendingSourceId = null;
                        pendingSourceHandle = null;
                        return;
                      }
                      pendingSourceId = node.id;
                      pendingSourceHandle = out.handle;
                      selectedId = node.id;
                    }}
                    onpointerdown={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                    }}
                  >
                    {out.handle === 'true' ? 'T' : out.handle === 'false' ? 'F' : '+'}
                  </button>
                {/each}
              </div>
            {/if}

            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="text-xs text-muted-foreground">{node.type}</div>
                <div class="truncate text-sm font-medium">{node.label}</div>
              </div>
              <div class="text-xs text-muted-foreground">#{node.id.slice(0, 4)}</div>
            </div>
          </div>
        {/each}
      </div>

      <div class="absolute bottom-3 right-3 flex items-center gap-2 rounded-md border bg-background/80 px-2 py-1 text-xs backdrop-blur">
        <button
          type="button"
          class="rounded px-2 py-1 hover:bg-accent"
          onclick={() => (viewport = { ...viewport, scale: clamp(viewport.scale * 1.1, 0.3, 2.5) })}
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          type="button"
          class="rounded px-2 py-1 hover:bg-accent"
          onclick={() => (viewport = { ...viewport, scale: clamp(viewport.scale * 0.9, 0.3, 2.5) })}
          aria-label="Zoom out"
        >
          −
        </button>
        <button
          type="button"
          class="rounded px-2 py-1 hover:bg-accent"
          onclick={resetView}
          aria-label="Reset view"
        >
          Reset
        </button>
        <div class="px-1 tabular-nums text-muted-foreground">
          {Math.round(viewport.scale * 100)}%
        </div>
      </div>
    </div>
  </section>

  <!-- Inspector -->
  <section data-tour="inspector" class="rounded-lg border bg-card">
    <div class="border-b p-4">
      <h2 class="font-semibold">Inspector</h2>
      <p class="text-xs text-muted-foreground">Edit the selected block.</p>
    </div>
    <div class="p-4 space-y-4">
      {#if !selected}
        <div class="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
          Select a block on the canvas to edit it.
        </div>
      {:else}
        {#if issueForSelected.length > 0}
          <Alert.Root class="border-destructive/30 bg-destructive/5">
            <Alert.Title>Issues</Alert.Title>
            <Alert.Description>
              <ul class="mt-2 list-disc pl-5 space-y-1">
                {#each issueForSelected as issue, idx (idx)}
                  <li>{issue.message}</li>
                {/each}
              </ul>
            </Alert.Description>
          </Alert.Root>
        {/if}

        <div class="space-y-2">
          <Label for="label">Label</Label>
          <Input
            id="label"
            value={selected.label}
            oninput={(e) => updateNode(selected.id, { label: (e.currentTarget as HTMLInputElement).value })}
          />
        </div>

        <div class="rounded-md border bg-muted/30 p-3 text-sm">
          <div class="flex items-center justify-between">
            <div class="text-xs font-medium text-muted-foreground">Connections</div>
            <div class="text-xs text-muted-foreground">
              In {selectedEdges.incoming.length} · Out {selectedEdges.outgoing.length}
            </div>
          </div>
          {#if selectedEdges.incoming.length === 0 && selectedEdges.outgoing.length === 0}
            <div class="mt-2 text-sm text-muted-foreground">
              No connections yet.
            </div>
          {:else}
            <div class="mt-2 space-y-2">
              {#each [...selectedEdges.incoming, ...selectedEdges.outgoing] as e (e.id)}
                <div class="flex items-center justify-between gap-3">
                  <div class="min-w-0 text-xs text-muted-foreground">
                    {e.source.slice(0, 4)}.{e.sourceHandle ?? '?'} → {e.target.slice(0, 4)}.{e.targetHandle ?? '?'}
                  </div>
                  <button
                    class="text-xs text-primary hover:underline"
                    type="button"
                    onclick={() => deleteEdge(e.id)}
                  >
                    Remove
                  </button>
                </div>
              {/each}
            </div>
          {/if}
        </div>

        {#if selected.type === 'SMA' || selected.type === 'EMA'}
          <div class="space-y-2">
            <Label for="period">Period</Label>
            <Input
              id="period"
              type="number"
              min="1"
              value={String(selected.params.period ?? 20)}
              oninput={(e) =>
                updateNodeParam(selected.id, 'period', Number((e.currentTarget as HTMLInputElement).value))
              }
            />
          </div>
        {/if}

        {#if selected.type === 'RSI'}
          <div class="space-y-2">
            <Label for="rsiPeriod">Period</Label>
            <Input
              id="rsiPeriod"
              type="number"
              min="1"
              value={String(selected.params.period ?? 14)}
              oninput={(e) =>
                updateNodeParam(selected.id, 'period', Number((e.currentTarget as HTMLInputElement).value))
              }
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label for="overbought">Overbought</Label>
              <Input
                id="overbought"
                type="number"
                min="1"
                max="100"
                value={String(selected.params.overbought ?? 70)}
                oninput={(e) =>
                  updateNodeParam(selected.id, 'overbought', Number((e.currentTarget as HTMLInputElement).value))
                }
              />
            </div>
            <div class="space-y-2">
              <Label for="oversold">Oversold</Label>
              <Input
                id="oversold"
                type="number"
                min="1"
                max="100"
                value={String(selected.params.oversold ?? 30)}
                oninput={(e) =>
                  updateNodeParam(selected.id, 'oversold', Number((e.currentTarget as HTMLInputElement).value))
                }
              />
            </div>
          </div>
        {/if}

        {#if selected.type === 'Data'}
          <div class="space-y-2">
            <Label for="timeframe">Timeframe</Label>
            <Input
              id="timeframe"
              value={String(selected.params.timeframe ?? '1D')}
              oninput={(e) =>
                updateNodeParam(selected.id, 'timeframe', (e.currentTarget as HTMLInputElement).value)
              }
            />
          </div>
        {/if}

        {#if selected.type === 'OnBar'}
          <div class="space-y-2">
            <Label for="triggerTimeframe">Timeframe</Label>
            <Input
              id="triggerTimeframe"
              value={String(selected.params.timeframe ?? '1D')}
              oninput={(e) =>
                updateNodeParam(selected.id, 'timeframe', (e.currentTarget as HTMLInputElement).value)
              }
            />
          </div>
        {/if}

        {#if selected.type === 'Constant'}
          <div class="space-y-2">
            <Label for="constValue">Value</Label>
            <Input
              id="constValue"
              type="number"
              step="any"
              value={String(selected.params.value ?? 30)}
              oninput={(e) => {
                const v = parseFloat((e.currentTarget as HTMLInputElement).value);
                if (!isNaN(v)) updateNodeParam(selected.id, 'value', v);
              }}
            />
            <p class="text-xs text-muted-foreground">
              Common values: 30 (RSI oversold), 70 (RSI overbought), 50 (midline), 200 (MA period)
            </p>
          </div>
        {/if}

        {#if selected.type === 'MACD'}
          <div class="grid grid-cols-3 gap-3">
            <div class="space-y-2">
              <Label for="macdFast">Fast</Label>
              <Input id="macdFast" type="number" min="1" value={String(selected.params.fast ?? 12)}
                oninput={(e) => updateNodeParam(selected.id, 'fast', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="macdSlow">Slow</Label>
              <Input id="macdSlow" type="number" min="1" value={String(selected.params.slow ?? 26)}
                oninput={(e) => updateNodeParam(selected.id, 'slow', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="macdSignal">Signal</Label>
              <Input id="macdSignal" type="number" min="1" value={String(selected.params.signal ?? 9)}
                oninput={(e) => updateNodeParam(selected.id, 'signal', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
          </div>
          <p class="text-xs text-muted-foreground">Outputs: MACD line, Signal line, Histogram</p>
        {/if}

        {#if selected.type === 'BollingerBands'}
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label for="bbPeriod">Period</Label>
              <Input id="bbPeriod" type="number" min="1" value={String(selected.params.period ?? 20)}
                oninput={(e) => updateNodeParam(selected.id, 'period', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="bbStd">Std Dev</Label>
              <Input id="bbStd" type="number" min="0.1" step="0.1" value={String(selected.params.std ?? 2)}
                oninput={(e) => updateNodeParam(selected.id, 'std', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
          </div>
          <p class="text-xs text-muted-foreground">Outputs: Upper band, Middle (SMA), Lower band</p>
        {/if}

        {#if selected.type === 'ATR'}
          <div class="space-y-2">
            <Label for="atrPeriod">Period</Label>
            <Input id="atrPeriod" type="number" min="1" value={String(selected.params.period ?? 14)}
              oninput={(e) => updateNodeParam(selected.id, 'period', Number((e.currentTarget as HTMLInputElement).value))} />
            <p class="text-xs text-muted-foreground">Average True Range — measures volatility. Useful for dynamic stop sizing.</p>
          </div>
        {/if}

        {#if selected.type === 'Stochastic'}
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label for="stochK">%K Period</Label>
              <Input id="stochK" type="number" min="1" value={String(selected.params.k ?? 14)}
                oninput={(e) => updateNodeParam(selected.id, 'k', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="stochD">%D Period</Label>
              <Input id="stochD" type="number" min="1" value={String(selected.params.d ?? 3)}
                oninput={(e) => updateNodeParam(selected.id, 'd', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
          </div>
          <p class="text-xs text-muted-foreground">Outputs: %K (fast), %D (slow signal). Range 0–100.</p>
        {/if}

        {#if selected.type === 'KDJ'}
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label for="kdjLength">Length</Label>
              <Input id="kdjLength" type="number" min="1" value={String(selected.params.length ?? 9)}
                oninput={(e) => updateNodeParam(selected.id, 'length', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="kdjSignal">Signal</Label>
              <Input id="kdjSignal" type="number" min="1" value={String(selected.params.signal ?? 3)}
                oninput={(e) => updateNodeParam(selected.id, 'signal', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
          </div>
          <p class="text-xs text-muted-foreground">
            K/D/J lines. Common rule: buy when J crosses above D below 20; sell when J crosses below D above 80.
          </p>
        {/if}

        {#if selected.type === 'MFI'}
          <div class="space-y-2">
            <Label for="mfiPeriod">Period</Label>
            <Input id="mfiPeriod" type="number" min="1" value={String(selected.params.period ?? 14)}
              oninput={(e) => updateNodeParam(selected.id, 'period', Number((e.currentTarget as HTMLInputElement).value))} />
            <p class="text-xs text-muted-foreground">
              Money Flow Index — volume-weighted RSI, range 0–100. Oversold &lt; 20, overbought &gt; 80.
            </p>
          </div>
        {/if}

        {#if selected.type === 'OBV'}
          <p class="text-xs text-muted-foreground">
            On-Balance Volume — cumulative signed volume. Useful for trend confirmation (divergence vs. price).
          </p>
        {/if}

        {#if selected.type === 'KST'}
          <p class="text-xs text-muted-foreground">
            Know Sure Thing — weighted sum of four ROCs (10/15/20/30). Signal = 9-period SMA of KST.
            Trade the crossover of KST over its signal.
          </p>
        {/if}

        {#if selected.type === 'And' || selected.type === 'Or'}
          <p class="text-xs text-muted-foreground">
            {selected.type === 'And'
              ? 'Fires the "true" port only when both inputs A and B fire on the same bar.'
              : 'Fires the "true" port when either input A or B fires on the bar.'}
          </p>
        {/if}

        {#if selected.type === 'Not'}
          <p class="text-xs text-muted-foreground">Inverts the incoming condition.</p>
        {/if}

        {#if selected.type === 'TimeWindow'}
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label for="twStart">Start</Label>
              <Input id="twStart" type="date" value={String(selected.params.start ?? '')}
                oninput={(e) => updateNodeParam(selected.id, 'start', (e.currentTarget as HTMLInputElement).value)} />
            </div>
            <div class="space-y-2">
              <Label for="twEnd">End</Label>
              <Input id="twEnd" type="date" value={String(selected.params.end ?? '')}
                oninput={(e) => updateNodeParam(selected.id, 'end', (e.currentTarget as HTMLInputElement).value)} />
            </div>
          </div>
          <p class="text-xs text-muted-foreground">
            "true" fires while the bar date is within the window (inclusive); "false" fires outside.
          </p>
        {/if}

        {#if selected.type === 'Position'}
          <p class="text-xs text-muted-foreground">
            Branch on strategy state. "flat" fires when no position is held; "holding" fires while in position.
          </p>
        {/if}

        {#if selected.type === 'StopLoss' || selected.type === 'TakeProfit' || selected.type === 'TrailingStop'}
          <div class="space-y-2">
            <Label for="riskPct">Percentage</Label>
            <Input id="riskPct" type="number" min="0.1" step="0.1"
              value={String(selected.params.pct ?? (selected.type === 'StopLoss' ? 2 : selected.type === 'TakeProfit' ? 5 : 3))}
              oninput={(e) => updateNodeParam(selected.id, 'pct', Number((e.currentTarget as HTMLInputElement).value))} />
          </div>
          <p class="text-xs text-muted-foreground">
            {selected.type === 'StopLoss'
              ? 'Closes the position if the close falls N% below the entry price.'
              : selected.type === 'TakeProfit'
                ? 'Closes the position if the close rises N% above the entry price.'
                : 'Closes the position if the close falls N% below the highest close since entry.'}
          </p>
        {/if}

        {#if selected.type === 'Buy'}
          {@const sizeType = String(selected.params.size_type ?? 'units')}
          {@const amountLabel =
            sizeType === 'pct_equity'
              ? 'Percent of initial capital (%)'
              : sizeType === 'dollar'
                ? 'Dollar amount ($)'
                : 'Amount (units)'}
          {@const amountStep = sizeType === 'units' ? '1' : '0.01'}
          {@const amountDefault = sizeType === 'pct_equity' ? 10 : sizeType === 'dollar' ? 1000 : 10}
          <div class="space-y-2">
            <Label for="buySizeType">Sizing</Label>
            <select
              id="buySizeType"
              class="h-9 w-full rounded-md border bg-background px-3 py-1 text-sm"
              value={sizeType}
              onchange={(e) => {
                const next = (e.currentTarget as HTMLSelectElement).value;
                updateNodeParam(selected.id, 'size_type', next);
                // Reset amount to a sensible default when mode changes so the
                // user doesn't end up buying 10% per bar after switching from
                // "10 units" — different scales, same number is dangerous.
                const reset = next === 'pct_equity' ? 10 : next === 'dollar' ? 1000 : 10;
                updateNodeParam(selected.id, 'amount', reset);
              }}
            >
              <option value="units">Units (shares)</option>
              <option value="pct_equity">% of initial capital</option>
              <option value="dollar">Dollar amount</option>
            </select>
          </div>
          <div class="space-y-2">
            <Label for="buyAmount">{amountLabel}</Label>
            <Input
              id="buyAmount"
              type="number"
              min="0"
              step={amountStep}
              value={String(selected.params.amount ?? amountDefault)}
              oninput={(e) => {
                const v = parseFloat((e.currentTarget as HTMLInputElement).value);
                if (!isNaN(v) && v > 0) updateNodeParam(selected.id, 'amount', v);
              }}
            />
            <p class="text-xs text-muted-foreground">
              {#if sizeType === 'pct_equity'}
                Quantity is computed from initial capital at entry: floor((capital × pct) / price).
              {:else if sizeType === 'dollar'}
                Quantity is floor(amount / price) at entry.
              {:else}
                Fixed share count per buy. Effective exposure drifts as equity grows.
              {/if}
            </p>
          </div>
        {/if}

        {#if selected.type === 'Sell'}
          {@const sellSize = String(selected.params.size_type ?? 'all')}
          {@const sellAmountLabel =
            sellSize === 'pct_position' ? 'Percent of position (%)'
              : sellSize === 'units' ? 'Shares to sell'
              : null}
          <div class="space-y-2">
            <Label for="sellSizeType">Sizing</Label>
            <select
              id="sellSizeType"
              class="h-9 w-full rounded-md border bg-background px-3 py-1 text-sm"
              value={sellSize}
              onchange={(e) => {
                const next = (e.currentTarget as HTMLSelectElement).value;
                updateNodeParam(selected.id, 'size_type', next);
                if (next === 'pct_position') updateNodeParam(selected.id, 'amount', 50);
                else if (next === 'units') updateNodeParam(selected.id, 'amount', 1);
                else updateNodeParam(selected.id, 'amount', 0);
              }}
            >
              <option value="all">Close entire position</option>
              <option value="pct_position">% of position</option>
              <option value="units">Shares (units)</option>
            </select>
          </div>
          {#if sellAmountLabel}
            <div class="space-y-2">
              <Label for="sellAmount">{sellAmountLabel}</Label>
              <Input
                id="sellAmount"
                type="number"
                min="0"
                step={sellSize === 'units' ? '1' : '0.01'}
                value={String(selected.params.amount ?? (sellSize === 'pct_position' ? 50 : 1))}
                oninput={(e) => {
                  const v = parseFloat((e.currentTarget as HTMLInputElement).value);
                  if (!isNaN(v) && v > 0) updateNodeParam(selected.id, 'amount', v);
                }}
              />
              <p class="text-xs text-muted-foreground">
                {#if sellSize === 'pct_position'}
                  Closes the given fraction of the open position, FIFO.
                  Useful for scale-out rules (e.g. sell 33% at each target).
                {:else}
                  Closes exactly this share count, FIFO. Engine caps at the
                  current position size if you ask for more.
                {/if}
              </p>
            </div>
          {:else}
            <p class="text-xs text-muted-foreground">
              Closes every open share for this symbol in one go — the legacy
              "exit" behaviour.
            </p>
          {/if}
        {/if}

        {#if selected.type === 'Momentum'}
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label for="momLookback">Lookback (bars)</Label>
              <Input id="momLookback" type="number" min="2" value={String(selected.params.lookback ?? 252)}
                oninput={(e) => updateNodeParam(selected.id, 'lookback', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="momSkip">Skip (bars)</Label>
              <Input id="momSkip" type="number" min="0" value={String(selected.params.skip ?? 21)}
                oninput={(e) => updateNodeParam(selected.id, 'skip', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
          </div>
          <p class="text-xs text-muted-foreground">
            Score = close[t−skip] / close[t−lookback] − 1. Classic academic momentum excludes the
            most recent month (skip=21) to avoid short-term reversal.
          </p>
        {/if}

        {#if selected.type === 'Value'}
          <p class="text-xs text-muted-foreground">
            Score = TTM EPS ÷ price (earnings yield). Higher = cheaper. Negative earnings rank lowest.
            Requires fundamentals data to be refreshed for the universe.
          </p>
        {/if}

        {#if selected.type === 'Add' || selected.type === 'Subtract' || selected.type === 'Multiply' || selected.type === 'Divide'}
          <p class="text-xs text-muted-foreground">
            {selected.type === 'Add'
              ? 'value = A + B. Combines any two numeric outputs (indicators, fundamentals, constants).'
              : selected.type === 'Subtract'
                ? 'value = A − B. Classic use: SMA(20) − SMA(50) as a raw trend score.'
                : selected.type === 'Multiply'
                  ? 'value = A × B. E.g. ATR × 2 for dynamic stop-loss distance, or Close × Volume for dollar volume.'
                  : 'value = A ÷ B. None when B ≈ 0 (protects downstream comparisons from NaN).'}
          </p>
        {/if}

        {#if selected.type === 'PE' || selected.type === 'EPS' || selected.type === 'ROE' || selected.type === 'DividendYield'}
          <p class="text-xs text-muted-foreground">
            {selected.type === 'PE'
              ? 'Price ÷ TTM EPS, computed at each bar from the latest fundamentals snapshot. None if EPS ≤ 0.'
              : selected.type === 'EPS'
                ? 'Rolling sum of the last four quarterly diluted EPS values.'
                : selected.type === 'ROE'
                  ? 'Net income ÷ shareholder equity, from the latest quarterly filing.'
                  : 'TTM dividend per share ÷ current close price, expressed as a percentage.'}
          </p>
        {/if}

        {#if selected.type === 'Reversal' || selected.type === 'LowVol' || selected.type === 'Liquidity'}
          {@const defaultPeriod = selected.type === 'Reversal' ? 21 : selected.type === 'LowVol' ? 63 : 60}
          <div class="space-y-2">
            <Label for="factorPeriod">Period (bars)</Label>
            <Input id="factorPeriod" type="number" min="2" value={String(selected.params.period ?? defaultPeriod)}
              oninput={(e) => updateNodeParam(selected.id, 'period', Number((e.currentTarget as HTMLInputElement).value))} />
          </div>
          <p class="text-xs text-muted-foreground">
            {selected.type === 'Reversal'
              ? 'Score = −(close[t] / close[t−period] − 1). Buy losers, short winners.'
              : selected.type === 'LowVol'
                ? 'Score = −stdev of daily returns over period. Lower volatility ranks higher.'
                : 'Score = mean(close × volume) over period. More liquid names rank higher.'}
          </p>
        {/if}

        {#if selected.type === 'Rank'}
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label for="rankTopPct">Top %</Label>
              <Input id="rankTopPct" type="number" min="0.01" max="1" step="0.05"
                value={String(selected.params.top_pct ?? 0.2)}
                oninput={(e) => updateNodeParam(selected.id, 'top_pct', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="rankBotPct">Bottom %</Label>
              <Input id="rankBotPct" type="number" min="0.01" max="1" step="0.05"
                value={String(selected.params.bottom_pct ?? 0.2)}
                oninput={(e) => updateNodeParam(selected.id, 'bottom_pct', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="rankRebal">Rebalance (bars)</Label>
              <Input id="rankRebal" type="number" min="1"
                value={String(selected.params.rebalance_days ?? 21)}
                oninput={(e) => updateNodeParam(selected.id, 'rebalance_days', Number((e.currentTarget as HTMLInputElement).value))} />
            </div>
            <div class="space-y-2">
              <Label for="rankMode">Mode</Label>
              <select id="rankMode"
                class="h-9 w-full rounded-md border bg-background px-3 py-1 text-sm"
                value={String(selected.params.mode ?? 'long_only')}
                onchange={(e) => updateNodeParam(selected.id, 'mode', (e.currentTarget as HTMLSelectElement).value)}
              >
                <option value="long_only">Long only</option>
                <option value="long_short">Long / Short (dollar-neutral)</option>
              </select>
            </div>
          </div>
          <p class="text-xs text-muted-foreground">
            Long-only buys the top decile; long/short adds an equal-dollar short in the bottom decile.
            Rebalance every N bars.
          </p>
        {/if}

        <div class="rounded-md border bg-muted/30 p-3">
          <div class="text-xs font-medium text-muted-foreground">Block JSON</div>
          <pre class="mt-2 text-xs overflow-auto">{JSON.stringify(selected, null, 2)}</pre>
        </div>
      {/if}
    </div>
  </section>
</div>
