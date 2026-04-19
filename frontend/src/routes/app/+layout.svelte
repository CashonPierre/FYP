<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import AppShell from '$lib/components/app/AppShell.svelte';
  import { BACKEND } from '$lib/config.js';

  let { children } = $props();
  let ready = $state(false);

  // Guard against double-install if the layout remounts (e.g. HMR).
  let restoreFetch: (() => void) | null = null;

  const kickToLogin = () => {
    // Preserve where the user was so we can bounce them back after login.
    try {
      const here = window.location.pathname + window.location.search;
      sessionStorage.setItem('postLoginRedirect', here);
    } catch {}
    localStorage.removeItem('token');
    goto('/login');
  };

  // Intercept every fetch call to the backend. Any 401 means the stored
  // token is stale or missing; clear it and redirect to /login so the UI
  // doesn't silently keep rendering "logged-in" pages with 401'd data.
  const installFetchGuard = () => {
    if (restoreFetch) return;
    const original = window.fetch;
    const wrapped: typeof fetch = async (input, init) => {
      const res = await original(input, init);
      if (res.status === 401) {
        const url = typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
        if (BACKEND && url.startsWith(BACKEND)) {
          kickToLogin();
        }
      }
      return res;
    };
    window.fetch = wrapped;
    restoreFetch = () => { window.fetch = original; };
  };

  onMount(() => {
    if (!localStorage.getItem('token')) {
      goto('/login');
      return;
    }
    installFetchGuard();
    ready = true;
    return () => {
      restoreFetch?.();
      restoreFetch = null;
    };
  });
</script>

{#if ready}
  <AppShell>
    {@render children?.()}
  </AppShell>
{/if}

