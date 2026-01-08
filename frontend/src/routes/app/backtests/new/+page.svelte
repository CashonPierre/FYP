<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { Textarea } from '$lib/components/ui/textarea/index.js';
  import * as Alert from '$lib/components/ui/alert/index.js';
  import { cn } from '$lib/utils.js';
  import { toast } from 'svelte-sonner';

  type NodeType =
    | 'OnBar'
    | 'Data'
    | 'SMA'
    | 'EMA'
    | 'RSI'
    | 'IfAbove'
    | 'Buy'
    | 'Sell';

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

  type PortType = 'event' | 'number';

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
    { type: 'OnBar', title: 'On Bar', hint: 'Trigger per bar' },
    { type: 'Data', title: 'Price Bars', hint: 'OHLCV input' },
    { type: 'SMA', title: 'SMA', hint: 'Simple moving average' },
    { type: 'EMA', title: 'EMA', hint: 'Exponential moving average' },
    { type: 'RSI', title: 'RSI', hint: 'Relative strength index' },
    { type: 'IfAbove', title: 'If A > B', hint: 'Branch on comparison' },
    { type: 'Buy', title: 'Buy', hint: 'Enter position' },
    { type: 'Sell', title: 'Sell', hint: 'Exit position' },
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
  let panStart = $state({ x: 0, y: 0 });
  let panOrigin = $state({ x: 0, y: 0 });
  let didPan = $state(false);
  let showExport = $state(false);
  let showImport = $state(false);
  let exportJson = $state('');
  let importJson = $state('');
  const importPlaceholder =
    '{\n' +
    '  "version": 0,\n' +
    '  "settings": { "timeframe": "1D", "initialCapital": 10000 },\n' +
    '  "graph": { "nodes": [...], "edges": [...] }\n' +
    '}';

  const DRAFT_KEY = 'backtest:draft:v0';
  const IMPORT_KEY = 'backtest:import:v0';

  const selected = $derived(nodes.find((n) => n.id === selectedId) ?? null);
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
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [{ handle: 'out', label: 'value', type: 'number', y: NODE_DEFAULT_PORT_Y }],
        };
      case 'IfAbove':
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
      case 'Buy':
      case 'Sell':
        return {
          inputs: [{ handle: 'in', label: 'event', type: 'event', y: NODE_DEFAULT_PORT_Y }],
          outputs: [],
        };
      case 'Data':
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

  const validate = (
    currentNodes: BuilderNode[],
    currentEdges: BuilderEdge[]
  ): ValidationIssue[] => {
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

      if ((node.type === 'SMA' || node.type === 'EMA') && typeof node.params.period !== 'number') {
        issues.push({
          level: 'error',
          nodeId: node.id,
          message: 'Period must be a number.',
        });
      }
      if ((node.type === 'SMA' || node.type === 'EMA') && Number(node.params.period) <= 0) {
        issues.push({
          level: 'error',
          nodeId: node.id,
          message: 'Period must be greater than 0.',
        });
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

  const issueForSelected = $derived(
    selectedId ? issues.filter((i) => i.nodeId === selectedId) : []
  );

  const loadTemplateSmaCrossover = () => {
    const onBarId = newId('node');
    const sma10Id = newId('node');
    const sma50Id = newId('node');
    const ifId = newId('node');
    const buyId = newId('node');
    const sellId = newId('node');

    nodes = [
      { id: onBarId, type: 'OnBar', x: 60, y: 80, label: 'OnBar', params: { timeframe: '1D' } },
      { id: sma10Id, type: 'SMA', x: 320, y: 30, label: 'SMA(10)', params: { period: 10 } },
      { id: sma50Id, type: 'SMA', x: 320, y: 140, label: 'SMA(50)', params: { period: 50 } },
      { id: ifId, type: 'IfAbove', x: 600, y: 80, label: 'If SMA10 > SMA50', params: {} },
      { id: buyId, type: 'Buy', x: 900, y: 40, label: 'Buy', params: {} },
      { id: sellId, type: 'Sell', x: 900, y: 160, label: 'Sell', params: {} },
    ];

    edges = [
      { id: newId('edge'), source: onBarId, sourceHandle: 'out', target: sma10Id, targetHandle: 'in' },
      { id: newId('edge'), source: onBarId, sourceHandle: 'out', target: sma50Id, targetHandle: 'in' },
      { id: newId('edge'), source: onBarId, sourceHandle: 'out', target: ifId, targetHandle: 'in' },
      { id: newId('edge'), source: sma10Id, sourceHandle: 'out', target: ifId, targetHandle: 'a' },
      { id: newId('edge'), source: sma50Id, sourceHandle: 'out', target: ifId, targetHandle: 'b' },
      { id: newId('edge'), source: ifId, sourceHandle: 'true', target: buyId, targetHandle: 'in' },
      { id: newId('edge'), source: ifId, sourceHandle: 'false', target: sellId, targetHandle: 'in' },
    ];

    pendingSourceId = null;
    pendingSourceHandle = null;
    selectedId = ifId;
  };

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
      timeframe?: string;
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
        timeframe,
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
    importJson = '';
  };

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
      'IfAbove',
      'Buy',
      'Sell',
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
    resetView();
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
    try {
      const raw = sessionStorage.getItem(IMPORT_KEY);
      if (!raw) return;
      applyImportedPayload(JSON.parse(raw));
      sessionStorage.removeItem(IMPORT_KEY);
      toast.success('Duplicated into builder');
    } catch {
      sessionStorage.removeItem(IMPORT_KEY);
    }
  });

  const runBacktest = () => {
    if (hasErrors) return;
    const runId = `mock_${Date.now()}`;
    sessionStorage.setItem(
      'backtest:lastRun',
      JSON.stringify({
        createdAt: new Date().toISOString(),
        graph: { nodes, edges },
      })
    );
    goto(`/app/backtests/${runId}`);
  };
