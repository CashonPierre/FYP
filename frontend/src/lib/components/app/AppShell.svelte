<script lang="ts">
  import { page } from '$app/state';
  import { cn } from '$lib/utils.js';

  type NavItem = {
    label: string;
    href: string;
    disabled?: boolean;
  };

  const nav: NavItem[] = [
    { label: 'New Backtest', href: '/app/backtests/new' },
    { label: 'Backtest History', href: '/app/backtests' },
    { label: 'Strategies', href: '/app/strategies', disabled: true },
    { label: 'Settings', href: '/app/settings', disabled: true },
  ];

  let { children } = $props();

  const isActive = (href: string, pathname: string) =>
    pathname === href || pathname.startsWith(`${href}/`);
</script>

<div class="min-h-screen bg-background text-foreground">
  <header class="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div class="flex h-14 items-center justify-between gap-4">
        <a href="/home" class="font-semibold tracking-tight">
          Backtest UI
        </a>

        <nav class="hidden items-center gap-1 sm:flex">
          {#each nav as item (item.href)}
            <a
              href={item.disabled ? undefined : item.href}
              aria-disabled={item.disabled}
              tabindex={item.disabled ? -1 : undefined}
              class={cn(
                'rounded-md px-3 py-2 text-sm transition-colors',
                item.disabled
                  ? 'text-muted-foreground/60 cursor-not-allowed'
                  : 'hover:bg-accent hover:text-accent-foreground',
                isActive(item.href, page.url.pathname) && !item.disabled
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground'
              )}
            >
              {item.label}
            </a>
          {/each}
        </nav>
      </div>
    </div>
  </header>

  <main class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
    {@render children?.()}
  </main>
</div>
