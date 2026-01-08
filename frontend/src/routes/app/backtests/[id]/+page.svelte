<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';

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

  const runId = $derived(page.params.id);
  const IMPORT_KEY = 'backtest:import:v0';

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

    const timer = setInterval(() => {
      progress = Math.min(100, progress + 12);
      if (progress >= 100) {
        status = 'completed';
        clearInterval(timer);
      }
    }, 250);

    return () => clearInterval(timer);
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

<div class="mt-6 grid gap-4 lg:grid-cols-[1fr_320px]">
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
            <Card.Description>Total Return</Card.Description>
            <Card.Title class="text-xl">+12.4%</Card.Title>
          </Card.Header>
        </Card.Root>
        <Card.Root class="border">
          <Card.Header>
            <Card.Description>Max Drawdown</Card.Description>
            <Card.Title class="text-xl">-4.1%</Card.Title>
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
          <Card.Title class="text-base">Equity Curve</Card.Title>
          <Card.Description>Chart placeholder.</Card.Description>
        </Card.Header>
        <Card.CardContent>
          <div class="h-64 rounded-md border bg-muted/30"></div>
        </Card.CardContent>
      </Card.Root>
    {/if}
  </section>

  <aside class="space-y-4">
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