</script>

<svelte:window onpointermove={onCanvasPointerMove} onpointerup={stopDragging} />

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">New Backtest</h1>
    <p class="text-sm text-muted-foreground">
      Drag blocks onto the canvas, wire an event flow, then run a mocked backtest.
    </p>
  </div>

  <div class="flex items-center gap-2">
    <Button variant="outline" onclick={saveDraft} disabled={nodes.length === 0}>
      Save Draft
    </Button>
    <Button variant="outline" onclick={loadDraft}>Load Draft</Button>
    <Button variant="outline" onclick={openImport}>Import</Button>
    <Button variant="outline" onclick={openExport}>Export</Button>
    <Button variant="outline" onclick={deleteSelected} disabled={!selectedId}>
      Delete
    </Button>
    <Button onclick={runBacktest} disabled={nodes.length === 0 || hasErrors}>Run</Button>
  </div>
</div>

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
  <section class="rounded-lg border bg-card">
    <div class="border-b p-4">
      <h2 class="font-semibold">Blocks</h2>
      <p class="text-xs text-muted-foreground">Drag to canvas (or click).</p>
    </div>
    <div class="border-b p-3">
      <Button
        class="w-full"
        variant="outline"
        onclick={loadTemplateSmaCrossover}
      >
        Load Template: SMA10 &gt; SMA50
      </Button>
    </div>
    <div class="p-3 space-y-2">
      {#each palette as item (item.type)}
        <button
          class="w-full rounded-md border bg-background px-3 py-2 text-left hover:bg-accent transition-colors"
          onclick={() => addNode(item.type)}
          draggable="true"
          ondragstart={(e) => onPaletteDragStart(e, item.type)}
        >
          <div class="text-sm font-medium">{item.title}</div>
          <div class="text-xs text-muted-foreground">{item.hint}</div>
        </button>
      {/each}
    </div>
  </section>

  <!-- Canvas -->
  <section class="rounded-lg border bg-card overflow-hidden">
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
        if (e.currentTarget !== e.target) return;
        isPanning = true;
        didPan = false;
        panStart = { x: e.clientX, y: e.clientY };
        panOrigin = { x: viewport.x, y: viewport.y };
      }}
      onpointerup={() => {
        if (!didPan) {
          pendingSourceId = null;
          pendingSourceHandle = null;
          selectedId = null;
        }
        isPanning = false;
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
          <div class="absolute inset-0 grid place-items-center">
            <div class="text-center space-y-2">
              <div class="text-sm font-medium">Drop your first block</div>
              <div class="text-xs text-muted-foreground">
                Start with “On Bar”, then add indicators and actions.
              </div>
            </div>
          </div>
        {/if}

        {#each nodes as node (node.id)}
          {@const spec = getNodeSpec(node.type)}
          <div
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
  <section class="rounded-lg border bg-card">
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

        <div class="rounded-md border bg-muted/30 p-3">
          <div class="text-xs font-medium text-muted-foreground">Block JSON</div>
          <pre class="mt-2 text-xs overflow-auto">{JSON.stringify(selected, null, 2)}</pre>
        </div>
      {/if}
    </div>
  </section>
</div>
