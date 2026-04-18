<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { BACKEND } from '$lib/config.js';

  type StrategyItem = {
    id: string;
    name: string;
    created_at: string;
    updated_at: string;
  };

  let strategies = $state<StrategyItem[]>([]);
  let loading = $state(true);
  let search = $state('');
  let deletingId = $state<string | null>(null);

  const fmtDate = (iso: string) =>
    new Date(iso).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  const requireToken = (): string | null => {
    const t = localStorage.getItem('token');
    if (!t) {
      toast.error('Not logged in');
      goto('/login');
      return null;
    }
    return t;
  };

  const loadAll = async () => {
    const token = requireToken();
    if (!token) return;

    try {
      const res = await fetch(`${BACKEND}/strategies`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        toast.error('Failed to load strategies');
        return;
      }
      strategies = await res.json();
    } catch {
      toast.error('Could not reach backend');
    } finally {
      loading = false;
    }
  };

  const openInBuilder = (s: StrategyItem) => {
    goto(`/app/backtests/new?strategyId=${s.id}`);
  };

  const deleteStrategy = async (s: StrategyItem) => {
    if (!confirm(`Delete strategy “${s.name}”? This cannot be undone.`)) return;
    const token = requireToken();
    if (!token) return;

    deletingId = s.id;
    try {
      const res = await fetch(`${BACKEND}/strategies/${s.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        toast.error('Delete failed');
        return;
      }
      strategies = strategies.filter((x) => x.id !== s.id);
      toast.success('Strategy deleted');
    } catch {
      toast.error('Could not reach backend');
    } finally {
      deletingId = null;
    }
  };

  onMount(loadAll);

  const filtered = $derived.by(() => {
    const q = search.trim().toLowerCase();
    if (!q) return strategies;
    return strategies.filter((s) => s.name.toLowerCase().includes(q));
  });
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Strategies</h1>
    <p class="text-sm text-muted-foreground">
      Saved strategy graphs. Open one in the builder to edit or run.
    </p>
  </div>
  <Button onclick={() => goto('/app/backtests/new')}>New Strategy</Button>
</div>

<div class="mt-6 sm:w-64">
  <Input type="search" placeholder="Search by name…" bind:value={search} />
</div>

<div class="mt-4">
  {#if loading}
    <div class="text-sm text-muted-foreground">Loading…</div>
  {:else if strategies.length === 0}
    <div class="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
      No saved strategies yet.
      <button
        class="ml-1 font-medium text-primary hover:underline"
        onclick={() => goto('/app/backtests/new')}
      >
        Build one.
      </button>
    </div>
  {:else if filtered.length === 0}
    <div class="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
      No strategies match your search.
    </div>
  {:else}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each filtered as s (s.id)}
        <Card.Root class="border">
          <Card.Header>
            <Card.Title class="truncate text-base">{s.name}</Card.Title>
            <Card.Description>
              Updated {fmtDate(s.updated_at)}
            </Card.Description>
          </Card.Header>
          <Card.CardContent class="flex justify-between gap-2 pb-4">
            <Button variant="outline" size="sm" onclick={() => openInBuilder(s)}>
              Open in Builder
            </Button>
            <Button
              variant="ghost"
              size="sm"
              class="text-destructive hover:text-destructive"
              disabled={deletingId === s.id}
              onclick={() => deleteStrategy(s)}
            >
              {deletingId === s.id ? 'Deleting…' : 'Delete'}
            </Button>
          </Card.CardContent>
        </Card.Root>
      {/each}
    </div>
  {/if}
</div>
