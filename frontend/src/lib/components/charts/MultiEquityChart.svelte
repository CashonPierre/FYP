<script lang="ts">
  import type { EquityPoint } from './EquityCurveChart.svelte';

  export type EquitySeries = {
    label: string;
    points: EquityPoint[];
    color?: string;
    dashed?: boolean;
  };

  let {
    series,
    height = 260,
  }: {
    series: EquitySeries[];
    height?: number;
  } = $props();

  const WIDTH = 1000;
  const PADDING = { top: 16, right: 16, bottom: 24, left: 64 };

  const PALETTE = [
    'oklch(0.65 0.22 250)',
    'oklch(0.68 0.20 30)',
    'oklch(0.70 0.18 150)',
    'oklch(0.65 0.22 320)',
    'oklch(0.72 0.18 80)',
    'oklch(0.60 0.18 200)',
  ];

  const colorFor = (i: number, explicit?: string) => explicit ?? PALETTE[i % PALETTE.length];

  const range = $derived.by(() => {
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (const s of series) {
      for (const p of s.points) {
        if (p.equity < min) min = p.equity;
        if (p.equity > max) max = p.equity;
      }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
    if (min === max) return { min: min - 1, max: max + 1 };
    return { min, max };
  });

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
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(value);

  const buildPath = (points: EquityPoint[]) => {
    if (points.length === 0) return '';
    const cmds: string[] = [];
    for (let i = 0; i < points.length; i++) {
      const x = xForIndex(i, points.length);
      const y = yFor(points[i].equity, range.min, range.max);
      cmds.push(`${i === 0 ? 'M' : 'L'} ${x} ${y}`);
    }
    return cmds.join(' ');
  };

  const paths = $derived.by(() =>
    series.map((s, i) => ({
      label: s.label,
      d: buildPath(s.points),
      color: colorFor(i, s.color),
      dashed: s.dashed ?? false,
    }))
  );

  const fmtDate = (iso: string) => iso.slice(0, 10);

  const longest = $derived.by(() => {
    let best = series[0]?.points ?? [];
    for (const s of series) if (s.points.length > best.length) best = s.points;
    return best;
  });

  const xTicks = $derived.by(() => {
    if (longest.length < 2) return [];
    const count = Math.min(5, longest.length);
    return Array.from({ length: count }, (_, k) => {
      const i = Math.round((k * (longest.length - 1)) / (count - 1));
      return { x: xForIndex(i, longest.length), label: fmtDate(longest[i].time) };
    });
  });
</script>

<svg
  viewBox={`0 0 ${WIDTH} ${height}`}
  class="w-full rounded-md border bg-background"
  aria-label="Multi-series equity curve"
  role="img"
>
  {#if longest.length > 0}
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

  {#each paths as p (p.label)}
    <path
      d={p.d}
      fill="none"
      stroke={p.color}
      stroke-width="2.25"
      stroke-dasharray={p.dashed ? '4 4' : undefined}
    />
  {/each}

  {#if series.length > 0}
    <g transform={`translate(${PADDING.left + 8}, ${PADDING.top + 4})`}>
      <rect
        x="0"
        y="0"
        width="220"
        height={12 + series.length * 16}
        rx="4"
        fill="var(--background)"
        opacity="0.88"
      />
      {#each paths as p, i (p.label)}
        <line
          x1="8"
          y1={12 + i * 16}
          x2="24"
          y2={12 + i * 16}
          stroke={p.color}
          stroke-width="2.25"
          stroke-dasharray={p.dashed ? '4 4' : undefined}
        />
        <text x="30" y={15 + i * 16} font-size="11" fill="var(--foreground)">
          {p.label}
        </text>
      {/each}
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
