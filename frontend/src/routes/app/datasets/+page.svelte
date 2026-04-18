<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { BACKEND } from '$lib/config.js';

  type DatasetSummary = {
    id: string;
    name: string;
    symbol: string;
    timeframe: string;
    rows_count: number;
    first_bar: string | null;
    last_bar: string | null;
    created_at: string;
  };

  type RejectedRow = { row: number; reason: string };
  type UploadResult = {
    dataset: DatasetSummary;
    rows_inserted: number;
    rejected_rows: RejectedRow[];
  };

  type PreviewBar = {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number | null;
  };

  const TIMEFRAMES = ['1min', '5min', '15min', '30min', '1H', '4H', '1D', '1W', '1M'];
  const CSV_TEMPLATE =
    'date,open,high,low,close,volume\n' +
    '2024-01-02,180.00,182.50,179.50,181.25,1000000\n' +
    '2024-01-03,181.25,183.00,180.80,182.70,1100000\n';

  let datasets = $state<DatasetSummary[]>([]);
  let loading = $state(true);
  let deletingId = $state<string | null>(null);
  let previewing = $state<DatasetSummary | null>(null);
  let previewBars = $state<PreviewBar[]>([]);
  let previewLoading = $state(false);

  // Upload-form state
  let showUpload = $state(false);
  let uploadName = $state('');
  let uploadSymbol = $state('');
  let uploadTimeframe = $state('1D');
  let uploadFile = $state<File | null>(null);
  let uploading = $state(false);
  let lastReject = $state<RejectedRow[] | null>(null);

  const fmtDate = (iso: string | null) =>
    !iso
      ? '—'
      : new Date(iso).toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        });

  const requireToken = (): string | null => {
    const t = localStorage.getItem('token');
    if (!t) {
      toast.error('Not logged in');
      goto('/login');
      return null;
    }
    return t;
  };

  const loadAll = async () => {
    const token = requireToken();
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND}/user/datasets`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        toast.error('Failed to load datasets');
        return;
      }
      datasets = await res.json();
    } catch {
      toast.error('Could not reach backend');
    } finally {
      loading = false;
    }
  };

  const resetForm = () => {
    uploadName = '';
    uploadSymbol = '';
    uploadTimeframe = '1D';
    uploadFile = null;
    lastReject = null;
  };

  const onFileChange = (e: Event) => {
    const target = e.target as HTMLInputElement;
    uploadFile = target.files?.[0] ?? null;
  };

  const submitUpload = async () => {
    const token = requireToken();
    if (!token) return;

    if (!uploadName.trim() || !uploadSymbol.trim() || !uploadFile) {
      toast.error('Name, symbol, and CSV file are required');
      return;
    }
    if (uploadFile.size === 0) {
      toast.error('File is empty');
      return;
    }
    if (uploadFile.size > 10 * 1024 * 1024) {
      toast.error('File exceeds 10 MB');
      return;
    }

    const form = new FormData();
    form.append('name', uploadName.trim());
    form.append('symbol', uploadSymbol.trim());
    form.append('timeframe', uploadTimeframe);
    form.append('file', uploadFile);

    uploading = true;
    lastReject = null;
    try {
      const res = await fetch(`${BACKEND}/user/datasets/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const body: UploadResult | { detail: string } = await res.json();
      if (!res.ok) {
        const msg = (body as { detail?: string })?.detail ?? 'Upload failed';
        toast.error(msg);
        return;
      }
      const ok = body as UploadResult;
      toast.success(
        `Inserted ${ok.rows_inserted} bar${ok.rows_inserted === 1 ? '' : 's'}` +
          (ok.rejected_rows.length ? ` (${ok.rejected_rows.length} rejected)` : ''),
      );
      datasets = [ok.dataset, ...datasets];
      lastReject = ok.rejected_rows.length ? ok.rejected_rows : null;
      resetForm();
      if (!ok.rejected_rows.length) showUpload = false;
    } catch {
      toast.error('Could not reach backend');
    } finally {
      uploading = false;
    }
  };

  const openPreview = async (d: DatasetSummary) => {
    previewing = d;
    previewBars = [];
    previewLoading = true;
    const token = requireToken();
    if (!token) return;
    try {
      const res = await fetch(
        `${BACKEND}/user/datasets/${d.id}/preview?limit=20`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (res.ok) previewBars = await res.json();
      else toast.error('Failed to load preview');
    } catch {
      toast.error('Could not reach backend');
    } finally {
      previewLoading = false;
    }
  };

  const del = async (d: DatasetSummary) => {
    if (!confirm(`Delete dataset "${d.name}"? All ${d.rows_count} bars will be removed.`)) return;
    const token = requireToken();
    if (!token) return;
    deletingId = d.id;
    try {
      const res = await fetch(`${BACKEND}/user/datasets/${d.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status !== 204) {
        toast.error('Delete failed');
        return;
      }
      datasets = datasets.filter((x) => x.id !== d.id);
      if (previewing?.id === d.id) {
        previewing = null;
        previewBars = [];
      }
      toast.success('Dataset deleted');
    } catch {
      toast.error('Could not reach backend');
    } finally {
      deletingId = null;
    }
  };

  const downloadTemplate = () => {
    const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ohlcv_template.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  onMount(loadAll);
</script>

<div class="flex items-start justify-between gap-4">
  <div class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">My Data</h1>
    <p class="text-sm text-muted-foreground">
      Upload your own OHLCV CSVs and backtest strategies against them.
    </p>
  </div>
  <Button onclick={() => (showUpload = !showUpload)}>
    {showUpload ? 'Close' : 'Upload CSV'}
  </Button>
</div>

{#if showUpload}
  <Card.Root class="mt-6 border">
    <Card.Header>
      <Card.Title class="text-base">Upload OHLCV CSV</Card.Title>
      <Card.Description>
        Max 10 MB, 100,000 rows. Headers are case-insensitive.
      </Card.Description>
    </Card.Header>
    <Card.CardContent class="space-y-5">
      <div class="rounded-md border bg-muted/30 p-3 text-xs leading-relaxed">
        <div class="mb-2 font-medium">CSV format</div>
        <ul class="list-disc space-y-1 pl-4 text-muted-foreground">
          <li>
            Required columns: <code class="rounded bg-muted px-1">date, open, high, low, close</code>.
            Optional: <code class="rounded bg-muted px-1">volume</code>.
          </li>
          <li>
            <code class="rounded bg-muted px-1">date</code> accepts ISO 8601 — e.g.
            <code class="rounded bg-muted px-1">2024-01-02</code> or
            <code class="rounded bg-muted px-1">2024-01-02T14:30:00Z</code>.
          </li>
          <li>Rows with missing OHLC, invalid dates, duplicate timestamps, or high &lt; max(open,close) are skipped and reported.</li>
        </ul>
        <div class="mt-3">
          <Button size="sm" variant="outline" onclick={downloadTemplate}>
            Download template
          </Button>
        </div>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <div class="space-y-1.5">
          <Label for="ds-name">Dataset name</Label>
          <Input id="ds-name" placeholder="BTC 4H — 2020–2024" bind:value={uploadName} />
        </div>
        <div class="space-y-1.5">
          <Label for="ds-symbol">Symbol</Label>
          <Input id="ds-symbol" placeholder="BTCUSD" bind:value={uploadSymbol} />
        </div>
        <div class="space-y-1.5">
          <Label for="ds-tf">Timeframe</Label>
          <select
            id="ds-tf"
            bind:value={uploadTimeframe}
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
          >
            {#each TIMEFRAMES as tf}
              <option value={tf}>{tf}</option>
            {/each}
          </select>
        </div>
        <div class="space-y-1.5">
          <Label for="ds-file">CSV file</Label>
          <Input id="ds-file" type="file" accept=".csv,text/csv" onchange={onFileChange} />
        </div>
      </div>

      {#if lastReject && lastReject.length > 0}
        <div class="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs">
          <div class="mb-1 font-medium text-destructive">
            {lastReject.length} row{lastReject.length === 1 ? '' : 's'} rejected (first 20 shown)
          </div>
          <ul class="max-h-32 list-disc overflow-y-auto pl-5">
            {#each lastReject as r (r.row)}
              <li>Row {r.row}: {r.reason}</li>
            {/each}
          </ul>
        </div>
      {/if}

      <div class="flex justify-end gap-2">
        <Button variant="ghost" onclick={() => { showUpload = false; resetForm(); }} disabled={uploading}>
          Cancel
        </Button>
        <Button onclick={submitUpload} disabled={uploading}>
          {uploading ? 'Uploading…' : 'Upload'}
        </Button>
      </div>
    </Card.CardContent>
  </Card.Root>
{/if}

<div class="mt-6">
  {#if loading}
    <div class="text-sm text-muted-foreground">Loading…</div>
  {:else if datasets.length === 0}
    <div class="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
      No uploaded datasets yet.
      <button
        class="ml-1 font-medium text-primary hover:underline"
        onclick={() => (showUpload = true)}
      >
        Upload your first CSV.
      </button>
    </div>
  {:else}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each datasets as d (d.id)}
        <Card.Root class="border">
          <Card.Header>
            <Card.Title class="truncate text-base">{d.name}</Card.Title>
            <Card.Description>
              {d.symbol} · {d.timeframe} · {d.rows_count.toLocaleString()} bars
            </Card.Description>
          </Card.Header>
          <Card.CardContent class="space-y-3 pb-4">
            <div class="text-xs text-muted-foreground">
              {fmtDate(d.first_bar)} → {fmtDate(d.last_bar)}
            </div>
            <div class="flex gap-2">
              <Button variant="outline" size="sm" onclick={() => openPreview(d)}>
                Preview
              </Button>
              <Button
                variant="outline"
                size="sm"
                onclick={() => goto(`/app/backtests/new?datasetId=${d.id}`)}
              >
                Use in backtest
              </Button>
              <Button
                variant="ghost"
                size="sm"
                class="ml-auto text-destructive hover:text-destructive"
                disabled={deletingId === d.id}
                onclick={() => del(d)}
              >
                {deletingId === d.id ? 'Deleting…' : 'Delete'}
              </Button>
            </div>
          </Card.CardContent>
        </Card.Root>
      {/each}
    </div>
  {/if}
</div>

{#if previewing}
  <Card.Root class="mt-6 border">
    <Card.Header class="flex-row items-center justify-between">
      <div>
        <Card.Title class="text-base">Preview: {previewing.name}</Card.Title>
        <Card.Description>First {previewBars.length} bar{previewBars.length === 1 ? '' : 's'}</Card.Description>
      </div>
      <Button variant="ghost" size="sm" onclick={() => { previewing = null; previewBars = []; }}>
        Close
      </Button>
    </Card.Header>
    <Card.CardContent>
      {#if previewLoading}
        <div class="text-sm text-muted-foreground">Loading…</div>
      {:else if previewBars.length === 0}
        <div class="text-sm text-muted-foreground">No bars.</div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="border-b text-left text-muted-foreground">
              <tr>
                <th class="px-2 py-1">Time</th>
                <th class="px-2 py-1 text-right">Open</th>
                <th class="px-2 py-1 text-right">High</th>
                <th class="px-2 py-1 text-right">Low</th>
                <th class="px-2 py-1 text-right">Close</th>
                <th class="px-2 py-1 text-right">Volume</th>
              </tr>
            </thead>
            <tbody>
              {#each previewBars as b (b.time)}
                <tr class="border-b last:border-0">
                  <td class="px-2 py-1 font-mono">{b.time.slice(0, 19).replace('T', ' ')}</td>
                  <td class="px-2 py-1 text-right font-mono">{b.open.toFixed(2)}</td>
                  <td class="px-2 py-1 text-right font-mono">{b.high.toFixed(2)}</td>
                  <td class="px-2 py-1 text-right font-mono">{b.low.toFixed(2)}</td>
                  <td class="px-2 py-1 text-right font-mono">{b.close.toFixed(2)}</td>
                  <td class="px-2 py-1 text-right font-mono">{b.volume?.toLocaleString() ?? '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </Card.CardContent>
  </Card.Root>
{/if}
