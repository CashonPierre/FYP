<script lang="ts">
  import type { TradeMarker } from './CandlestickChart.svelte';

  type SortKey = 'time' | 'side' | 'price' | 'quantity';
  type SortDir = 'asc' | 'desc';

  let { trades }: { trades: TradeMarker[] } = $props();

  let sortKey = $state<SortKey>('time');
  let sortDir = $state<SortDir>('asc');

  const setSort = (key: SortKey) => {
    if (sortKey === key) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      sortDir = 'asc';
    }
  };

  const sorted = $derived.by(() => {
    return [...trades].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'time') cmp = a.time.localeCompare(b.time);
      else if (sortKey === 'side') cmp = a.side.localeCompare(b.side);
      else if (sortKey === 'price') cmp = a.price - b.price;
      else if (sortKey === 'quantity') cmp = (a.quantity ?? 0) - (b.quantity ?? 0);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  });

  const arrow = (key: SortKey) => (sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '');

  const fmtDate = (iso: string) => iso.slice(0, 10);
  const fmtPrice = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
</script>

<div class="overflow-x-auto">
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b text-left text-xs text-muted-foreground">
        <th class="cursor-pointer px-4 py-2 font-medium hover:text-foreground" onclick={() => setSort('time')}>
          Date{arrow('time')}
        </th>
        <th class="cursor-pointer px-4 py-2 font-medium hover:text-foreground" onclick={() => setSort('side')}>
          Side{arrow('side')}
        </th>
        <th class="cursor-pointer px-4 py-2 font-medium hover:text-foreground text-right" onclick={() => setSort('price')}>
          Price{arrow('price')}
        </th>
        <th class="cursor-pointer px-4 py-2 font-medium hover:text-foreground text-right" onclick={() => setSort('quantity')}>
          Qty{arrow('quantity')}
        </th>
      </tr>
    </thead>
    <tbody>
      {#each sorted as t (`${t.time}-${t.side}-${t.price}`)}
        <tr class="border-b last:border-0 hover:bg-muted/40">
          <td class="px-4 py-2 tabular-nums text-muted-foreground">{fmtDate(t.time)}</td>
          <td class="px-4 py-2">
            <span class={t.side === 'buy' ? 'text-green-600 font-medium' : 'text-red-500 font-medium'}>
              {t.side.toUpperCase()}
            </span>
          </td>
          <td class="px-4 py-2 text-right tabular-nums">{fmtPrice.format(t.price)}</td>
          <td class="px-4 py-2 text-right tabular-nums text-muted-foreground">{t.quantity ?? '—'}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
