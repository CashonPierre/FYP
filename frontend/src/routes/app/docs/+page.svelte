<script lang="ts">
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button/index.js';
  import { STRATEGY_TEMPLATES } from '$lib/strategies/templates.js';

  type NodeDoc = {
    type: string;
    title: string;
    oneLine: string;
    inputs: string;
    outputs: string;
    params?: string;
    detail: string;
  };

  type Section = {
    id: string;
    title: string;
    blurb: string;
    nodes: NodeDoc[];
  };

  const modes = [
    {
      id: 'mode-single',
      title: 'Single',
      body: 'One symbol, one price series. Simplest mode — the strategy graph runs bar-by-bar on that single asset.',
    },
    {
      id: 'mode-multi',
      title: 'Multi',
      body: 'N symbols you type in (comma-separated). The same strategy graph is run independently on each symbol and results are fanned out into a batch. Good for robustness checks.',
    },
    {
      id: 'mode-dataset',
      title: 'Dataset (BYOD)',
      body: 'Run on a CSV you uploaded in My Data. Same indicator / condition palette as Single; just a different data source.',
    },
    {
      id: 'mode-universe',
      title: 'Universe',
      body: 'Cross-sectional factor strategy: rank every stock in a universe by a single factor score, long the top decile and (optionally) short the bottom. The graph must be exactly one factor node feeding one Rank node — nothing else.',
    },
  ] as const;

  const sections: Section[] = [
    {
      id: 'sec-triggers',
      title: 'Triggers & Data',
      blurb: 'Sources that drive the graph. Every graph starts with an OnBar trigger; Data / Constant / Volume give you raw values to feed into conditions.',
      nodes: [
        { type: 'OnBar', title: 'On Bar', oneLine: 'Fires once per bar (daily/weekly/etc.).', inputs: '—', outputs: 'event', params: 'timeframe (e.g. 1D)', detail: 'Root of the graph. Indicators like SMA/EMA/RSI consume this event and emit updated values.' },
        { type: 'Data', title: 'Price Bars', oneLine: 'Live close of the current bar as a number.', inputs: '—', outputs: 'close (number)', detail: 'Use when a condition needs the raw close price (e.g. If Close > 200). Pair with IfAbove/IfBelow.' },
        { type: 'Constant', title: 'Constant', oneLine: 'Fixed numeric value (e.g. 30, 70).', inputs: '—', outputs: 'value (number)', params: 'value', detail: 'Usually the B side of an IfAbove / IfBelow comparison — e.g. RSI > 70.' },
        { type: 'Volume', title: 'Volume', oneLine: 'Volume of the current bar.', inputs: '—', outputs: 'volume (number)', detail: 'Compare against a Constant or a running average to detect breakouts or blackouts.' },
      ],
    },
    {
      id: 'sec-indicators-event',
      title: 'Indicators (price-based)',
      blurb: 'Indicators that consume the OnBar event and emit a number each bar. Wire OnBar → indicator → condition.',
      nodes: [
        { type: 'SMA', title: 'SMA', oneLine: 'Simple moving average of close.', inputs: 'event', outputs: 'value (number)', params: 'period', detail: 'Classic trend gauge. Crossing SMA(50) above SMA(200) is a golden cross.' },
        { type: 'EMA', title: 'EMA', oneLine: 'Exponential moving average — reacts faster than SMA.', inputs: 'event', outputs: 'value (number)', params: 'period', detail: 'Weights recent bars more heavily. Common periods: 9, 21, 55.' },
        { type: 'RSI', title: 'RSI', oneLine: 'Relative strength index (0–100).', inputs: 'event', outputs: 'value (number)', params: 'period, overbought, oversold', detail: '< 30 oversold, > 70 overbought. Feed into IfBelow/IfAbove with a Constant.' },
        { type: 'MACD', title: 'MACD', oneLine: 'MACD line, signal line, and histogram.', inputs: 'event', outputs: 'macd / signal / histogram (numbers)', params: 'fast, slow, signal', detail: 'Three output handles — wire macd into A and signal into B of IfCrossAbove for a trend-trigger.' },
        { type: 'BollingerBands', title: 'Bollinger Bands', oneLine: 'Upper / middle / lower bands around a moving average.', inputs: 'event', outputs: 'upper / middle / lower (numbers)', params: 'period, std', detail: 'Classic mean-reversion: buy when close < lower, sell when close > upper.' },
        { type: 'ROC', title: 'ROC', oneLine: 'Rate of change — % return over the last N bars.', inputs: 'event', outputs: 'value (number)', params: 'period', detail: 'Simple momentum gauge. Positive ROC = uptrend.' },
      ],
    },
    {
      id: 'sec-indicators-ohlcv',
      title: 'Indicators (OHLCV-based)',
      blurb: 'Indicators that read the full OHLCV bar directly — no event input needed. Wire the output straight into a condition.',
      nodes: [
        { type: 'ATR', title: 'ATR', oneLine: 'Average True Range (volatility).', inputs: '—', outputs: 'value (number)', params: 'period', detail: 'Use to detect volatility regimes or size stops proportional to range.' },
        { type: 'Stochastic', title: 'Stochastic', oneLine: '%K fast and %D slow oscillators (0–100).', inputs: '—', outputs: 'k / d (numbers)', params: 'k, d', detail: 'K crossing above D in oversold territory is a classic entry trigger.' },
        { type: 'WilliamsR', title: 'Williams %R', oneLine: 'Momentum oscillator (-100 to 0).', inputs: '—', outputs: 'value (number)', params: 'period', detail: '< -80 oversold, > -20 overbought. Mirror of Stochastic with a different scale.' },
        { type: 'CCI', title: 'CCI', oneLine: 'Commodity Channel Index — distance from typical price.', inputs: '—', outputs: 'value (number)', params: 'period', detail: '> +100 strong up-move, < -100 strong down-move.' },
        { type: 'KDJ', title: 'KDJ', oneLine: 'Stochastic K/D plus the J derivative (popular in Asia).', inputs: '—', outputs: 'k / d / j (numbers)', params: 'length, signal', detail: 'J is more sensitive — extreme J values often precede reversals.' },
        { type: 'MFI', title: 'MFI', oneLine: 'Money Flow Index — a volume-weighted RSI.', inputs: '—', outputs: 'value (number)', params: 'period', detail: 'Reads like RSI (< 20 oversold, > 80 overbought) but factors in volume.' },
        { type: 'OBV', title: 'OBV', oneLine: 'On-Balance Volume — cumulative directional volume.', inputs: '—', outputs: 'value (number)', detail: 'Rising OBV confirms uptrend; divergence from price warns of a reversal.' },
        { type: 'KST', title: 'KST', oneLine: 'Know Sure Thing — weighted long-term momentum.', inputs: '—', outputs: 'kst / signal (numbers)', detail: 'Smoother than MACD; cross above signal = bullish regime.' },
      ],
    },
    {
      id: 'sec-conditions',
      title: 'Conditions',
      blurb: 'Turn numbers into events. Each condition takes two numbers (A, B) plus an event gate, and emits true/false events.',
      nodes: [
        { type: 'IfAbove', title: 'If A > B', oneLine: 'True every bar A is above B.', inputs: 'event, A (number), B (number)', outputs: 'true / false (events)', detail: 'Continuous — fires each bar while A > B. Use for state gates.' },
        { type: 'IfBelow', title: 'If A < B', oneLine: 'True every bar A is below B.', inputs: 'event, A (number), B (number)', outputs: 'true / false (events)', detail: 'Mirror of IfAbove.' },
        { type: 'IfCrossAbove', title: 'Cross Above', oneLine: 'Fires once on the bar A crosses above B.', inputs: 'event, A (number), B (number)', outputs: 'true / false (events)', detail: 'Edge-trigger — best for entries (e.g. golden cross).' },
        { type: 'IfCrossBelow', title: 'Cross Below', oneLine: 'Fires once on the bar A crosses below B.', inputs: 'event, A (number), B (number)', outputs: 'true / false (events)', detail: 'Edge-trigger — best for exits (e.g. death cross).' },
      ],
    },
    {
      id: 'sec-combinators',
      title: 'Combinators',
      blurb: 'Build compound conditions. Wire the output of one condition into And / Or / Not.',
      nodes: [
        { type: 'And', title: 'And', oneLine: 'True when both A and B fire.', inputs: 'A (event), B (event)', outputs: 'true / false (events)', detail: 'Classic regime filter — e.g. Cross Above AND RSI < 70.' },
        { type: 'Or',  title: 'Or',  oneLine: 'True when either A or B fires.', inputs: 'A (event), B (event)', outputs: 'true / false (events)', detail: 'Good for "any of these signals" strategies (e.g. multiple oversold oscillators).' },
        { type: 'Not', title: 'Not', oneLine: 'Inverts an event.', inputs: 'event', outputs: 'true / false (events)', detail: 'Pair with TimeWindow to skip periods (e.g. don\'t trade in December).' },
      ],
    },
    {
      id: 'sec-gates',
      title: 'Gates',
      blurb: 'Route or suppress events based on calendar time or current position.',
      nodes: [
        { type: 'TimeWindow', title: 'Time Window', oneLine: 'True while date is within [start, end].', inputs: 'event', outputs: 'in / out (events)', params: 'start, end', detail: 'Combine with Not to exclude a window.' },
        { type: 'Position',   title: 'Position',    oneLine: 'Branch on flat vs. holding state.', inputs: 'event', outputs: 'flat / holding (events)', detail: 'Route only-entries through "flat" and only-exits through "holding" to avoid double-entry.' },
      ],
    },
    {
      id: 'sec-actions',
      title: 'Actions',
      blurb: 'Turn events into trades. Buy and Sell each support three sizing modes via the inspector.',
      nodes: [
        { type: 'Buy', title: 'Buy', oneLine: 'Enter a long position.', inputs: 'event', outputs: '—', params: 'size_type: units | pct_equity | dollar, amount', detail: 'units = N shares. pct_equity = % of current equity (e.g. 10 = 10%). dollar = fixed $ per entry.' },
        { type: 'Sell', title: 'Sell', oneLine: 'Exit an open position.', inputs: 'event', outputs: '—', params: 'size_type: all | pct_position | units, amount?', detail: 'all = close everything. pct_position = close part of the position (e.g. 50 = halve). units = close N shares (FIFO).' },
      ],
    },
    {
      id: 'sec-risk',
      title: 'Risk Nodes',
      blurb: 'Automatic exit rules attached to an OnBar event. They emit their own exit signals without explicit Sell wiring.',
      nodes: [
        { type: 'StopLoss',     title: 'Stop Loss',     oneLine: 'Exit if price drops N% below entry.', inputs: 'event', outputs: '—', params: 'pct', detail: 'Hard floor — applied per fill.' },
        { type: 'TakeProfit',   title: 'Take Profit',   oneLine: 'Exit if price rises N% above entry.', inputs: 'event', outputs: '—', params: 'pct', detail: 'Lock in gains at a fixed target.' },
        { type: 'TrailingStop', title: 'Trailing Stop', oneLine: 'Exit if price drops N% below the high since entry.', inputs: 'event', outputs: '—', params: 'pct', detail: 'Ratchets the stop up as price advances — good for trend-following.' },
      ],
    },
    {
      id: 'sec-universe',
      title: 'Universe Palette',
      blurb: 'Universe mode only. A valid graph is exactly one factor node + one Rank node, wired together.',
      nodes: [
        { type: 'Momentum',  title: 'Momentum',  oneLine: 'Trailing return (lookback − skip).', inputs: '—', outputs: 'score', params: 'lookback, skip', detail: 'Classic 12-1: lookback=252, skip=21 to exclude the last month (short-term reversal).' },
        { type: 'Reversal',  title: 'Reversal',  oneLine: 'Negated short-term return — buy losers.', inputs: '—', outputs: 'score', params: 'period', detail: '1-month reversal is a well-known cross-sectional anomaly.' },
        { type: 'LowVol',    title: 'Low Vol',   oneLine: 'Negated realized volatility — buy quiet names.', inputs: '—', outputs: 'score', params: 'period', detail: 'Low-volatility factor — empirically outperforms on risk-adjusted basis.' },
        { type: 'Liquidity', title: 'Liquidity', oneLine: 'Average dollar volume — buy liquid names.', inputs: '—', outputs: 'score', params: 'period', detail: 'Demo factor — real strategies usually negate liquidity (small, illiquid names earn more).' },
        { type: 'Rank',      title: 'Rank',      oneLine: 'Long top decile / short bottom decile of the factor score.', inputs: 'score', outputs: '—', params: 'top_pct, bottom_pct, rebalance_days, mode (long_only | long_short)', detail: 'Rebalances on a fixed cadence. long_short is dollar-neutral; long_only just holds winners.' },
      ],
    },
  ];

  const anchorFor = (type: string) => `node-${type}`;
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">Documentation</h1>
    <p class="text-sm text-muted-foreground">
      Reference for every node, mode, and template in the builder. Jump in from the table of contents or land here via the <span class="font-mono text-xs">?</span> icon on any palette node.
    </p>
  </div>
  <Button onclick={() => goto('/app/backtests/new')}>Open Builder</Button>
