<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { Skeleton } from '$lib/components/ui/skeleton/index.js';
  import { EmptyState } from '$lib/components/ui/empty-state/index.js';
  import { FlaskConical, Layers } from '@lucide/svelte';
  import { BACKEND } from '$lib/config.js';

  type RunStatus = 'queued' | 'running' | 'completed' | 'failed';
  type BatchStatus = 'queued' | 'running' | 'completed' | 'failed' | 'partial';

  type BacktestListItem = {
    id: string;
    status: RunStatus;
    symbol: string | null;
    timeframe: string;
    created_at: string;
    total_return: number | null;
    batch_id: string | null;
  };

  type BatchListItem = {
    id: string;
    status: BatchStatus;
    symbols: string[];
    total_symbols: number;
    completed: number;
    failed: number;
    created_at: string;
    ended_at: string | null;
    avg_return: number | null;
    execution_mode: string | null;
    strategy_name: string | null;
  };

  type Tab = 'runs' | 'batches';

  let activeTab = $state<Tab>('runs');

  let runs = $state<BacktestListItem[]>([]);
  let runsLoading = $state(true);
  let selected = $state<Set<string>>(new Set());

  let batches = $state<BatchListItem[]>([]);
  let batchesLoading = $state(false);
  let batchesLoaded = $state(false);

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selected = next;
  };

  const clearSelection = () => {
    selected = new Set();
  };

  const compareSelected = () => {
    const ids = [...selected];
    if (ids.length < 2) {
      toast.error('Select at least 2 runs to compare');
      return;
    }
    goto(`/app/backtests/compare?ids=${ids.join(',')}`);
  };

  const statusColor: Record<RunStatus, string> = {
    queued: 'text-muted-foreground',
    running: 'text-blue-500',
    completed: 'text-green-600',
    failed: 'text-destructive',
  };

  const batchStatusColor: Record<BatchStatus, string> = {
    queued: 'text-muted-foreground',
    running: 'text-blue-500',
    completed: 'text-green-600',
    failed: 'text-destructive',
    partial: 'text-amber-600',
  };

  const percent = new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
    signDisplay: 'exceptZero',
  });

  const fmtDate = (iso: string) =>
    new Date(iso).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  // Truncate long symbol lists for display, e.g. 20 symbols → "AAPL, MSFT, GOOGL, …"
  const fmtSymbols = (symbols: string[]) => {
    if (symbols.length === 0) return '—';
    if (symbols.length <= 3) return symbols.join(', ');
    return `${symbols.slice(0, 3).join(', ')}, +${symbols.length - 3} more`;
  };

  const loadRuns = async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    runsLoading = true;
    try {
      const res = await fetch(`${BACKEND}/backtests`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        toast.error('Failed to load backtest history');
        return;
      }
      runs = await res.json();
    } catch {
      toast.error('Could not reach backend');
    } finally {
      runsLoading = false;
    }
  };

  const loadBatches = async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    batchesLoading = true;
    try {
      const res = await fetch(`${BACKEND}/backtests/batches`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        toast.error('Failed to load batch history');
        return;
      }
      batches = await res.json();
      batchesLoaded = true;
    } catch {
      toast.error('Could not reach backend');
    } finally {
      batchesLoading = false;
    }
  };

  const switchTab = (tab: Tab) => {
    activeTab = tab;
    if (tab === 'batches' && !batchesLoaded && !batchesLoading) {
      loadBatches();
    }
  };

  onMount(loadRuns);
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Backtest History</h1>
    <p class="text-sm text-muted-foreground">
      {#if activeTab === 'runs'}
        {selected.size > 0
          ? `${selected.size} selected — pick 2 or more to compare`
          : 'Tick two or more runs to compare them side-by-side.'}
      {:else}
        Multi-symbol and universe batches grouped into one row each.
      {/if}
    </p>
  </div>
  <div class="flex items-center gap-2">
    {#if activeTab === 'runs' && selected.size > 0}
      <Button variant="ghost" onclick={clearSelection}>Clear</Button>
      <Button variant="outline" onclick={compareSelected} disabled={selected.size < 2}>
        Compare ({selected.size})
      </Button>
    {/if}
    <Button onclick={() => goto('/app/backtests/new')}>New Backtest</Button>
  </div>
</div>

<div class="mt-6 inline-flex rounded-lg border bg-muted/40 p-1">
  <button
    type="button"
    class="rounded-md px-4 py-1.5 text-sm font-medium transition-colors {activeTab === 'runs'
      ? 'bg-background text-foreground shadow-sm'
      : 'text-muted-foreground hover:text-foreground'}"
    onclick={() => switchTab('runs')}
  >
    Runs
  </button>
  <button
    type="button"
    class="rounded-md px-4 py-1.5 text-sm font-medium transition-colors {activeTab === 'batches'
      ? 'bg-background text-foreground shadow-sm'
      : 'text-muted-foreground hover:text-foreground'}"
    onclick={() => switchTab('batches')}
  >
    Batches
  </button>
</div>

