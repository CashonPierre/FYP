<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import EquityCurveChart, { type EquityPoint } from '$lib/components/charts/EquityCurveChart.svelte';
  import { BACKEND } from '$lib/config.js';

  type RunStatus = 'queued' | 'running' | 'completed' | 'failed';

  type BatchRun = {
    run_id: string;
    symbol: string;
    status: RunStatus;
    total_return: number | null;
    max_drawdown: number | null;
    sharpe: number | null;
    total_trades: number | null;
    error_message: string | null;
  };

  type BatchAggregate = {
    total_symbols: number;
    completed: number;
    failed: number;
    running: number;
    queued: number;
    best_symbol: string | null;
    best_return: number | null;
    worst_symbol: string | null;
    worst_return: number | null;
    avg_return: number | null;
  };

  type BatchStatus = {
    id: string;
    status: 'queued' | 'running' | 'completed' | 'failed' | 'partial';
    symbols: string[];
    runs: BatchRun[];
    aggregate: BatchAggregate;
    created_at: string;
    started_at: string | null;
    ended_at: string | null;
  };

  type CombinedSummary = {
    initial_capital: number;
    final_nav: number;
    total_return: number;
    annualized_return: number | null;
    max_drawdown: number | null;
    volatility: number | null;
    sharpe: number | null;
    sortino: number | null;
    calmar: number | null;
    total_trades: number;
    win_rate: number | null;
    fees: number;
    slippage: number;
  };

  type CombinedResults = {
    id: string;
    status: string;
    symbols: string[];
    skipped_symbols: string[];
    initial_capital: number;
    summary: CombinedSummary | null;
    equity: EquityPoint[];
  };

  const batchId = $derived(page.params.id ?? '');

  let batch = $state<BatchStatus | null>(null);
  // Universe mode: a single run whose settings span many symbols (cross-sectional
  // factor strategy). There is no genuine per-symbol data — the "run" already IS
  // the portfolio — so we collapse the per-symbol table and best/worst cells.
  const isUniverseMode = $derived(
    !!batch && batch.runs.length === 1 && batch.symbols.length > 1,
  );
  let loading = $state(true);
  let errMsg = $state<string | null>(null);
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  let combined = $state<CombinedResults | null>(null);
  let combinedLoading = $state(false);
  let combinedError = $state<string | null>(null);

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

  const fetchBatch = async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      toast.error('Not logged in');
      goto('/login');
      return;
    }
    try {
      const res = await fetch(`${BACKEND}/backtests/batch/${batchId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        if (res.status === 404) {
          errMsg = 'Batch not found';
          if (pollTimer) clearInterval(pollTimer);
        }
        return;
      }
      const data = (await res.json()) as BatchStatus;
      batch = data;
      if (data.status === 'completed' || data.status === 'failed' || data.status === 'partial') {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = null;
        // Only fetch the combined payload once the batch is done and at least
        // one symbol completed — nothing to pool otherwise.
        if (!combined && !combinedLoading && data.aggregate.completed > 0) {
          fetchCombined();
        }
      }
    } catch {
      // transient — keep polling
    } finally {
      loading = false;
    }
  };

  const fetchCombined = async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    combinedLoading = true;
    combinedError = null;
    try {
      const res = await fetch(`${BACKEND}/backtests/batch/${batchId}/combined`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        combinedError = `Failed to load combined view (HTTP ${res.status})`;
        return;
      }
      combined = (await res.json()) as CombinedResults;
    } catch (e) {
      combinedError = e instanceof Error ? e.message : 'Network error';
    } finally {
      combinedLoading = false;
    }
  };

  onMount(() => {
    fetchBatch();
    pollTimer = setInterval(fetchBatch, 2000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  let selected = $state<Set<string>>(new Set());

  const toggle = (runId: string) => {
    const next = new Set(selected);
    if (next.has(runId)) next.delete(runId);
    else next.add(runId);
    selected = next;
  };

  const compareSelected = () => {
    const ids = [...selected];
    if (ids.length < 2) {
      toast.error('Select at least 2 runs');
      return;
    }
    goto(`/app/backtests/compare?ids=${ids.join(',')}`);
  };

  const compareAllCompleted = () => {
    if (!batch) return;
    const ids = batch.runs.filter((r) => r.status === 'completed').map((r) => r.run_id);
    if (ids.length < 2) {
      toast.error('Need at least 2 completed runs');
      return;
    }
    goto(`/app/backtests/compare?ids=${ids.join(',')}`);
  };
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Batch Backtest</h1>
    <p class="text-sm text-muted-foreground">Batch id: {batchId}</p>
  </div>
  <div class="flex gap-2">
    <Button variant="outline" onclick={() => goto('/app/backtests')}>
      History
    </Button>
    <Button onclick={() => goto('/app/backtests/new')}>New Backtest</Button>
  </div>
</div>

<div class="mt-6 space-y-4">
  {#if loading && !batch}
    <div class="text-sm text-muted-foreground">Loading batch…</div>
  {:else if errMsg}
    <Card.Root class="border border-destructive">
      <Card.CardContent class="py-6">
        <p class="text-sm text-destructive">{errMsg}</p>
      </Card.CardContent>
    </Card.Root>
  {:else if batch}
    <Card.Root class="border">
      <Card.Header>
        <Card.Title class="text-base capitalize">{batch.status}</Card.Title>
        <Card.Description>
          {#if isUniverseMode}
            Universe run · {batch.symbols.length} symbols ranked cross-sectionally
          {:else}
            {batch.aggregate.completed} / {batch.aggregate.total_symbols} completed
            {#if batch.aggregate.failed > 0} · {batch.aggregate.failed} failed{/if}
            {#if batch.aggregate.running > 0} · {batch.aggregate.running} running{/if}
            {#if batch.aggregate.queued > 0} · {batch.aggregate.queued} queued{/if}
          {/if}
        </Card.Description>
      </Card.Header>
      <Card.CardContent>
        {#if isUniverseMode}
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <div class="text-xs text-muted-foreground">Mode</div>
              <div class="text-lg font-medium">Cross-sectional</div>
            </div>
            <div>
              <div class="text-xs text-muted-foreground">Universe Size</div>
              <div class="text-lg font-medium">{batch.symbols.length} symbols</div>
            </div>
          </div>
        {:else}
          <div class="grid gap-4 sm:grid-cols-4">
            <div>
              <div class="text-xs text-muted-foreground">Avg Return</div>
              <div class="text-lg font-medium">
                {fmtPercent(batch.aggregate.avg_return)}
              </div>
            </div>
            <div>
              <div class="text-xs text-muted-foreground">Best</div>
              <div class="text-lg font-medium text-green-600">
                {batch.aggregate.best_symbol ?? '—'}
                {#if batch.aggregate.best_return != null}
                  <span class="text-xs">({fmtPercent(batch.aggregate.best_return)})</span>
                {/if}
              </div>
            </div>
            <div>
              <div class="text-xs text-muted-foreground">Worst</div>
              <div class="text-lg font-medium text-destructive">
                {batch.aggregate.worst_symbol ?? '—'}
                {#if batch.aggregate.worst_return != null}
                  <span class="text-xs">({fmtPercent(batch.aggregate.worst_return)})</span>
                {/if}
              </div>
            </div>
            <div>
              <div class="text-xs text-muted-foreground">Symbols</div>
              <div class="text-lg font-medium">{batch.aggregate.total_symbols}</div>
            </div>
          </div>
        {/if}
      </Card.CardContent>
    </Card.Root>

    {#if combined || combinedLoading || combinedError}
      <Card.Root class="border">
        <Card.Header>
          <Card.Title class="text-base">
            {isUniverseMode ? 'Portfolio Performance' : 'Combined Portfolio'}
          </Card.Title>
          <Card.Description>
            {#if isUniverseMode}
              Cross-sectional factor portfolio — the strategy ranks the universe
              every bar and holds the top selections as one pooled NAV.
            {:else}
              Equal-weight pool of every completed symbol (each gets
              initial_capital / N). Misaligned coverage is forward-filled.
            {/if}
          </Card.Description>
        </Card.Header>
        <Card.CardContent>
          {#if combinedLoading && !combined}
            <div class="text-sm text-muted-foreground">Loading combined view…</div>
          {:else if combinedError}
            <div class="text-sm text-destructive">{combinedError}</div>
          {:else if combined && combined.summary}
            <div class="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
              <div>
                <div class="text-xs text-muted-foreground">Total Return</div>
                <div class="text-lg font-medium {combined.summary.total_return >= 0 ? 'text-green-600' : 'text-destructive'}">
                  {fmtPercent(combined.summary.total_return)}
                </div>
              </div>
              <div>
                <div class="text-xs text-muted-foreground">Annualized</div>
                <div class="text-lg font-medium">
                  {fmtPercent(combined.summary.annualized_return)}
                </div>
              </div>
              <div>
                <div class="text-xs text-muted-foreground">Sharpe</div>
                <div class="text-lg font-medium">
                  {fmtNumber3(combined.summary.sharpe)}
                </div>
              </div>
              <div>
                <div class="text-xs text-muted-foreground">Max DD</div>
                <div class="text-lg font-medium text-destructive">
                  {fmtPercent(combined.summary.max_drawdown)}
                </div>
              </div>
              <div>
                <div class="text-xs text-muted-foreground">Volatility</div>
                <div class="text-lg font-medium">
                  {fmtPercent(combined.summary.volatility)}
                </div>
              </div>
              <div>
                <div class="text-xs text-muted-foreground">Trades</div>
                <div class="text-lg font-medium">{combined.summary.total_trades}</div>
              </div>
            </div>
            <div class="mt-4 text-xs text-muted-foreground">
              Pooled {combined.symbols.length} symbol{combined.symbols.length === 1 ? '' : 's'}
              · Initial capital ${combined.initial_capital.toLocaleString()}
              {#if combined.skipped_symbols.length > 0}
                · Skipped: <span class="text-destructive">{combined.skipped_symbols.join(', ')}</span>
              {/if}
            </div>
            {#if combined.equity.length > 1}
              <div class="mt-4">
                <EquityCurveChart points={combined.equity} height={260} />
              </div>
            {/if}
          {:else if combined}
            <div class="text-sm text-muted-foreground">
              No completed runs to combine yet.
            </div>
          {/if}
        </Card.CardContent>
      </Card.Root>
    {/if}

    {#if !isUniverseMode}
    <Card.Root class="border">
      <Card.Header class="flex flex-row items-start justify-between gap-4 space-y-0">
        <div class="space-y-1">
          <Card.Title class="text-base">Per-Symbol Results</Card.Title>
          <Card.Description>
            {selected.size > 0
              ? `${selected.size} selected`
              : 'Tick runs to compare them, or compare all completed.'}
          </Card.Description>
        </div>
        <div class="flex gap-2">
          {#if selected.size > 0}
            <Button variant="ghost" onclick={() => (selected = new Set())}>Clear</Button>
            <Button variant="outline" onclick={compareSelected} disabled={selected.size < 2}>
              Compare Selected ({selected.size})
            </Button>
          {/if}
          <Button
            variant="outline"
            onclick={compareAllCompleted}
            disabled={batch.aggregate.completed < 2}
          >
            Compare All Completed
          </Button>
        </div>
      </Card.Header>
      <Card.CardContent class="overflow-x-auto p-0">
        <table class="w-full text-sm">
          <thead class="border-b bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th class="w-10 px-4 py-2"></th>
              <th class="px-4 py-2 text-left font-medium">Symbol</th>
              <th class="px-4 py-2 text-left font-medium">Status</th>
              <th class="px-4 py-2 text-right font-medium">Return</th>
              <th class="px-4 py-2 text-right font-medium">Sharpe</th>
              <th class="px-4 py-2 text-right font-medium">Max DD</th>
              <th class="px-4 py-2 text-right font-medium">Trades</th>
              <th class="px-4 py-2 text-right font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {#each batch.runs as run (run.run_id)}
              <tr class="border-b last:border-b-0 hover:bg-muted/30">
                <td class="px-4 py-2">
                  <input
                    type="checkbox"
                    class="h-4 w-4 accent-primary disabled:opacity-40"
                    checked={selected.has(run.run_id)}
                    disabled={run.status !== 'completed'}
                    onchange={() => toggle(run.run_id)}
                  />
                </td>
                <td class="px-4 py-2 font-medium">{run.symbol}</td>
                <td class="px-4 py-2 capitalize {statusColor[run.status]}">{run.status}</td>
                <td class="px-4 py-2 text-right {run.total_return != null && run.total_return >= 0 ? 'text-green-600' : run.total_return != null ? 'text-destructive' : ''}">
                  {fmtPercent(run.total_return)}
                </td>
                <td class="px-4 py-2 text-right">{fmtNumber3(run.sharpe)}</td>
                <td class="px-4 py-2 text-right">{fmtPercent(run.max_drawdown)}</td>
                <td class="px-4 py-2 text-right">{run.total_trades ?? '—'}</td>
                <td class="px-4 py-2 text-right">
                  <button
                    class="text-primary hover:underline"
                    onclick={() => goto(`/app/backtests/${run.run_id}`)}
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
  {/if}
</div>
