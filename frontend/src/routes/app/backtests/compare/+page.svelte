<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import MultiEquityChart, { type EquitySeries } from '$lib/components/charts/MultiEquityChart.svelte';
  import { BACKEND } from '$lib/config.js';

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
    summary: ApiSummary | null;
    series: {
      ohlc: { time: string; open: number; high: number; low: number; close: number; volume: number | null }[];
      trades: { id: string; time: string; side: string; price: number; quantity: number; symbol: string }[];
      equity: { time: string; equity: number }[];
    };
  };

  type RunRow = {
    id: string;
    label: string;
    symbol: string;
    results: ApiResults | null;
    error: string | null;
  };

  const ids = $derived.by(() => {
    const raw = page.url.searchParams.get('ids') ?? '';
    return raw.split(',').map((s) => s.trim()).filter(Boolean);
  });

  let rows = $state<RunRow[]>([]);
  let loading = $state(true);

  const currency = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
  const percent = new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  });
  const number3 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 });

  const fmtCurrency = (v: number | null | undefined) => (v == null ? '—' : currency.format(v));
  const fmtPercent = (v: number | null | undefined) => (v == null ? '—' : percent.format(v));
  const fmtNumber3 = (v: number | null | undefined) => (v == null ? '—' : number3.format(v));

  const shortId = (id: string) => id.slice(0, 8);

  onMount(async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      toast.error('Not logged in');
      goto('/login');
      return;
    }

    if (ids.length < 2) {
      toast.error('Need at least 2 runs to compare');
      loading = false;
      return;
    }

    const fetched = await Promise.all(
      ids.map(async (id, i): Promise<RunRow> => {
        try {
          const res = await fetch(`${BACKEND}/backtests/${id}/results`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok) {
            return { id, label: `Run ${i + 1}`, symbol: '—', results: null, error: `HTTP ${res.status}` };
          }
          const data: ApiResults = await res.json();
          const symbol = data.series.trades[0]?.symbol ?? '—';
          return {
            id,
            label: `${symbol} · ${shortId(id)}`,
            symbol,
            results: data,
            error: data.summary == null ? 'Results not ready' : null,
          };
        } catch (e) {
          return { id, label: `Run ${i + 1}`, symbol: '—', results: null, error: (e as Error).message };
        }
      })
    );
    rows = fetched;
    loading = false;
  });

  const equitySeries = $derived.by<EquitySeries[]>(() => {
    const out: EquitySeries[] = [];
    for (const row of rows) {
      const pts = row.results?.series.equity ?? [];
      if (pts.length > 0) out.push({ label: row.label, points: pts });
    }
    return out;
  });

  const anyReady = $derived.by(() => rows.some((r) => r.results?.summary != null));
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Compare Backtests</h1>
    <p class="text-sm text-muted-foreground">
      {ids.length} runs side-by-side.
    </p>
  </div>
  <div class="flex gap-2">
    <Button variant="outline" onclick={() => goto('/app/backtests')}>
      Back to History
    </Button>
  </div>
</div>

<div class="mt-6 space-y-4">
  {#if loading}
    <div class="text-sm text-muted-foreground">Loading runs…</div>
  {:else if rows.length === 0}
    <div class="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
      No runs selected.
    </div>
  {:else}
    {#if anyReady}
      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">Equity Curves</Card.Title>
          <Card.Description>All selected runs on a single axis.</Card.Description>
        </Card.Header>
        <Card.CardContent>
          <MultiEquityChart series={equitySeries} height={280} />
        </Card.CardContent>
      </Card.Root>
    {/if}

    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base">Metrics</Card.Title>
        <Card.Description>Key statistics per run.</Card.Description>
      </Card.Header>
      <Card.CardContent class="overflow-x-auto p-0">
        <table class="w-full text-sm">
          <thead class="border-b bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th class="px-4 py-2 text-left font-medium">Run</th>
              <th class="px-4 py-2 text-right font-medium">Total Return</th>
              <th class="px-4 py-2 text-right font-medium">Annualized</th>
              <th class="px-4 py-2 text-right font-medium">Sharpe</th>
              <th class="px-4 py-2 text-right font-medium">Max DD</th>
              <th class="px-4 py-2 text-right font-medium">Volatility</th>
              <th class="px-4 py-2 text-right font-medium">Trades</th>
              <th class="px-4 py-2 text-right font-medium">Win Rate</th>
              <th class="px-4 py-2 text-right font-medium">Final NAV</th>
            </tr>
          </thead>
          <tbody>
            {#each rows as row (row.id)}
              {@const s = row.results?.summary}
              <tr class="border-b last:border-b-0 hover:bg-muted/30">
                <td class="px-4 py-2">
                  <button
                    class="text-left hover:underline"
                    onclick={() => goto(`/app/backtests/${row.id}`)}
                  >
                    <div class="font-medium">{row.symbol}</div>
                    <div class="text-xs text-muted-foreground">{shortId(row.id)}</div>
                  </button>
                </td>
                {#if s}
                  <td class="px-4 py-2 text-right {s.total_return >= 0 ? 'text-green-600' : 'text-destructive'}">
                    {fmtPercent(s.total_return)}
                  </td>
                  <td class="px-4 py-2 text-right">{fmtPercent(s.annualized_return)}</td>
                  <td class="px-4 py-2 text-right">{fmtNumber3(s.sharpe)}</td>
                  <td class="px-4 py-2 text-right">{fmtPercent(s.max_drawdown)}</td>
                  <td class="px-4 py-2 text-right">{fmtPercent(s.volatility)}</td>
                  <td class="px-4 py-2 text-right">{s.total_trades}</td>
                  <td class="px-4 py-2 text-right">{fmtPercent(s.win_rate)}</td>
                  <td class="px-4 py-2 text-right">{fmtCurrency(s.final_nav)}</td>
                {:else}
                  <td class="px-4 py-2 text-right text-muted-foreground" colspan="8">
                    {row.error ?? 'No summary available'}
                  </td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </Card.CardContent>
    </Card.Root>
  {/if}
</div>
