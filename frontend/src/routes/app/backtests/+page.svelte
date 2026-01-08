<script lang="ts">
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button/index.js';
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Backtest History</h1>
    <p class="text-sm text-muted-foreground">Placeholder list (wire to backend later).</p>
  </div>
  <Button onclick={() => goto('/app/backtests/new')}>New Backtest</Button>
</div>

<div class="mt-6 rounded-lg border bg-card p-4 text-sm text-muted-foreground">
  No saved runs yet. Use “New Backtest” to create a mocked run.
</div>