</div>

<div class="mt-6 grid gap-6 lg:grid-cols-[220px_1fr]">
  <aside class="lg:sticky lg:top-20 lg:self-start">
    <nav class="rounded-lg border bg-card p-3 text-sm">
      <div class="mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Contents</div>
      <ul class="space-y-1">
        <li><a class="block rounded px-2 py-1 hover:bg-accent" href="#modes">Asset Modes</a></li>
        {#each sections as s (s.id)}
          <li><a class="block rounded px-2 py-1 hover:bg-accent" href={`#${s.id}`}>{s.title}</a></li>
        {/each}
        <li><a class="block rounded px-2 py-1 hover:bg-accent" href="#templates">Templates</a></li>
      </ul>
    </nav>
  </aside>

  <div class="space-y-10">
    <section id="modes" class="scroll-mt-24">
      <h2 class="text-xl font-semibold tracking-tight">Asset Modes</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        The asset mode you pick on the builder page decides which palette is shown and how results are aggregated.
      </p>
      <div class="mt-4 grid gap-3 sm:grid-cols-2">
        {#each modes as m (m.id)}
          <div id={m.id} class="scroll-mt-24 rounded-lg border bg-card p-4">
            <div class="text-sm font-semibold">{m.title}</div>
            <p class="mt-1 text-sm text-muted-foreground">{m.body}</p>
          </div>
        {/each}
      </div>
    </section>

    {#each sections as section (section.id)}
      <section id={section.id} class="scroll-mt-24">
        <h2 class="text-xl font-semibold tracking-tight">{section.title}</h2>
        <p class="mt-1 text-sm text-muted-foreground">{section.blurb}</p>
        <div class="mt-4 space-y-3">
          {#each section.nodes as n (n.type)}
            <div id={anchorFor(n.type)} class="scroll-mt-24 rounded-lg border bg-card p-4">
              <div class="flex items-baseline justify-between gap-2">
                <div class="text-sm font-semibold">{n.title}</div>
                <div class="font-mono text-xs text-muted-foreground">{n.type}</div>
              </div>
              <p class="mt-1 text-sm">{n.oneLine}</p>
              <dl class="mt-3 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-[auto_1fr]">
                <dt class="text-muted-foreground">Inputs</dt>
                <dd class="font-mono">{n.inputs}</dd>
                <dt class="text-muted-foreground">Outputs</dt>
                <dd class="font-mono">{n.outputs}</dd>
                {#if n.params}
                  <dt class="text-muted-foreground">Params</dt>
                  <dd class="font-mono">{n.params}</dd>
                {/if}
              </dl>
              <p class="mt-3 text-xs text-muted-foreground">{n.detail}</p>
            </div>
          {/each}
        </div>
      </section>
    {/each}

    <section id="templates" class="scroll-mt-24">
      <h2 class="text-xl font-semibold tracking-tight">Templates</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        Worked examples — each one demonstrates at least one node type. Load them from the builder's Templates button.
      </p>
      <div class="mt-4 grid gap-3 sm:grid-cols-2">
        {#each STRATEGY_TEMPLATES as t (t.id)}
          <div class="rounded-lg border bg-card p-4">
            <div class="flex items-baseline justify-between gap-2">
              <div class="text-sm font-semibold">{t.name}</div>
              <div class="font-mono text-xs text-muted-foreground">{t.modes.join(' · ')}</div>
            </div>
            <p class="mt-1 text-sm text-muted-foreground">{t.description}</p>
          </div>
        {/each}
      </div>
    </section>
  </div>
</div>
