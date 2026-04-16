<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import AppShell from '$lib/components/app/AppShell.svelte';

  let { children } = $props();
  let ready = $state(false);

  onMount(() => {
    if (!localStorage.getItem('token')) {
      goto('/login');
    } else {
      ready = true;
    }
  });
</script>

{#if ready}
  <AppShell>
    {@render children?.()}
  </AppShell>
{/if}

