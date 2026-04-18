<script lang="ts">
  export type EquityPoint = {
    time: string;
    equity: number;
  };

  let {
    points,
    benchmark = [],
    benchmarkLabel = 'Benchmark',
    height = 220,
  }: {
    points: EquityPoint[];
    benchmark?: EquityPoint[];
    benchmarkLabel?: string;
    height?: number;
  } = $props();

  const WIDTH = 1000;
  const PADDING = { top: 16, right: 16, bottom: 24, left: 64 };

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

  const range = $derived.by(() =>
    extent([...points.map((p) => p.equity), ...benchmark.map((p) => p.equity)])
  );

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

  const fmtCurrency = (value: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(value);

  const buildPath = (series: EquityPoint[]) => {
    if (series.length === 0) return "";
    const cmds: string[] = [];
    for (let i = 0; i < series.length; i++) {
      const x = xForIndex(i, series.length);
      const y = yFor(series[i].equity, range.min, range.max);
      cmds.push(`${i === 0 ? "M" : "L"} ${x} ${y}`);
    }
    return cmds.join(" ");
  };

  const pathD = $derived.by(() => buildPath(points));
  const benchmarkD = $derived.by(() => buildPath(benchmark));

  const fmtDate = (iso: string) => iso.slice(0, 10);

  const xTicks = $derived.by(() => {
    if (points.length < 2) return [];
    const count = Math.min(5, points.length);
    return Array.from({ length: count }, (_, k) => {
      const i = Math.round((k * (points.length - 1)) / (count - 1));
      return { x: xForIndex(i, points.length), label: fmtDate(points[i].time) };
    });
  });
</script>

<svg
  viewBox={`0 0 ${WIDTH} ${height}`}
  class="w-full rounded-md border bg-background"
  aria-label="Equity curve chart"
  role="img"
>
  {#if points.length > 0}
    {@const yTop = yFor(range.max, range.min, range.max)}
    {@const yMid = yFor((range.min + range.max) / 2, range.min, range.max)}
    {@const yBot = yFor(range.min, range.min, range.max)}

    {#each [
      { y: yTop, v: range.max },
      { y: yMid, v: (range.min + range.max) / 2 },
      { y: yBot, v: range.min }
    ] as tick (tick.y)}
      <line
        x1={PADDING.left}
        x2={WIDTH - PADDING.right}
        y1={tick.y}
        y2={tick.y}
        stroke="var(--border)"
        stroke-width="1"
      />
      <text
        x={PADDING.left - 8}
        y={tick.y + 4}
        text-anchor="end"
        font-size="11"
        fill="var(--muted-foreground)"
      >
        {fmtCurrency(tick.v)}
      </text>
    {/each}
  {/if}

  {#if benchmark.length > 0}
    <path
      d={benchmarkD}
      fill="none"
      stroke="var(--muted-foreground)"
      stroke-width="2"
      stroke-dasharray="4 4"
      opacity="0.8"
    />
  {/if}

  <path d={pathD} fill="none" stroke="var(--primary)" stroke-width="2.5" />

  {#if benchmark.length > 0}
    <g transform={`translate(${PADDING.left + 8}, ${PADDING.top + 4})`}>
      <rect x="0" y="0" width="150" height="36" rx="4" fill="var(--background)" opacity="0.85" />
      <line x1="8" y1="12" x2="24" y2="12" stroke="var(--primary)" stroke-width="2.5" />
      <text x="30" y="15" font-size="11" fill="var(--foreground)">Strategy</text>
      <line x1="8" y1="27" x2="24" y2="27" stroke="var(--muted-foreground)" stroke-width="2" stroke-dasharray="4 4" />
      <text x="30" y="30" font-size="11" fill="var(--muted-foreground)">{benchmarkLabel}</text>
    </g>
  {/if}

  {#each xTicks as tick, i (tick.x + ':' + i)}
    <text
      x={tick.x}
      y={height - 6}
      text-anchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
      font-size="11"
      fill="var(--muted-foreground)"
    >
      {tick.label}
    </text>
  {/each}
</svg>
