<script lang="ts">
  import * as Card from '$lib/components/ui/card/index.js';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { ArrowLeft, CheckCircle, Loader } from '@lucide/svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { toast } from 'svelte-sonner';

  const BACKEND = 'http://localhost:8000';

  const token = $derived($page.url.searchParams.get('token') ?? '');

  let newPassword = $state('');
  let confirmPassword = $state('');
  let isLoading = $state(false);
  let isDone = $state(false);

  async function handleSubmit() {
    if (!newPassword || newPassword.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    if (!token) {
      toast.error('Invalid or missing reset token');
      return;
    }

    isLoading = true;
    try {
      const res = await fetch(`${BACKEND}/auth/reset-password`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      if (!res.ok) {
        const text = await res.text();
        toast.error(text || 'Reset failed. The link may have expired.');
        return;
      }
      isDone = true;
    } catch {
      toast.error('Could not reach server. Please try again.');
    } finally {
      isLoading = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center bg-linear-to-br from-gray-50 to-gray-100 p-4">
  <div class="w-full max-w-md">
    <Card.Root class="border shadow-lg">
      <Card.Header class="text-center">
        <Button
          variant="ghost"
          size="sm"
          onclick={() => goto('/login')}
          class="absolute left-4 top-4"
        >
          <ArrowLeft class="mr-2 h-4 w-4" />
          Back
        </Button>
        <Card.Title class="text-2xl font-bold tracking-tight">Reset Password</Card.Title>
        <Card.Description class="text-muted-foreground">
          {#if !isDone}
            Enter your new password below
          {:else}
            Your password has been updated
          {/if}
        </Card.Description>
      </Card.Header>

      <Card.Content class="space-y-6">
        {#if !token}
          <p class="text-sm text-destructive text-center">
            Invalid reset link. Please request a new one.
          </p>
          <Button onclick={() => goto('/forget-password')} variant="outline" class="w-full">
            Request new link
          </Button>
        {:else if !isDone}
          <div class="space-y-4">
            <div class="space-y-2">
              <Label for="newPassword">New password</Label>
              <Input
                id="newPassword"
                type="password"
                bind:value={newPassword}
                placeholder="At least 8 characters"
                autocomplete="new-password"
              />
            </div>
            <div class="space-y-2">
              <Label for="confirmPassword">Confirm new password</Label>
              <Input
                id="confirmPassword"
                type="password"
                bind:value={confirmPassword}
                placeholder="Repeat your new password"
                autocomplete="new-password"
              />
            </div>
            <Button onclick={handleSubmit} class="w-full" disabled={isLoading}>
              {#if isLoading}
                <Loader class="mr-2 h-4 w-4 animate-spin" />
                Resetting…
              {:else}
                Reset Password
              {/if}
            </Button>
          </div>
        {:else}
          <div class="text-center space-y-4">
            <div class="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
              <CheckCircle class="h-8 w-8 text-green-600" />
            </div>
            <p class="text-muted-foreground text-sm">
              Your password has been reset. You can now log in with your new password.
            </p>
            <Button onclick={() => goto('/login')} class="w-full">Go to Login</Button>
          </div>
        {/if}
      </Card.Content>
    </Card.Root>
  </div>
</div>
