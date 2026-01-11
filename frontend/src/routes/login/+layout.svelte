<script>
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";

  let { children } = $props();

  onMount(() => {
    const token = localStorage.getItem("token");
    if (token) {
      goto("/app/backtests/new");
    }
  });
</script>

{@render children()}
