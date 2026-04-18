<script lang="ts">
  import "./layout.css";
  import { Toaster } from 'svelte-sonner';

  let { children } = $props();
</script>

<Toaster richColors position="top-right" />
{@render children()}
