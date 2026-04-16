<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';

  const BACKEND = 'http://localhost:8000';

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
    <p class="text-sm text-muted-foreground">All your past backtest runs.</p>
  </div>
  <Button onclick={() => goto('/app/backtests/new')}>New Backtest</Button>
</div>

<div class="mt-6">
  {#if loading}
    <div class="text-sm text-muted-foreground">Loading…</div>
  {:else if runs.length === 0}
    <div class="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
      No backtest runs yet.
      <button
        class="ml-1 font-medium text-primary hover:underline"
        onclick={() => goto('/app/backtests/new')}
      >
        Create one now.
      </button>
    </div>
  {:else}
    <div class="space-y-2">
      {#each runs as run (run.id)}
        <Card.Root
          class="border cursor-pointer hover:bg-muted/40 transition-colors"
          onclick={() => goto(`/app/backtests/${run.id}`)}
        >
          <Card.CardContent class="flex items-center justify-between py-4">
            <div class="flex items-center gap-6">
              <div>
                <div class="font-medium">{run.symbol}</div>
                <div class="text-xs text-muted-foreground">{run.timeframe}</div>
              </div>
              <div>
                <div class="text-xs text-muted-foreground">Created</div>
                <div class="text-sm">{fmtDate(run.created_at)}</div>
              </div>
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
