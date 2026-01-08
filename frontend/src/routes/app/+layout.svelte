<script lang="ts">
  import AppShell from '$lib/components/app/AppShell.svelte';

  let { children } = $props();
</script>

<AppShell>
  {@render children?.()}
</AppShell>

