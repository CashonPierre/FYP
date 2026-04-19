<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { Skeleton } from '$lib/components/ui/skeleton/index.js';
  import { EmptyState } from '$lib/components/ui/empty-state/index.js';
  import { FlaskConical } from '@lucide/svelte';
  import { BACKEND } from '$lib/config.js';

  type RunStatus = 'queued' | 'running' | 'completed' | 'failed';

  type BacktestListItem = {
    id: string;
    status: RunStatus;
    symbol: string;
    timeframe: string;
    created_at: string;
    total_return: number | null;
  };

  let runs = $state<BacktestListItem[]>([]);
  let loading = $state(true);
  let selected = $state<Set<string>>(new Set());

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

  onMount(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;

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
      loading = false;
    }
  });
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Backtest History</h1>
    <p class="text-sm text-muted-foreground">
      {selected.size > 0
        ? `${selected.size} selected — pick 2 or more to compare`
        : 'Tick two or more runs to compare them side-by-side.'}
    </p>
  </div>
  <div class="flex items-center gap-2">
    {#if selected.size > 0}
      <Button variant="ghost" onclick={clearSelection}>Clear</Button>
      <Button variant="outline" onclick={compareSelected} disabled={selected.size < 2}>
        Compare ({selected.size})
      </Button>
    {/if}
    <Button onclick={() => goto('/app/backtests/new')}>New Backtest</Button>
  </div>
</div>

<div class="mt-6">
  {#if loading}
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
                  <div class="font-medium">{run.symbol}</div>
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
</div>
