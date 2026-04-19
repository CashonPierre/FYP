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

  type SweepAxis = {
    nodeLabel: string;
    paramKey: string;
    values: number[];
  };

  type StoredRun = {
    runId: string;
    // New shape: values indexed by axis. Legacy: single `value`.
    values?: number[];
    value?: number;
  };

  type SweepMeta = {
    id: string;
    // New shape
    axes?: SweepAxis[];
    runs: StoredRun[];
    createdAt: string;
    // Legacy shape
    nodeLabel?: string;
    paramKey?: string;
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
    values: number[]; // length 1 or 2
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

  // Heatmap metric selector (2-D only)
  type HeatMetric = 'sharpe' | 'total_return' | 'annualized_return' | 'max_drawdown';
  let heatMetric = $state<HeatMetric>('sharpe');

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

  // Normalise legacy 1-D metadata into the axes[] shape.
  const deriveAxes = (m: SweepMeta): SweepAxis[] => {
    if (m.axes && m.axes.length > 0) return m.axes;
    // Legacy — rebuild a single axis from runs[].value
    const values = m.runs
      .map((r) => (r.value ?? r.values?.[0]))
      .filter((v): v is number => typeof v === 'number');
    return [{
      nodeLabel: m.nodeLabel ?? '',
      paramKey: m.paramKey ?? 'value',
      values: Array.from(new Set(values)).sort((a, b) => a - b),
    }];
  };

  const axes = $derived.by<SweepAxis[]>(() => (meta ? deriveAxes(meta) : []));
  const is2D = $derived.by(() => axes.length >= 2);

  const pollAll = async () => {
    const token = localStorage.getItem('token');
    if (!token || !meta) return;

    const updated: SweepRow[] = await Promise.all(
      meta.runs.map(async (r, i): Promise<SweepRow> => {
        const vs = r.values ?? (r.value != null ? [r.value] : []);
        const prev = rows[i] ?? {
          values: vs,
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
        values: r.values ?? (r.value != null ? [r.value] : []),
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

  // Sort by first axis, then second (for tables / line chart)
  const sortedRows = $derived.by(() => [...rows].sort((a, b) => {
    const d0 = (a.values[0] ?? 0) - (b.values[0] ?? 0);
    if (d0 !== 0) return d0;
    return (a.values[1] ?? 0) - (b.values[1] ?? 0);
  }));

  // Sharpe-ranked rows (null sharpe → bottom)
  const sharpeRanked = $derived.by(() =>
    [...rows]
      .filter((r) => r.summary != null && r.summary.sharpe != null)
      .sort((a, b) => (b.summary!.sharpe ?? -Infinity) - (a.summary!.sharpe ?? -Infinity))
  );

  const rowLabel = (r: SweepRow): string => {
    if (axes.length === 0) return '';
    return axes
      .map((ax, i) => `${ax.paramKey}=${r.values[i]}`)
      .join(', ');
  };

  const equitySeries = $derived.by<EquitySeries[]>(() => {
    return sortedRows
      .filter((r) => r.equity.length > 0)
      .slice(0, 12) // keep readable when 15+ runs on one chart
      .map((r) => ({ label: rowLabel(r), points: r.equity }));
  });

  // Best run by Sharpe (2-D) or total_return (1-D, preserving old behaviour)
  const best = $derived.by<SweepRow | null>(() => {
    if (is2D) return sharpeRanked[0] ?? null;
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

  // -------------------------------------------------------------------------
  // Heatmap — 2-D only
  // -------------------------------------------------------------------------

  const metricOf = (s: ApiSummary | null, m: HeatMetric): number | null => {
    if (!s) return null;
    return s[m];
  };

  const metricLabels: Record<HeatMetric, string> = {
    sharpe: 'Sharpe',
    total_return: 'Return',
    annualized_return: 'CAGR',
    max_drawdown: 'Max DD',
  };

  // Map axis values to cell index (lookup optimised for repeated reads)
  const axisIndex = (ax: SweepAxis, v: number) => ax.values.indexOf(v);

  // Grid [axis1 value index][axis0 value index] → row (for display rows=axis0, cols=axis1 is more natural)
  const heatGrid = $derived.by(() => {
    if (!is2D) return null;
    const [ax0, ax1] = axes;
    const grid: (SweepRow | null)[][] = Array.from({ length: ax0.values.length }, () =>
      Array.from({ length: ax1.values.length }, () => null),
    );
    for (const r of rows) {
      const i = axisIndex(ax0, r.values[0]);
      const j = axisIndex(ax1, r.values[1]);
      if (i < 0 || j < 0) continue;
      grid[i][j] = r;
    }
    return grid;
  });

  const heatRange = $derived.by(() => {
    if (!is2D) return null;
    let lo = Infinity;
    let hi = -Infinity;
    for (const r of rows) {
      const v = metricOf(r.summary, heatMetric);
      if (v == null || !Number.isFinite(v)) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null;
    return { lo, hi };
  });

  // Diverging red→white→green for metrics where higher-is-better (sharpe,
  // total_return, annualized_return), reversed for max_drawdown (where less
  // negative is better — we map drawdown directly, lo=worst, hi=least-bad).
  const colorFor = (v: number | null, lo: number, hi: number): string => {
    if (v == null || !Number.isFinite(v)) return 'var(--muted)';
    const span = hi - lo || 1;
    const t = (v - lo) / span; // 0..1
    // Red (bad) → yellow (mid) → green (good)
    // Simple HSL: 0° (red) at t=0, 60° (yellow) at t=0.5, 120° (green) at t=1
    const hue = 120 * t;
    const sat = 70;
    const light = 50;
    return `hsl(${hue}, ${sat}%, ${light}%)`;
  };

  const formatMetric = (v: number | null, m: HeatMetric): string => {
    if (v == null) return '—';
    if (m === 'sharpe') return number3.format(v);
    return percent.format(v);
  };
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Parameter Sweep</h1>
    {#if meta && axes.length > 0}
      <p class="text-sm text-muted-foreground">
        {#each axes as ax, i (i)}
          {#if i > 0}<span class="px-1">×</span>{/if}
          <span>{ax.nodeLabel}</span> · <span class="font-mono">{ax.paramKey}</span>
          <span class="text-xs">({ax.values.length})</span>
        {/each}
        · {rows.length} runs
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
            <div class="text-xs text-muted-foreground">
              {is2D ? 'Best (Sharpe)' : 'Best Value'}
            </div>
            <div class="text-lg font-medium text-green-600">
              {best ? rowLabel(best) : '—'}
              {#if best?.summary}
                <span class="text-xs">
                  ({is2D
                    ? fmtNumber3(best.summary.sharpe)
                    : fmtPercent(best.summary.total_return)})
                </span>
              {/if}
            </div>
          </div>
          <div>
            <div class="text-xs text-muted-foreground">Runs</div>
            <div class="text-lg font-medium">{rows.length}</div>
          </div>
          <div>
            <div class="text-xs text-muted-foreground">Created</div>
            <div class="text-sm">{new Date(meta.createdAt).toLocaleString()}</div>
          </div>
        </div>
      </Card.CardContent>
    </Card.Root>

    {#if is2D && heatGrid && heatRange}
      {@const ax0 = axes[0]}
      {@const ax1 = axes[1]}
      <Card.Root class="border">
        <Card.Header class="flex flex-row items-start justify-between gap-2">
          <div>
            <Card.Title class="text-base">Heatmap</Card.Title>
            <Card.Description>
              Rows: <span class="font-mono">{ax0.paramKey}</span> ·
              Columns: <span class="font-mono">{ax1.paramKey}</span> ·
              Color: {metricLabels[heatMetric]}
              (range {formatMetric(heatRange.lo, heatMetric)} → {formatMetric(heatRange.hi, heatMetric)})
            </Card.Description>
          </div>
          <select
            class="rounded-md border bg-background px-2 py-1 text-xs"
            bind:value={heatMetric}
          >
            <option value="sharpe">Sharpe</option>
            <option value="total_return">Total Return</option>
            <option value="annualized_return">Annualized Return</option>
            <option value="max_drawdown">Max Drawdown</option>
          </select>
        </Card.Header>
        <Card.CardContent class="overflow-x-auto">
          <table class="border-separate text-xs" style="border-spacing: 2px;">
            <thead>
              <tr>
                <th class="px-2 py-1 text-right text-muted-foreground">
                  <span class="font-mono">{ax0.paramKey}</span> \ <span class="font-mono">{ax1.paramKey}</span>
                </th>
                {#each ax1.values as v1 (v1)}
                  <th class="px-2 py-1 text-right font-mono font-normal text-muted-foreground">{v1}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each ax0.values as v0, i (v0)}
                <tr>
                  <td class="px-2 py-1 text-right font-mono text-muted-foreground">{v0}</td>
                  {#each ax1.values as _v1, j (_v1)}
                    {@const cell = heatGrid[i][j]}
                    {@const mv = cell ? metricOf(cell.summary, heatMetric) : null}
                    <td
                      class="h-10 min-w-[4rem] cursor-pointer rounded px-2 text-center text-[11px] font-medium transition hover:opacity-80"
                      style="background-color: {colorFor(mv, heatRange.lo, heatRange.hi)}; color: {mv == null ? 'var(--muted-foreground)' : 'white'}; text-shadow: {mv == null ? 'none' : '0 1px 1px rgba(0,0,0,0.45)'};"
                      title={cell
                        ? `${rowLabel(cell)}\nSharpe ${fmtNumber3(cell.summary?.sharpe)}\nReturn ${fmtPercent(cell.summary?.total_return)}\nMax DD ${fmtPercent(cell.summary?.max_drawdown)}`
                        : 'No data'}
                      onclick={() => cell && goto(`/app/backtests/${cell.runId}`)}
                    >
                      {formatMetric(mv, heatMetric)}
                    </td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
          <p class="mt-3 text-xs text-muted-foreground">
            Click any cell to open that run. A stable plateau of similar colors around the best
            cell indicates a robust parameter region; an isolated bright cell surrounded by dark
            ones is a cliff-adjacent point.
          </p>
        </Card.CardContent>
      </Card.Root>
    {/if}

    {#if equitySeries.length > 0}
      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">Equity Curves</Card.Title>
          <Card.Description>
            {is2D
              ? `First ${equitySeries.length} of ${rows.length} runs (sorted by ${axes[0]?.paramKey}).`
              : 'One line per parameter value.'}
          </Card.Description>
        </Card.Header>
        <Card.CardContent>
          <MultiEquityChart series={equitySeries} height={280} />
        </Card.CardContent>
      </Card.Root>
    {/if}

    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base">
          {is2D ? 'Runs ranked by Sharpe' : `Metrics by ${axes[0]?.paramKey ?? 'value'}`}
        </Card.Title>
      </Card.Header>
      <Card.CardContent class="overflow-x-auto p-0">
        <table class="w-full text-sm">
          <thead class="border-b bg-muted/40 text-xs text-muted-foreground">
            <tr>
              {#each axes as ax, i (i)}
                <th class="px-4 py-2 text-right font-medium font-mono">{ax.paramKey}</th>
              {/each}
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
            {#each (is2D ? sharpeRanked : sortedRows) as row (row.runId)}
              <tr class="border-b last:border-b-0 hover:bg-muted/30">
                {#each axes as _ax, i (i)}
                  <td class="px-4 py-2 text-right font-mono">{row.values[i] ?? '—'}</td>
                {/each}
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
