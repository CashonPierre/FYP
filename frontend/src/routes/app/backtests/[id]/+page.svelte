<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { Separator } from '$lib/components/ui/separator/index.js';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import CandlestickChart, { type OhlcBar, type TradeMarker } from '$lib/components/charts/CandlestickChart.svelte';
  import EquityCurveChart, { type EquityPoint } from '$lib/components/charts/EquityCurveChart.svelte';
  import TradesTable from '$lib/components/charts/TradesTable.svelte';
  import { BACKEND } from '$lib/config.js';

  type RunStatus = 'queued' | 'running' | 'completed' | 'failed';

  type ApiSummary = {
    initial_capital: number;
    final_nav: number;
    total_return: number;
    annualized_return: number | null;
    max_drawdown: number | null;
    volatility: number | null;
    sharpe: number | null;
    total_trades: number;
    win_rate: number | null;
    fees: number;
    slippage: number;
  };

  type ApiResults = {
    id: string;
    status: string;
    symbol: string | null;
    timeframe: string | null;
    summary: ApiSummary | null;
    series: {
      ohlc: { time: string; open: number; high: number; low: number; close: number; volume: number | null }[];
      trades: { id: string; time: string; side: string; price: number; quantity: number; symbol: string }[];
      equity: { time: string; equity: number }[];
    };
  };

  let apiResults = $state<ApiResults | null>(null);
  let apiError = $state<string | null>(null);

  let status = $state<RunStatus>('queued');
  let progress = $state(0);
  type StoredRunPayload = {
    createdAt: string;
    settings?: Record<string, unknown>;
    graph?: { nodes: unknown[]; edges: unknown[] };
    nodes?: unknown[];
    edges?: unknown[];
  };
  let payload = $state<{ createdAt: string; settings?: Record<string, unknown>; graph: { nodes: unknown[]; edges: unknown[] } } | null>(null);

  const runId = $derived(page.params.id ?? 'unknown');
  const IMPORT_KEY = 'backtest:import:v0';

  const currency = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  });
  const percent = new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  });
  const number3 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 });

  const fmtCurrency = (v: number) => currency.format(v);
  const fmtPercent = (v: number) => percent.format(v);
  const fmtNumber3 = (v: number) => number3.format(v);

  const seeded = (seed: number) => {
    let t = seed >>> 0;
    return () => {
      t += 0x6d2b79f5;
      let r = Math.imul(t ^ (t >>> 15), 1 | t);
      r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  };

  const makeMockBars = (start: Date, count: number, seed: number): OhlcBar[] => {
    const rand = seeded(seed);
    const bars: OhlcBar[] = [];
    let lastClose = 150 + rand() * 20;
    for (let i = 0; i < count; i++) {
      const time = new Date(start.getTime() + i * 60 * 60 * 1000); // 1h bars
      const open = lastClose;
      const drift = (rand() - 0.5) * 1.8;
      const close = Math.max(1, open + drift);
      const wickUp = rand() * 1.6;
      const wickDown = rand() * 1.6;
      const high = Math.max(open, close) + wickUp;
      const low = Math.max(0.5, Math.min(open, close) - wickDown);
      bars.push({
        time: time.toISOString(),
        open,
        high,
        low,
        close,
      });
      lastClose = close;
    }
    return bars;
  };

  const makeMockEquity = (bars: OhlcBar[], initial: number, seed: number): EquityPoint[] => {
    const rand = seeded(seed ^ 0x9e3779b9);
    const points: EquityPoint[] = [];
    let equity = initial;
    for (let i = 0; i < bars.length; i++) {
      const step = (rand() - 0.45) * 2400;
      equity = Math.max(initial * 0.6, equity + step);
      points.push({ time: bars[i].time, equity });
    }
    return points;
  };

  const makeMockTrades = (bars: OhlcBar[], seed: number): TradeMarker[] => {
    const rand = seeded(seed ^ 0x85ebca6b);
    const trades: TradeMarker[] = [];
    if (bars.length < 12) return trades;
    const picks = new Set<number>();
    while (picks.size < 6) picks.add(4 + Math.floor(rand() * (bars.length - 8)));
    const idxs = [...picks].sort((a, b) => a - b);
    for (let i = 0; i < idxs.length; i++) {
      const bar = bars[idxs[i]];
      trades.push({
        time: bar.time,
        side: i % 2 === 0 ? 'buy' : 'sell',
        price: i % 2 === 0 ? bar.low : bar.high,
      });
    }
    return trades;
  };

  let ohlc = $state<OhlcBar[]>([]);
  let equity = $state<EquityPoint[]>([]);
  let trades = $state<TradeMarker[]>([]);

  const csvEscape = (value: unknown): string => {
    const s = value == null ? '' : String(value);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };

  const downloadCsv = (filename: string, rows: (string | number | null | undefined)[][]) => {
    const body = rows.map((row) => row.map(csvEscape).join(',')).join('\n');
    const blob = new Blob([body + '\n'], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const exportTradesCsv = () => {
    if (trades.length === 0) {
      toast.error('No trades to export');
      return;
    }
    const header = ['time', 'side', 'price', 'quantity'];
    const apiTrades = apiResults?.series.trades ?? [];
    const rows: (string | number | null | undefined)[][] = [header];
    for (let i = 0; i < trades.length; i++) {
      const t = trades[i];
      const detail = apiTrades[i];
      rows.push([t.time, t.side, t.price, detail?.quantity ?? t.quantity ?? '']);
    }
    downloadCsv(`trades_${runId}.csv`, rows);
    toast.success('Trades exported');
  };

  const exportEquityCsv = () => {
    if (equity.length === 0) {
      toast.error('No equity data to export');
      return;
    }
    const rows: (string | number | null | undefined)[][] = [['time', 'equity']];
    for (const p of equity) rows.push([p.time, p.equity]);
    downloadCsv(`equity_${runId}.csv`, rows);
    toast.success('Equity curve exported');
  };

  onMount(() => {
    // Legacy mock runs (id starts with "mock_")
    if (runId.startsWith('mock_')) {
      try {
        const raw = sessionStorage.getItem('backtest:lastRun');
        const parsed: StoredRunPayload | null = raw ? JSON.parse(raw) : null;
        if (parsed?.graph) {
          payload = { createdAt: parsed.createdAt, settings: parsed.settings, graph: parsed.graph };
        } else if (parsed) {
          payload = {
            createdAt: parsed.createdAt,
            settings: parsed.settings,
            graph: { nodes: parsed.nodes ?? [], edges: parsed.edges ?? [] },
          };
        } else {
          payload = null;
        }
      } catch {
        payload = null;
      }

      status = 'running';
      progress = 5;
      const seed = Array.from(runId).reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
      const start = payload?.createdAt ? new Date(payload.createdAt) : new Date();
      ohlc = makeMockBars(start, 80, seed);
      equity = makeMockEquity(ohlc, 1_000_000, seed);
      trades = makeMockTrades(ohlc, seed);

      const timer = setInterval(() => {
        progress = Math.min(100, progress + 12);
        if (progress >= 100) {
          status = 'completed';
          clearInterval(timer);
        }
      }, 250);
      return () => clearInterval(timer);
    }

    // Real run — poll status then fetch results
    const token = localStorage.getItem('token');
    if (!token) {
      toast.error('Not logged in');
      goto('/login');
      return;
    }

    status = 'queued';
    progress = 5;

    const fetchResults = async () => {
      try {
        const res = await fetch(`${BACKEND}/backtests/${runId}/results`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data: ApiResults = await res.json();
        apiResults = data;
        progress = 100;

        ohlc = data.series.ohlc.map((b) => ({
          time: b.time,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        }));
        trades = data.series.trades.map((t) => ({
          id: t.id,
          time: t.time,
          side: t.side as 'buy' | 'sell',
          price: t.price,
          quantity: t.quantity,
        }));
        equity = data.series.equity.map((e) => ({ time: e.time, equity: e.equity }));
      } catch {
        // results fetch failure is non-fatal; charts stay empty
      }
    };

    const poll = async () => {
      try {
        const res = await fetch(`${BACKEND}/backtests/${runId}/status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          if (res.status === 404) {
            apiError = 'Run not found';
            status = 'failed';
            clearInterval(pollTimer);
          }
          return;
        }
        const data = (await res.json()) as { status: string; error_message?: string | null };
        status = data.status as RunStatus;
        if (data.status === 'running') progress = 50;

        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollTimer);
          if (data.status === 'completed') await fetchResults();
          if (data.status === 'failed') apiError = data.error_message ?? 'Backtest failed.';
        }
      } catch {
        // network blip — keep polling
      }
    };

    poll();
    const pollTimer = setInterval(poll, 2000);
    return () => clearInterval(pollTimer);
  });

  const benchmark = $derived.by<EquityPoint[]>(() => {
    if (ohlc.length === 0) return [];
    const initial = apiResults?.summary?.initial_capital ?? 10000;
    const first = ohlc[0].close;
    if (!first) return [];
    return ohlc.map((b) => ({ time: b.time, equity: (initial * b.close) / first }));
  });

  const summary = $derived.by(() => {
    const api = apiResults?.summary ?? null;

    // Prefer the symbol/timeframe echoed by the results API — `payload` is only
    // populated for mock runs. Falling back to AAPL/1D here meant every real
    // run's "Buy & Hold …" label read AAPL regardless of the actual symbol.
    const apiSymbol = apiResults?.symbol ?? null;
    const apiTimeframe = apiResults?.timeframe ?? null;
    const payloadSymbol =
      payload?.settings?.symbol && typeof payload.settings.symbol === 'string'
        ? payload.settings.symbol
        : null;
    const payloadTimeframe =
      payload?.settings?.timeframe && typeof payload.settings.timeframe === 'string'
        ? payload.settings.timeframe
        : null;
    const symbol = (apiSymbol ?? payloadSymbol ?? '').toUpperCase() || '—';
    const timeframe = apiTimeframe ?? payloadTimeframe ?? '1D';
    const startDate =
      payload?.settings?.startDate && typeof payload.settings.startDate === 'string'
        ? payload.settings.startDate
        : null;
    const endDate =
      payload?.settings?.endDate && typeof payload.settings.endDate === 'string'
        ? payload.settings.endDate
        : null;

    const initialCapital = api?.initial_capital ?? 10000;
    const nav = api?.final_nav ?? initialCapital;
    const totalTrades = api?.total_trades ?? 0;
    const winRate = api?.win_rate ?? null;

    return {
      initialCapital,
      nav,
      pl: nav - initialCapital,
      totalReturn: api?.total_return ?? 0,
      annualizedReturn: api?.annualized_return ?? null,
      transactionFees: api?.fees ?? 0,
      slippage: api?.slippage ?? 0,
      maxDrawdown: api?.max_drawdown ?? null,
      volatility: api?.volatility ?? null,
      sharpeRatio: api?.sharpe ?? null,
      triggerSymbol: symbol,
      tradingSymbol: symbol,
      triggerSettings: `${symbol} — 1 bar per ${timeframe} candle`,
      accountUsed: 'Backtesting Account',
      backtestPeriod: startDate && endDate ? `${startDate} – ${endDate}` : 'Full available period',
      filledOrders: totalTrades,
      winRate,
    };
  });
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Backtest Results</h1>
    <p class="text-sm text-muted-foreground">Run id: {runId}</p>
  </div>
  <div class="flex flex-wrap items-center gap-2">
    <Button
      variant="outline"
      onclick={exportTradesCsv}
      disabled={status !== 'completed' || trades.length === 0}
    >
      Export Trades CSV
    </Button>
    <Button
      variant="outline"
      onclick={exportEquityCsv}
      disabled={status !== 'completed' || equity.length === 0}
    >
      Export Equity CSV
    </Button>
    <Button variant="outline" onclick={() => goto('/app/backtests/new')}>
      New Backtest
    </Button>
    <Button variant="outline" onclick={() => goto('/app/backtests')}>
      History
    </Button>
  </div>
</div>

<div class="mt-6 grid gap-4 lg:grid-cols-[1fr_440px]">
  <section class="space-y-4">
    {#if status === 'failed'}
      <Card.Root class="border border-destructive">
        <Card.Header>
          <Card.Title class="text-base text-destructive">Backtest Failed</Card.Title>
          <Card.Description>The backtest encountered an error and could not complete.</Card.Description>
        </Card.Header>
        <Card.CardContent>
          <p class="text-sm text-muted-foreground">
            {apiError ?? 'An unknown error occurred. Check the Celery worker logs for details.'}
          </p>
          <Button class="mt-4" variant="outline" onclick={() => goto('/app/backtests/new')}>
            Try Again
          </Button>
        </Card.CardContent>
      </Card.Root>
    {:else if status !== 'completed'}
      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base capitalize">{status}</Card.Title>
          <Card.Description>
            {status === 'queued' ? 'Waiting for a worker to pick up this job…' : 'Running backtest, this may take a few seconds…'}
          </Card.Description>
        </Card.Header>
        <Card.CardContent class="space-y-3">
          <div class="h-2 w-full rounded bg-muted">
            <div
              class="h-2 rounded bg-primary transition-all"
              style={`width:${progress}%`}
            ></div>
          </div>
          <div class="text-sm text-muted-foreground">{progress}%</div>
        </Card.CardContent>
      </Card.Root>
    {:else}
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Profit/Loss (P/L)</Card.Description>
            <Card.Title class="text-xl">{fmtCurrency(summary.pl)}</Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Annualized Return</Card.Description>
            <Card.Title class="text-xl">
              {summary.annualizedReturn != null ? fmtPercent(summary.annualizedReturn) : '—'}
            </Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Volatility</Card.Description>
            <Card.Title class="text-xl">
              {summary.volatility != null ? fmtPercent(summary.volatility) : '—'}
            </Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Sharpe Ratio</Card.Description>
            <Card.Title class="text-xl">
              {summary.sharpeRatio != null ? fmtNumber3(summary.sharpeRatio) : '—'}
            </Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Total Return</Card.Description>
            <Card.Title class="text-xl">{fmtPercent(summary.totalReturn)}</Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Max Drawdown</Card.Description>
            <Card.Title class="text-xl">
              {summary.maxDrawdown != null ? fmtPercent(summary.maxDrawdown) : '—'}
            </Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Trades</Card.Description>
            <Card.Title class="text-xl">{summary.filledOrders}</Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Win Rate</Card.Description>
            <Card.Title class="text-xl">
              {summary.winRate != null ? fmtPercent(summary.winRate) : '—'}
            </Card.Title>
          </Card.Header>
        </Card.Root>
      </div>

      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">Price (Candles)</Card.Title>
          <Card.Description>Underlying OHLC + buy/sell markers.</Card.Description>
        </Card.Header>
        <Card.CardContent>
          <CandlestickChart bars={ohlc} trades={trades} height={280} />
        </Card.CardContent>
      </Card.Root>

      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">Equity Curve</Card.Title>
          <Card.Description>Portfolio value over time.</Card.Description>
        </Card.Header>
        <Card.CardContent>
          <EquityCurveChart
            points={equity}
            benchmark={benchmark}
            benchmarkLabel={`Buy & Hold ${summary.triggerSymbol}`}
            height={220}
          />
        </Card.CardContent>
      </Card.Root>

      {#if trades.length > 0}
        <Card.Root class="border">
          <Card.Header>
            <Card.Title class="text-base">Trades</Card.Title>
            <Card.Description>{trades.length} entries/exits — click a column header to sort.</Card.Description>
          </Card.Header>
          <Card.CardContent class="p-0">
            <TradesTable {trades} />
          </Card.CardContent>
        </Card.Root>
      {/if}
    {/if}
  </section>

  <aside class="space-y-4">
    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base">Backtest Summary</Card.Title>
      </Card.Header>
      <Card.CardContent class="space-y-4 text-sm">
        <div class="space-y-2">
          <div class="text-xs font-medium text-muted-foreground">Return & Fee Performance</div>
          <dl class="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
            <dt class="text-muted-foreground">Net Asset Value (NAV)</dt>
            <dd class="text-right font-medium">{fmtCurrency(summary.nav)}</dd>
            <dt class="text-muted-foreground">Profit/Loss (P/L)</dt>
            <dd class="text-right font-medium">{fmtCurrency(summary.pl)}</dd>
            <dt class="text-muted-foreground">Total Return</dt>
            <dd class="text-right font-medium">{fmtPercent(summary.totalReturn)}</dd>
            <dt class="text-muted-foreground">Annualized Return</dt>
            <dd class="text-right font-medium">
              {summary.annualizedReturn != null ? fmtPercent(summary.annualizedReturn) : '—'}
            </dd>
            <dt class="text-muted-foreground">Transaction Fees</dt>
            <dd class="text-right font-medium">{fmtCurrency(summary.transactionFees)}</dd>
            <dt class="text-muted-foreground">Slippage</dt>
            <dd class="text-right font-medium">{fmtCurrency(summary.slippage)}</dd>
          </dl>
        </div>

        <Separator />

        <div class="space-y-2">
          <div class="text-xs font-medium text-muted-foreground">Parameters</div>
          <dl class="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
            <dt class="text-muted-foreground">Symbol</dt>
            <dd class="text-right font-medium">{summary.triggerSymbol}</dd>
            <dt class="text-muted-foreground">Trigger Settings</dt>
            <dd class="text-right font-medium">{summary.triggerSettings}</dd>
            <dt class="text-muted-foreground">Initial Capital</dt>
            <dd class="text-right font-medium">{fmtCurrency(summary.initialCapital)}</dd>
            <dt class="text-muted-foreground">Backtest Period</dt>
            <dd class="text-right font-medium">{summary.backtestPeriod}</dd>
          </dl>
        </div>

        <Separator />

        <div class="space-y-2">
          <div class="text-xs font-medium text-muted-foreground">Performance Analysis</div>
          <dl class="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
            <dt class="text-muted-foreground">Maximum Drawdown</dt>
            <dd class="text-right font-medium">
              {summary.maxDrawdown != null ? fmtPercent(summary.maxDrawdown) : '—'}
            </dd>
            <dt class="text-muted-foreground">Volatility</dt>
            <dd class="text-right font-medium">
              {summary.volatility != null ? fmtPercent(summary.volatility) : '—'}
            </dd>
            <dt class="text-muted-foreground">Sharpe Ratio</dt>
            <dd class="text-right font-medium">
              {summary.sharpeRatio != null ? fmtNumber3(summary.sharpeRatio) : '—'}
            </dd>
            <dt class="text-muted-foreground">Total Trades</dt>
            <dd class="text-right font-medium">{summary.filledOrders}</dd>
            <dt class="text-muted-foreground">Win Rate</dt>
            <dd class="text-right font-medium">
              {summary.winRate != null ? fmtPercent(summary.winRate) : '—'}
            </dd>
          </dl>
        </div>
      </Card.CardContent>
    </Card.Root>

    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base">Run Config</Card.Title>
      </Card.Header>
      <Card.CardContent>
        {#if payload}
          <div class="text-xs text-muted-foreground">
            Created: {payload.createdAt}
          </div>
          <div class="mt-2 text-sm">
            Blocks: <span class="font-medium">{payload.graph.nodes.length}</span>
          </div>
          <div class="mt-1 text-sm">
            Connections: <span class="font-medium">{payload.graph.edges.length}</span>
          </div>
          <Button
            class="mt-4 w-full"
            variant="outline"
            onclick={() => {
              if (!payload) return;
              sessionStorage.setItem(
                IMPORT_KEY,
                JSON.stringify({ version: 0, settings: {}, graph: payload.graph })
              );
              toast.success('Opening in builder…');
              goto('/app/backtests/new');
            }}
          >
            Duplicate in Builder
          </Button>
        {:else}
          <div class="text-sm text-muted-foreground">
            No config found. Run a backtest from the builder first.
          </div>
          <Button class="mt-4 w-full" onclick={() => goto('/app/backtests/new')}>
            Go to Builder
          </Button>
        {/if}
      </Card.CardContent>
    </Card.Root>
  </aside>
</div>