<div class="mt-4">
  {#if activeTab === 'runs'}
    {#if runsLoading}
      <div class="space-y-2">
        {#each Array(4) as _, i (i)}
          <Skeleton class="h-20 w-full" />
        {/each}
      </div>
    {:else if runs.length === 0}
      <EmptyState
        icon={FlaskConical}
        title="No backtest runs yet"
        description="Build a strategy in the visual editor, pick a symbol and date range, and run your first backtest to see equity curve, trades and performance metrics here."
      >
        {#snippet action()}
          <Button onclick={() => goto('/app/backtests/new')}>Create your first backtest</Button>
        {/snippet}
      </EmptyState>
    {:else}
      <div class="space-y-2">
        {#each runs as run (run.id)}
          {@const canCompare = run.status === 'completed'}
          <Card.Root class="border">
            <Card.CardContent class="flex items-center justify-between py-4">
              <div class="flex items-center gap-4">
                <input
                  type="checkbox"
                  class="h-4 w-4 accent-primary disabled:opacity-40"
                  checked={selected.has(run.id)}
                  disabled={!canCompare}
                  title={canCompare ? 'Select to compare' : 'Only completed runs can be compared'}
                  onclick={(e) => e.stopPropagation()}
                  onchange={() => toggle(run.id)}
                />
                <button
                  type="button"
                  class="flex flex-1 items-center gap-6 text-left hover:opacity-80"
                  onclick={() => goto(`/app/backtests/${run.id}`)}
                >
                  <div>
                    <div class="font-medium">{run.symbol ?? 'Universe'}</div>
                    <div class="text-xs text-muted-foreground">{run.timeframe}</div>
                  </div>
                  <div>
                    <div class="text-xs text-muted-foreground">Created</div>
                    <div class="text-sm">{fmtDate(run.created_at)}</div>
                  </div>
                </button>
              </div>
              <div class="flex items-center gap-6">
                {#if run.total_return != null}
                  <div class="text-right">
                    <div class="text-xs text-muted-foreground">Return</div>
                    <div class="font-medium {run.total_return >= 0 ? 'text-green-600' : 'text-destructive'}">
                      {percent.format(run.total_return)}
                    </div>
                  </div>
                {/if}
                <div class="text-right">
                  <div class="text-xs text-muted-foreground">Status</div>
                  <div class="text-sm font-medium capitalize {statusColor[run.status]}">
                    {run.status}
                  </div>
                </div>
              </div>
            </Card.CardContent>
          </Card.Root>
        {/each}
      </div>
    {/if}
  {:else}
    {#if batchesLoading}
      <div class="space-y-2">
        {#each Array(3) as _, i (i)}
          <Skeleton class="h-20 w-full" />
        {/each}
      </div>
    {:else if batches.length === 0}
      <EmptyState
        icon={Layers}
        title="No batches yet"
        description="Batches appear here when you run a multi-symbol or universe backtest — each batch groups its child runs into a single entry."
      >
        {#snippet action()}
          <Button onclick={() => goto('/app/backtests/new')}>Create a batch backtest</Button>
        {/snippet}
      </EmptyState>
    {:else}
      <div class="space-y-2">
        {#each batches as batch (batch.id)}
          <Card.Root class="border">
            <Card.CardContent class="flex items-center justify-between py-4">
              <button
                type="button"
                class="flex flex-1 items-center gap-6 text-left hover:opacity-80"
                onclick={() => goto(`/app/backtests/batch/${batch.id}`)}
              >
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">{fmtSymbols(batch.symbols)}</span>
                    {#if batch.execution_mode === 'universe'}
                      <span class="rounded-sm bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-primary">
                        Universe
                      </span>
                    {/if}
                  </div>
                  <div class="text-xs text-muted-foreground">
                    {batch.total_symbols} symbol{batch.total_symbols === 1 ? '' : 's'}
                    {#if batch.strategy_name} · {batch.strategy_name}{/if}
                  </div>
                </div>
                <div>
                  <div class="text-xs text-muted-foreground">Created</div>
                  <div class="text-sm">{fmtDate(batch.created_at)}</div>
                </div>
                <div>
                  <div class="text-xs text-muted-foreground">Progress</div>
                  <div class="text-sm">
                    {batch.completed}/{batch.total_symbols}
                    {#if batch.failed > 0}
                      <span class="text-destructive">· {batch.failed} failed</span>
                    {/if}
                  </div>
                </div>
              </button>
              <div class="flex items-center gap-6">
                {#if batch.avg_return != null}
                  <div class="text-right">
                    <div class="text-xs text-muted-foreground">
                      {batch.execution_mode === 'universe' ? 'Return' : 'Avg Return'}
                    </div>
                    <div class="font-medium {batch.avg_return >= 0 ? 'text-green-600' : 'text-destructive'}">
                      {percent.format(batch.avg_return)}
                    </div>
                  </div>
                {/if}
                <div class="text-right">
                  <div class="text-xs text-muted-foreground">Status</div>
                  <div class="text-sm font-medium capitalize {batchStatusColor[batch.status]}">
                    {batch.status}
                  </div>
                </div>
              </div>
            </Card.CardContent>
          </Card.Root>
        {/each}
      </div>
    {/if}
  {/if}
</div>
