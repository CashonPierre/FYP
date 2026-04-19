<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Component } from 'svelte';
  import { cn } from '$lib/utils.js';

  let {
    icon,
    title,
    description,
    action,
    class: className,
  }: {
    icon?: Component<{ class?: string; size?: number }>;
    title: string;
    description?: string;
    action?: Snippet;
    class?: string;
  } = $props();
</script>

<div
  class={cn(
    'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-card px-6 py-12 text-center',
    className,
  )}
>
  {#if icon}
    {@const Icon = icon}
    <div class="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
      <Icon size={22} />
    </div>
  {/if}
  <div class="space-y-1">
    <div class="text-sm font-medium text-foreground">{title}</div>
    {#if description}
      <div class="max-w-sm text-sm text-muted-foreground">{description}</div>
    {/if}
  </div>
  {#if action}
    <div class="mt-1">{@render action()}</div>
  {/if}
</div>
