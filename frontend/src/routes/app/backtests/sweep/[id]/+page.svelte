<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import MultiEquityChart, { type EquitySeries } from '$lib/components/charts/MultiEquityChart.svelte';
  import { BACKEND } from '$lib/config.js';

  type RunStatus = 'queued' | 'running' | 'completed' | 'failed';

  type SweepMeta = {
    id: string;
    nodeLabel: string;
    paramKey: string;
    runs: { value: number; runId: string }[];
    createdAt: string;
  };

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
    series: { equity: { time: string; equity: number }[] };
  };

  type SweepRow = {
    value: number;
    runId: string;
    status: RunStatus;
    summary: ApiSummary | null;
    equity: { time: string; equity: number }[];
    error: string | null;
  };

  const sweepId = $derived(page.params.id ?? '');

  let meta = $state<SweepMeta | null>(null);
  let rows = $state<SweepRow[]>([]);
  let loading = $state(true);
  let missing = $state(false);
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  const percent = new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
    signDisplay: 'exceptZero',
  });
  const number3 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 });
  const fmtPercent = (v: number | null | undefined) => (v == null ? '—' : percent.format(v));
  const fmtNumber3 = (v: number | null | undefined) => (v == null ? '—' : number3.format(v));

  const statusColor: Record<RunStatus, string> = {
    queued: 'text-muted-foreground',
    running: 'text-blue-500',
    completed: 'text-green-600',
    failed: 'text-destructive',
  };

  const pollAll = async () => {
    const token = localStorage.getItem('token');
    if (!token || !meta) return;

    const updated: SweepRow[] = await Promise.all(
      meta.runs.map(async (r, i): Promise<SweepRow> => {
        const prev = rows[i] ?? {
          value: r.value,
          runId: r.runId,
          status: 'queued' as RunStatus,
          summary: null,
          equity: [],
          error: null,
        };

        if (prev.status === 'completed' || prev.status === 'failed') return prev;

        try {
          const statusRes = await fetch(`${BACKEND}/backtests/${r.runId}/status`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!statusRes.ok) return prev;
          const statusData = (await statusRes.json()) as { status: RunStatus; error_message?: string | null };
          const nextStatus = statusData.status;

          if (nextStatus === 'completed') {
            const res = await fetch(`${BACKEND}/backtests/${r.runId}/results`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) {
              return { ...prev, status: nextStatus };
            }
            const data = (await res.json()) as ApiResults;
            return {
              ...prev,
              status: nextStatus,
              summary: data.summary,
              equity: data.series.equity,
              error: null,
            };
          }
          return { ...prev, status: nextStatus, error: statusData.error_message ?? null };
        } catch {
          return prev;
        }
      })
    );
    rows = updated;

    const allDone = rows.every((r) => r.status === 'completed' || r.status === 'failed');
    if (allDone && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    loading = false;
  };

  onMount(() => {
    const raw = sessionStorage.getItem(`sweep:${sweepId}`);
    if (!raw) {
      missing = true;
      loading = false;
      return;
    }
    try {
      meta = JSON.parse(raw) as SweepMeta;
      rows = meta.runs.map((r) => ({
        value: r.value,
        runId: r.runId,
        status: 'queued',
        summary: null,
        equity: [],
        error: null,
      }));
    } catch {
      missing = true;
      loading = false;
      return;
    }

    pollAll();
    pollTimer = setInterval(pollAll, 2000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  const sortedRows = $derived.by(() => [...rows].sort((a, b) => a.value - b.value));

  const equitySeries = $derived.by<EquitySeries[]>(() => {
    const paramKey = meta?.paramKey ?? '';
    return sortedRows
      .filter((r) => r.equity.length > 0)
      .map((r) => ({ label: `${paramKey}=${r.value}`, points: r.equity }));
  });

  const best = $derived.by(() => {
    let b: SweepRow | null = null;
    for (const r of sortedRows) {
      if (r.summary == null) continue;
      if (b == null || r.summary.total_return > (b.summary?.total_return ?? -Infinity)) b = r;
    }
    return b;
  });

  const completedCount = $derived.by(() => rows.filter((r) => r.status === 'completed').length);
  const runningCount = $derived.by(() => rows.filter((r) => r.status === 'running' || r.status === 'queued').length);
  const failedCount = $derived.by(() => rows.filter((r) => r.status === 'failed').length);

  const compareAll = () => {
    const ids = sortedRows.filter((r) => r.status === 'completed').map((r) => r.runId);
    if (ids.length < 2) {
      toast.error('Need at least 2 completed runs');
      return;
    }
    goto(`/app/backtests/compare?ids=${ids.join(',')}`);
  };
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Parameter Sweep</h1>
    {#if meta}
      <p class="text-sm text-muted-foreground">
        {meta.nodeLabel} · <span class="font-mono">{meta.paramKey}</span> · {meta.runs.length} runs
      </p>
    {/if}
  </div>
  <div class="flex gap-2">
    <Button variant="outline" onclick={() => goto('/app/backtests')}>
      History
    </Button>
    <Button variant="outline" onclick={compareAll} disabled={completedCount < 2}>
      Compare All
    </Button>
    <Button onclick={() => goto('/app/backtests/new')}>New Backtest</Button>
  </div>
</div>

<div class="mt-6 space-y-4">
  {#if loading && !meta}
    <div class="text-sm text-muted-foreground">Loading sweep…</div>
  {:else if missing}
    <Card.Root class="border border-destructive">
      <Card.CardContent class="py-6">
        <p class="text-sm text-destructive">
          Sweep metadata not found. Sweeps are stored per-browser-tab; this sweep may be
          from a different session. Individual runs are still in History.
        </p>
      </Card.CardContent>
    </Card.Root>
  {:else if meta}
    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base">Progress</Card.Title>
        <Card.Description>
          {completedCount} completed · {runningCount} running · {failedCount} failed
        </Card.Description>
      </Card.Header>
      <Card.CardContent>
        <div class="grid gap-4 sm:grid-cols-3">
          <div>
            <div class="text-xs text-muted-foreground">Best Value</div>
            <div class="text-lg font-medium text-green-600">
              {best ? `${meta.paramKey}=${best.value}` : '—'}
              {#if best?.summary}
                <span class="text-xs">({fmtPercent(best.summary.total_return)})</span>
              {/if}
            </div>
          </div>
          <div>
            <div class="text-xs text-muted-foreground">Runs</div>
            <div class="text-lg font-medium">{meta.runs.length}</div>
          </div>
          <div>
            <div class="text-xs text-muted-foreground">Created</div>
            <div class="text-sm">{new Date(meta.createdAt).toLocaleString()}</div>
          </div>
        </div>
      </Card.CardContent>
    </Card.Root>

    {#if equitySeries.length > 0}
      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">Equity Curves</Card.Title>
          <Card.Description>One line per parameter value.</Card.Description>
        </Card.Header>
        <Card.CardContent>
          <MultiEquityChart series={equitySeries} height={280} />
        </Card.CardContent>
      </Card.Root>
    {/if}

    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base">Metrics by {meta.paramKey}</Card.Title>
      </Card.Header>
      <Card.CardContent class="overflow-x-auto p-0">
        <table class="w-full text-sm">
          <thead class="border-b bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th class="px-4 py-2 text-right font-medium">{meta.paramKey}</th>
              <th class="px-4 py-2 text-left font-medium">Status</th>
              <th class="px-4 py-2 text-right font-medium">Return</th>
              <th class="px-4 py-2 text-right font-medium">Annualized</th>
              <th class="px-4 py-2 text-right font-medium">Sharpe</th>
              <th class="px-4 py-2 text-right font-medium">Max DD</th>
              <th class="px-4 py-2 text-right font-medium">Trades</th>
              <th class="px-4 py-2 text-right font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {#each sortedRows as row (row.runId)}
              <tr class="border-b last:border-b-0 hover:bg-muted/30">
                <td class="px-4 py-2 text-right font-mono">{row.value}</td>
                <td class="px-4 py-2 capitalize {statusColor[row.status]}">{row.status}</td>
                <td class="px-4 py-2 text-right {row.summary && row.summary.total_return >= 0 ? 'text-green-600' : row.summary ? 'text-destructive' : ''}">
                  {fmtPercent(row.summary?.total_return)}
                </td>
                <td class="px-4 py-2 text-right">{fmtPercent(row.summary?.annualized_return)}</td>
                <td class="px-4 py-2 text-right">{fmtNumber3(row.summary?.sharpe)}</td>
                <td class="px-4 py-2 text-right">{fmtPercent(row.summary?.max_drawdown)}</td>
                <td class="px-4 py-2 text-right">{row.summary?.total_trades ?? '—'}</td>
                <td class="px-4 py-2 text-right">
                  <button
                    class="text-primary hover:underline"
                    onclick={() => goto(`/app/backtests/${row.runId}`)}
                  >
                    View →
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </Card.CardContent>
    </Card.Root>
  {/if}
</div>
