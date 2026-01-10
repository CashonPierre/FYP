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

  type RunStatus = 'queued' | 'running' | 'completed' | 'failed';

  let status = $state<RunStatus>('queued');
  let progress = $state(0);
  type StoredRunPayload = {
    createdAt: string;
    graph?: { nodes: unknown[]; edges: unknown[] };
    nodes?: unknown[];
    edges?: unknown[];
  };
  let payload = $state<{ createdAt: string; graph: { nodes: unknown[]; edges: unknown[] } } | null>(null);

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

  onMount(() => {
    try {
      const raw = sessionStorage.getItem('backtest:lastRun');
      const parsed: StoredRunPayload | null = raw ? JSON.parse(raw) : null;
      if (parsed?.graph) {
        payload = { createdAt: parsed.createdAt, graph: parsed.graph };
      } else if (parsed) {
        payload = {
          createdAt: parsed.createdAt,
          graph: {
            nodes: parsed.nodes ?? [],
            edges: parsed.edges ?? [],
          },
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
  });

  const summary = $derived.by(() => {
    const strategyName = 'Onboarding Task Strategy';
    const runtimeSeconds = 10;
    const start = payload?.createdAt ? new Date(payload.createdAt) : new Date();
    const end = new Date(start.getTime() + runtimeSeconds * 1000);

    const initialCapital = 1_000_000;
    const nav = 1_326_709.88;
    const pl = nav - initialCapital;

    return {
      strategyName,
      runtimeSeconds,
      start,
      end,
      initialCapital,
      nav,
      pl,
      annualizedReturn: 1.3462,
      totalReturn: 0.3267,
      transactionFees: 253.82,
      slippage: 0,
      triggerSymbol: 'AAPL (Apple)',
      tradingSymbol: 'AAPL (Apple)',
      triggerSettings: 'Apple Run once for every 1h candle',
      accountUsed: 'Backtesting Account (0001) - Securities',
      backtestPeriod: 'November 4, 2022 – March 4, 2023',
      maxDrawdown: 0.232,
      volatility: 0.4629,
      sharpeRatio: 2.83,
      sortinoRatio: 4.683,
      calmarRatio: 5.802,
      filledOrders: 98,
      buyOrders: '98/98 (all filled)',
      sellOrders: '0/98 (none executed)',
    };
  });
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Backtest Results</h1>
    <p class="text-sm text-muted-foreground">Run id: {runId}</p>
  </div>
  <div class="flex items-center gap-2">
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
    {#if status !== 'completed'}
      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">Running (mock)</Card.Title>
          <Card.Description>Replace with real job polling later.</Card.Description>
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
            <Card.Title class="text-xl">{fmtPercent(summary.annualizedReturn)}</Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Volatility</Card.Description>
            <Card.Title class="text-xl">{fmtPercent(summary.volatility)}</Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Sharpe Ratio</Card.Description>
            <Card.Title class="text-xl">{fmtNumber3(summary.sharpeRatio)}</Card.Title>
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
            <Card.Title class="text-xl">{fmtPercent(summary.maxDrawdown)}</Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Trades</Card.Description>
            <Card.Title class="text-xl">38</Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Win Rate</Card.Description>
            <Card.Title class="text-xl">55%</Card.Title>
          </Card.Header>
        </Card.Root>
      </div>

      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">Price (Candles)</Card.Title>
          <Card.Description>Underlying OHLC + buy/sell markers (mock).</Card.Description>
        </Card.Header>
        <Card.CardContent>
          <CandlestickChart bars={ohlc} trades={trades} height={280} />
        </Card.CardContent>
      </Card.Root>

      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">Equity Curve</Card.Title>
          <Card.Description>Line chart (mock).</Card.Description>
        </Card.Header>
        <Card.CardContent>
          <EquityCurveChart points={equity} height={220} />
        </Card.CardContent>
      </Card.Root>
    {/if}
  </section>

  <aside class="space-y-4">
    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base">
          Backtest Summary: {summary.strategyName}
        </Card.Title>
        <Card.Description>Mock summary (replace with backend output later).</Card.Description>
      </Card.Header>
      <Card.CardContent class="space-y-4 text-sm">
        <div class="space-y-2">
          <div class="text-xs font-medium text-muted-foreground">Basic Information</div>
          <dl class="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
            <dt class="text-muted-foreground">Strategy Name</dt>
            <dd class="text-right font-medium">{summary.strategyName}</dd>
            <dt class="text-muted-foreground">Backtest Runtime</dt>
            <dd class="text-right font-medium">{summary.runtimeSeconds} seconds</dd>
            <dt class="text-muted-foreground">Start Time</dt>
            <dd class="text-right font-medium">{summary.start.toLocaleString()}</dd>
            <dt class="text-muted-foreground">End Time</dt>
            <dd class="text-right font-medium">{summary.end.toLocaleString()}</dd>
          </dl>
        </div>

        <Separator />

        <div class="space-y-2">
          <div class="text-xs font-medium text-muted-foreground">Return & Fee Performance</div>
          <dl class="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
            <dt class="text-muted-foreground">Net Asset Value (NAV)</dt>
            <dd class="text-right font-medium">{fmtCurrency(summary.nav)}</dd>
            <dt class="text-muted-foreground">Profit/Loss (P/L)</dt>
            <dd class="text-right font-medium">{fmtCurrency(summary.pl)}</dd>
            <dt class="text-muted-foreground">Annualized Return</dt>
            <dd class="text-right font-medium">{fmtPercent(summary.annualizedReturn)}</dd>
            <dt class="text-muted-foreground">Total Return</dt>
            <dd class="text-right font-medium">{fmtPercent(summary.totalReturn)}</dd>
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
            <dt class="text-muted-foreground">Trigger Symbol</dt>
            <dd class="text-right font-medium">{summary.triggerSymbol}</dd>
            <dt class="text-muted-foreground">Trading Symbol</dt>
            <dd class="text-right font-medium">{summary.tradingSymbol}</dd>
            <dt class="text-muted-foreground">Trigger Settings</dt>
            <dd class="text-right font-medium">{summary.triggerSettings}</dd>
            <dt class="text-muted-foreground">Initial Capital</dt>
            <dd class="text-right font-medium">{fmtCurrency(summary.initialCapital)}</dd>
            <dt class="text-muted-foreground">Account Used</dt>
            <dd class="text-right font-medium">{summary.accountUsed}</dd>
            <dt class="text-muted-foreground">Backtest Period</dt>
            <dd class="text-right font-medium">{summary.backtestPeriod}</dd>
          </dl>
        </div>

        <Separator />

        <div class="space-y-2">
          <div class="text-xs font-medium text-muted-foreground">Performance Analysis</div>
          <dl class="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
            <dt class="text-muted-foreground">Maximum Drawdown</dt>
            <dd class="text-right font-medium">{fmtPercent(summary.maxDrawdown)}</dd>
            <dt class="text-muted-foreground">Volatility</dt>
            <dd class="text-right font-medium">{fmtPercent(summary.volatility)}</dd>
            <dt class="text-muted-foreground">Sharpe Ratio</dt>
            <dd class="text-right font-medium">{fmtNumber3(summary.sharpeRatio)}</dd>
            <dt class="text-muted-foreground">Sortino Ratio</dt>
            <dd class="text-right font-medium">{fmtNumber3(summary.sortinoRatio)}</dd>
            <dt class="text-muted-foreground">Calmar Ratio</dt>
            <dd class="text-right font-medium">{fmtNumber3(summary.calmarRatio)}</dd>
            <dt class="text-muted-foreground">Filled Orders</dt>
            <dd class="text-right font-medium">{summary.filledOrders}</dd>
            <dt class="text-muted-foreground">Buy Orders</dt>
            <dd class="text-right font-medium">{summary.buyOrders}</dd>
            <dt class="text-muted-foreground">Sell Orders</dt>
            <dd class="text-right font-medium">{summary.sellOrders}</dd>
          </dl>
        </div>
      </Card.CardContent>
    </Card.Root>

    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base">Run Config</Card.Title>
        <Card.Description>From sessionStorage (mock).</Card.Description>
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
