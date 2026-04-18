<script lang="ts">
  export type EquityPoint = {
    time: string;
    equity: number;
  };

  let { points, height = 220 }: { points: EquityPoint[]; height?: number } = $props();

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

  const range = $derived.by(() => extent(points.map((p) => p.equity)));

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

  const pathD = $derived.by(() => {
    if (points.length === 0) return "";
    const cmds: string[] = [];
    for (let i = 0; i < points.length; i++) {
      const x = xForIndex(i, points.length);
      const y = yFor(points[i].equity, range.min, range.max);
      cmds.push(`${i === 0 ? "M" : "L"} ${x} ${y}`);
    }
    return cmds.join(" ");
  });

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

  <path d={pathD} fill="none" stroke="var(--primary)" stroke-width="2.5" />

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
