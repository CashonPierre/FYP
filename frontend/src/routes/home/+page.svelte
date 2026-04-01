<script lang="ts">
  import { goto } from '$app/navigation';
</script>

<div class="min-h-screen bg-linear-to-br from-gray-50 to-gray-100 p-6">
  <div class="mx-auto max-w-3xl space-y-6">
    <div class="space-y-2">
      <h1 class="text-3xl font-bold tracking-tight">Home</h1>
      <p class="text-muted-foreground">
        Temporary hub while UI routes are being built.
      </p>
    </div>

    <div class="grid gap-3 sm:grid-cols-2">
      <button
        class="rounded-lg border bg-background p-4 text-left shadow-sm hover:bg-accent transition-colors"
        onclick={() => goto('/app/backtests/new')}
      >
        <div class="font-medium">New Backtest (builder)</div>
        <div class="text-sm text-muted-foreground">
          Builder UI skeleton (palette/canvas/inspector) + mocked run.
        </div>
      </button>

      <button
        class="rounded-lg border bg-background p-4 text-left shadow-sm hover:bg-accent transition-colors"
        onclick={() => goto('/login')}
      >
        <div class="font-medium">Login</div>
        <div class="text-sm text-muted-foreground">
          Auth UI (backend integration pending).
        </div>
      </button>
    </div>

    <button
      class="w-full rounded-lg border bg-background p-4 text-left shadow-sm hover:bg-accent transition-colors"
      onclick={() => goto('/backtest/input')}
    >
      <div class="font-medium">Legacy Backtest Form</div>
      <div class="text-sm text-muted-foreground">
        The original `/backtest/input` form + simulated job id redirect.
      </div>
    </button>
  </div>
</div>
