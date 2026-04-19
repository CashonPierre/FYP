<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button/index.js';

  let loggedIn = $state(false);

  onMount(() => {
    loggedIn = !!localStorage.getItem('token');
  });

  const primaryCta = () => goto(loggedIn ? '/app/backtests/new' : '/signup');
  const secondaryCta = () => goto(loggedIn ? '/app/backtests' : '/login');
</script>

<div class="flex min-h-screen flex-col">
  <header class="flex items-center justify-between border-b px-8 py-4">
    <a href="/" class="font-semibold tracking-tight">Quant Backtester</a>
    <div class="flex items-center gap-3">
      {#if loggedIn}
        <Button variant="ghost" onclick={() => goto('/app/docs')}>Docs</Button>
        <Button onclick={() => goto('/app/backtests/new')}>Open app</Button>
      {:else}
        <Button variant="ghost" onclick={() => goto('/login')}>Log in</Button>
        <Button onclick={() => goto('/signup')}>Get started</Button>
      {/if}
    </div>
  </header>

  <main class="flex flex-1 flex-col">
    <section class="mx-auto grid w-full max-w-6xl items-center gap-10 px-6 py-16 md:grid-cols-2 md:py-24">
      <div class="space-y-5">
        <span class="inline-block rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground">
          Final Year Project · No-code backtesting
        </span>
        <h1 class="text-4xl font-bold tracking-tight sm:text-5xl">
          Build and backtest trading strategies — visually.
        </h1>
        <p class="text-lg text-muted-foreground">
          Drag-and-drop blocks — indicators, conditions, risk, and sizing — run them on real historical data,
          and review the equity curve, trade log, and metrics. Works across single assets, multi-asset batches,
          factor universes, and your own uploaded data.
        </p>
        <div class="flex flex-wrap items-center gap-3 pt-1">
          <Button size="lg" onclick={primaryCta}>
            {loggedIn ? 'Open builder' : 'Get started free'}
          </Button>
          <Button size="lg" variant="outline" onclick={secondaryCta}>
            {loggedIn ? 'View history' : 'Log in'}
          </Button>
        </div>
      </div>

      <div class="rounded-xl border bg-card p-4 shadow-sm">
        <svg viewBox="0 0 480 300" class="h-full w-full" aria-hidden="true">
          <rect x="8" y="8" width="120" height="284" rx="8" fill="var(--muted)" opacity="0.4" />
          <text x="20" y="30" font-size="11" fill="var(--muted-foreground)">Palette</text>
          {#each ['OnBar', 'SMA', 'RSI', 'IfAbove', 'Buy', 'Sell'] as label, i (label)}
            <rect x="20" y={50 + i * 34} width="96" height="24" rx="4"
              fill="var(--background)" stroke="var(--border)" />
            <text x="30" y={66 + i * 34} font-size="11" fill="var(--foreground)">{label}</text>
          {/each}

          <rect x="140" y="8" width="332" height="284" rx="8" fill="var(--background)" stroke="var(--border)" />
          <rect x="170" y="40" width="110" height="50" rx="6" fill="var(--primary)" opacity="0.15" stroke="var(--primary)" />
          <text x="185" y="70" font-size="12" font-weight="600" fill="var(--primary)">OnBar</text>

          <rect x="310" y="40" width="110" height="50" rx="6" fill="var(--chart-2)" opacity="0.2" stroke="var(--chart-2)" />
          <text x="332" y="70" font-size="12" font-weight="600" fill="var(--chart-2)">RSI &lt; 30</text>

          <rect x="170" y="150" width="110" height="50" rx="6" fill="var(--chart-2)" opacity="0.2" stroke="var(--chart-2)" />
          <text x="195" y="180" font-size="12" font-weight="600" fill="var(--chart-2)">Buy 100%</text>

          <rect x="310" y="150" width="110" height="50" rx="6" fill="var(--destructive)" opacity="0.15" stroke="var(--destructive)" />
          <text x="335" y="180" font-size="12" font-weight="600" fill="var(--destructive)">Sell 100%</text>

          <path d="M 280 65 L 310 65" stroke="var(--muted-foreground)" stroke-width="1.5" fill="none" />
          <path d="M 225 90 L 225 150" stroke="var(--muted-foreground)" stroke-width="1.5" fill="none" />
          <path d="M 365 90 L 365 150" stroke="var(--muted-foreground)" stroke-width="1.5" fill="none" />

          <path d="M 160 260 L 190 240 L 220 250 L 250 225 L 280 232 L 310 215 L 340 220 L 370 205 L 400 210 L 430 195 L 460 200"
            fill="none" stroke="var(--primary)" stroke-width="2" />
        </svg>
      </div>
    </section>

    <section class="border-t bg-muted/30 px-6 py-14">
      <div class="mx-auto max-w-5xl">
        <h2 class="text-2xl font-semibold tracking-tight">How it works</h2>
        <div class="mt-8 grid gap-6 sm:grid-cols-3">
          {#each [
            { step: '1', title: 'Build', body: 'Drop triggers, indicators, conditions, risk, and sizing blocks onto the canvas — or start from one of 20 ready-made templates.' },
            { step: '2', title: 'Backtest', body: 'Pick a single symbol, a multi-asset batch, a factor universe, or your own uploaded dataset. Run against historical OHLC data.' },
            { step: '3', title: 'Analyse', body: 'Review the equity curve vs. benchmark, per-trade log, and metrics: Sharpe, Sortino, max drawdown, CAGR, Calmar, win rate.' },
          ] as item (item.step)}
            <div class="rounded-lg border bg-background p-5">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                {item.step}
              </div>
              <div class="mt-3 text-base font-semibold">{item.title}</div>
              <p class="mt-1 text-sm text-muted-foreground">{item.body}</p>
            </div>
          {/each}
        </div>
      </div>
    </section>

    <section class="px-6 py-14">
      <div class="mx-auto max-w-5xl">
        <h2 class="text-2xl font-semibold tracking-tight">What's in the box</h2>
        <div class="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div class="space-y-2">
            <div class="text-sm font-semibold">Four asset modes</div>
            <p class="text-sm text-muted-foreground">
              Single symbol, multi-symbol batch, cross-sectional factor universe, or your own uploaded data (BYOD).
            </p>
          </div>
          <div class="space-y-2">
            <div class="text-sm font-semibold">15+ indicators</div>
            <p class="text-sm text-muted-foreground">
              SMA, EMA, RSI, MACD, Bollinger, ATR, Stochastic, ROC, Williams %R, CCI, KDJ, MFI, OBV, KST, Volume — every one documented.
            </p>
          </div>
          <div class="space-y-2">
            <div class="text-sm font-semibold">Flexible sizing</div>
            <p class="text-sm text-muted-foreground">
              Buy by units, % of equity, or fixed dollar. Sell all, partial %, or fixed units. Attach StopLoss, TakeProfit, and TrailingStop.
            </p>
          </div>
          <div class="space-y-2">
            <div class="text-sm font-semibold">Factor strategies</div>
            <p class="text-sm text-muted-foreground">
              Rank a universe by Momentum, Reversal, Low-Vol, or Liquidity. Long-only or long/short dollar-neutral with scheduled rebalance.
            </p>
          </div>
          <div class="space-y-2">
            <div class="text-sm font-semibold">Bring your own data</div>
            <p class="text-sm text-muted-foreground">
              Upload CSV bars for any symbol and run the same strategies you'd run on built-in market data.
            </p>
          </div>
          <div class="space-y-2">
            <div class="text-sm font-semibold">Results dashboard</div>
            <p class="text-sm text-muted-foreground">
              Candlestick chart with buy/sell markers, equity curve vs. benchmark, Sharpe / Sortino / drawdown / CAGR / Calmar, full trade log.
            </p>
          </div>
        </div>
      </div>
    </section>

    <section class="border-t bg-muted/30 px-6 py-14">
      <div class="mx-auto max-w-5xl text-center">
        <h2 class="text-2xl font-semibold tracking-tight">Documented every step</h2>
        <p class="mx-auto mt-3 max-w-2xl text-sm text-muted-foreground">
          Every node in the palette has a "?" icon that opens a reference page covering its inputs, outputs, parameters,
          and example use. New users can load a template and trace through the graph with the docs side-by-side.
        </p>
        <div class="mt-6">
          <Button variant="outline" onclick={() => goto('/app/docs')}>Browse docs</Button>
        </div>
      </div>
    </section>
  </main>

  <footer class="border-t px-8 py-6 text-center text-xs text-muted-foreground">
    Quant Backtester · Final Year Project ·
    <a
      class="underline hover:text-foreground"
      href="https://github.com/Quant-Backtester/FYP"
      target="_blank"
      rel="noopener noreferrer"
    >GitHub</a>
  </footer>
</div>
