<script lang="ts">
  export type OhlcBar = {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
  };

  export type TradeMarker = {
    time: string;
    side: "buy" | "sell";
    price: number;
    quantity?: number;
  };

  let {
    bars,
    trades = [],
    height = 280,
  }: {
    bars: OhlcBar[];
    trades?: TradeMarker[];
    height?: number;
  } = $props();

  const WIDTH = 1000;
  const PADDING = { top: 16, right: 16, bottom: 24, left: 44 };

  const extent = (values: number[]) => {
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (const v of values) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
    if (min === max) return { min: min - 1, max: max + 1 };
    return { min, max };
  };

  const yFor = (value: number, min: number, max: number) => {
    const h = height - PADDING.top - PADDING.bottom;
    const t = (value - min) / (max - min);
    return PADDING.top + (1 - t) * h;
  };

  const xForIndex = (i: number, n: number) => {
    const w = WIDTH - PADDING.left - PADDING.right;
    if (n <= 1) return PADDING.left + w / 2;
    return PADDING.left + (i * w) / (n - 1);
  };

  const formatPrice = (value: number) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);

  const toDate = (time: string) => time.slice(0, 10);
  const byTime = (time: string) => bars.findIndex((b) => toDate(b.time) === toDate(time));

  const range = $derived.by(() => extent(bars.flatMap((b) => [b.low, b.high])));
  const candleBodyWidth = $derived.by(() => {
    const n = Math.max(1, bars.length);
    const w = WIDTH - PADDING.left - PADDING.right;
    const approx = w / n;
    return Math.max(3, Math.min(14, approx * 0.6));
  });
</script>

<svg
  viewBox={`0 0 ${WIDTH} ${height}`}
  class="w-full rounded-md border bg-background"
  aria-label="Candlestick price chart"
  role="img"
>
  <!-- y-axis ticks (3) -->
  {#if bars.length > 0}
    {@const y0 = range.min}
    {@const y2 = range.max}
    {@const y1 = (y0 + y2) / 2}

    {#each [y2, y1, y0] as tick (tick)}
      {@const y = yFor(tick, range.min, range.max)}
      <line
        x1={PADDING.left}
        x2={WIDTH - PADDING.right}
        y1={y}
        y2={y}
        stroke="var(--border)"
        stroke-width="1"
      />
      <text
        x={PADDING.left - 8}
        y={y + 4}
        text-anchor="end"
        font-size="11"
        fill="var(--muted-foreground)"
      >
        {formatPrice(tick)}
      </text>
    {/each}
  {/if}

  <!-- candles -->
  {#each bars as bar, i (bar.time)}
    {@const x = xForIndex(i, bars.length)}
    {@const yOpen = yFor(bar.open, range.min, range.max)}
    {@const yClose = yFor(bar.close, range.min, range.max)}
    {@const yHigh = yFor(bar.high, range.min, range.max)}
    {@const yLow = yFor(bar.low, range.min, range.max)}
    {@const up = bar.close >= bar.open}
    {@const color = up ? "var(--chart-2)" : "var(--destructive)"}
    <line x1={x} x2={x} y1={yHigh} y2={yLow} stroke={color} stroke-width="2" opacity="0.9" />
    <rect
      x={x - candleBodyWidth / 2}
      y={Math.min(yOpen, yClose)}
      width={candleBodyWidth}
      height={Math.max(2, Math.abs(yClose - yOpen))}
      fill={color}
      opacity="0.85"
      rx="1"
    />
  {/each}

  <!-- trades -->
  {#each trades as t, idx (t.time + ':' + idx)}
    {@const i = byTime(t.time)}
    {#if i >= 0}
      {@const x = xForIndex(i, bars.length)}
      {@const bar = bars[i]}
      {@const y = yFor(bar.high, range.min, range.max)}
      {@const label = t.side === "buy" ? "B" : "S"}
      {@const fill = t.side === "buy" ? "var(--chart-2)" : "var(--destructive)"}
      {@const boxW = 18}
      {@const boxH = 18}
      {@const boxX = x - boxW / 2}
      {@const boxY = y - boxH - 8}
      <g>
        <rect
          x={boxX}
          y={boxY}
          width={boxW}
          height={boxH}
          rx="4"
          fill={fill}
          stroke="var(--background)"
          stroke-width="1"
        />
        <text
          x={x}
          y={boxY + 13}
          text-anchor="middle"
          font-size="12"
          font-weight="700"
          fill="var(--primary-foreground)"
        >
          {label}
        </text>
      </g>
    {/if}
  {/each}

  <!-- x-axis label -->
  <text
    x={PADDING.left}
    y={height - 8}
    font-size="11"
    fill="var(--muted-foreground)"
  >
    Time →
  </text>
</svg>
