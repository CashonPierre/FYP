<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { BACKEND } from '$lib/config.js';

  type Profile = {
    username: string;
    email: string;
    is_verified: boolean;
  };

  let loading = $state(true);
  let profile = $state<Profile | null>(null);

  let username = $state('');
  let savingUsername = $state(false);

  let currentPassword = $state('');
  let newPassword = $state('');
  let confirmPassword = $state('');
  let changingPassword = $state(false);

  const requireToken = (): string | null => {
    const t = localStorage.getItem('token');
    if (!t) {
      toast.error('Not logged in');
      goto('/login');
      return null;
    }
    return t;
  };

  const loadProfile = async () => {
    const token = requireToken();
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND}/user/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        toast.error('Failed to load profile');
        return;
      }
      profile = await res.json();
      username = profile?.username ?? '';
    } catch {
      toast.error('Could not reach backend');
    } finally {
      loading = false;
    }
  };

  const saveUsername = async () => {
    if (savingUsername) return;
    const trimmed = username.trim();
    if (trimmed.length < 3) {
      toast.error('Username must be at least 3 characters');
      return;
    }
    if (trimmed === profile?.username) {
      toast.info('Username unchanged');
      return;
    }
    const token = requireToken();
    if (!token) return;

    savingUsername = true;
    try {
      const res = await fetch(`${BACKEND}/user/me`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ username: trimmed }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        toast.error(body?.detail ?? 'Update failed');
        return;
      }
      profile = await res.json();
      username = profile?.username ?? '';
      toast.success('Username updated');
    } catch {
      toast.error('Could not reach backend');
    } finally {
      savingUsername = false;
    }
  };

  const changePassword = async () => {
    if (changingPassword) return;
    if (!currentPassword) {
      toast.error('Enter your current password');
      return;
    }
    if (newPassword.length < 8) {
      toast.error('New password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('New password and confirmation do not match');
      return;
    }
    const token = requireToken();
    if (!token) return;

    changingPassword = true;
    try {
      const res = await fetch(`${BACKEND}/user/change-password`, {
        method: 'POST',
        headers: { 'content-type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        toast.error(body?.detail ?? 'Password change failed');
        return;
      }
      currentPassword = '';
      newPassword = '';
      confirmPassword = '';
      toast.success('Password changed');
    } catch {
      toast.error('Could not reach backend');
    } finally {
      changingPassword = false;
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    toast.success('Logged out');
    goto('/login');
  };

  onMount(loadProfile);
</script>

<div class="space-y-1">
  <h1 class="text-2xl font-bold tracking-tight">Settings</h1>
  <p class="text-sm text-muted-foreground">Manage your profile and password.</p>
</div>

<div class="mt-6 grid gap-6 md:grid-cols-2">
  <Card.Root class="border">
    <Card.Header>
      <Card.Title class="text-base">Profile</Card.Title>
      <Card.Description>Your account details.</Card.Description>
    </Card.Header>
    <Card.CardContent class="space-y-4 pb-6">
      {#if loading}
        <div class="text-sm text-muted-foreground">Loading…</div>
      {:else if !profile}
        <div class="text-sm text-destructive">Could not load profile.</div>
      {:else}
        <div class="space-y-1.5">
          <Label for="email">Email</Label>
          <Input id="email" type="email" value={profile.email} readonly disabled />
          <p class="text-xs text-muted-foreground">
            {profile.is_verified ? 'Verified.' : 'Not verified.'}
          </p>
        </div>

        <div class="space-y-1.5">
          <Label for="username">Username</Label>
          <Input id="username" type="text" bind:value={username} minlength={3} maxlength={64} />
        </div>

        <div class="flex justify-end">
          <Button
            size="sm"
            onclick={saveUsername}
            disabled={savingUsername || username.trim() === profile.username}
          >
            {savingUsername ? 'Saving…' : 'Save changes'}
          </Button>
        </div>
      {/if}
    </Card.CardContent>
  </Card.Root>

  <Card.Root class="border">
    <Card.Header>
      <Card.Title class="text-base">Change password</Card.Title>
      <Card.Description>Use at least 8 characters.</Card.Description>
    </Card.Header>
    <Card.CardContent class="space-y-4 pb-6">
      <div class="space-y-1.5">
        <Label for="current-password">Current password</Label>
        <Input
          id="current-password"
          type="password"
          autocomplete="current-password"
          bind:value={currentPassword}
        />
      </div>
      <div class="space-y-1.5">
        <Label for="new-password">New password</Label>
        <Input
          id="new-password"
          type="password"
          autocomplete="new-password"
          minlength={8}
          bind:value={newPassword}
        />
      </div>
      <div class="space-y-1.5">
        <Label for="confirm-password">Confirm new password</Label>
        <Input
          id="confirm-password"
          type="password"
          autocomplete="new-password"
          minlength={8}
          bind:value={confirmPassword}
        />
      </div>
      <div class="flex justify-end">
        <Button
          size="sm"
          onclick={changePassword}
          disabled={changingPassword || !currentPassword || !newPassword || !confirmPassword}
        >
          {changingPassword ? 'Updating…' : 'Update password'}
        </Button>
      </div>
    </Card.CardContent>
  </Card.Root>
</div>

<div class="mt-6">
  <Card.Root class="border">
    <Card.Header>
      <Card.Title class="text-base">Session</Card.Title>
      <Card.Description>Sign out of this browser.</Card.Description>
    </Card.Header>
    <Card.CardContent class="flex justify-end pb-6">
      <Button variant="outline" size="sm" onclick={logout}>Log out</Button>
    </Card.CardContent>
  </Card.Root>
</div>
