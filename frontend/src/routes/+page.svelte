<script lang="ts">
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button/index.js';
</script>

<div class="flex min-h-screen flex-col">
  <!-- Nav -->
  <header class="flex items-center justify-between px-8 py-4 border-b">
    <span class="font-semibold tracking-tight">Quant Backtester</span>
    <div class="flex items-center gap-3">
      <Button variant="ghost" onclick={() => goto('/login')}>Log in</Button>
      <Button onclick={() => goto('/signup')}>Get started</Button>
    </div>
  </header>

  <!-- Hero -->
  <main class="flex flex-1 flex-col items-center justify-center px-6 text-center gap-6">
    <div class="max-w-2xl space-y-4">
      <h1 class="text-4xl font-bold tracking-tight sm:text-5xl">
        Build and backtest trading strategies — visually
      </h1>
      <p class="text-lg text-muted-foreground">
        Drag-and-drop strategy blocks, run backtests against historical market data,
        and analyse results with charts and performance metrics. No coding required.
      </p>
      <div class="flex items-center justify-center gap-3 pt-2">
        <Button size="lg" onclick={() => goto('/signup')}>Get started free</Button>
        <Button size="lg" variant="outline" onclick={() => goto('/login')}>Log in</Button>
      </div>
    </div>
  </main>

  <!-- Feature strip -->
  <section class="border-t px-8 py-12">
    <div class="mx-auto grid max-w-4xl gap-8 sm:grid-cols-3">
      <div class="space-y-2">
        <div class="text-sm font-semibold">Visual Strategy Builder</div>
        <p class="text-sm text-muted-foreground">
          Connect trigger and action blocks on a canvas to define your strategy logic without writing code.
        </p>
      </div>
      <div class="space-y-2">
        <div class="text-sm font-semibold">Historical Backtesting</div>
        <p class="text-sm text-muted-foreground">
          Run strategies against S&P 500 OHLC data and get P/L, win rate, drawdown, and trade-by-trade results.
        </p>
      </div>
      <div class="space-y-2">
        <div class="text-sm font-semibold">Results Dashboard</div>
        <p class="text-sm text-muted-foreground">
          Candlestick charts with buy/sell markers, equity curve, and a full summary of every backtest run.
        </p>
      </div>
    </div>
  </section>

  <footer class="border-t px-8 py-4 text-center text-xs text-muted-foreground">
    Quant Backtester — Final Year Project
  </footer>
</div>
