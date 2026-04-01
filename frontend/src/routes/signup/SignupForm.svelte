<script lang="ts">
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { Checkbox } from '$lib/components/ui/checkbox/index.js';
  import { Lock, Mail, User, Eye, EyeOff, Loader } from '@lucide/svelte';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import type { SignupFormData } from '$lib/types/auth.js';
  import { _ } from 'svelte-i18n';
  import { enhance } from '$app/forms';
  import type { SubmitFunction } from '@sveltejs/kit';

  let showPassword = $state(false);
  let showConfirmPassword = $state(false);
  let isLoading = $state(false);

  let form: SignupFormData = $state({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    agreeToTerms: false,
  });

  const signupEnhance: SubmitFunction = () => {
    isLoading = true;
    return async ({ result }) => {
      isLoading = false;
      if (result.type === 'success') {
        toast.success(
          ((result.data as any)?.message as string | undefined) ??
            'Registered. Please verify your email, then login.'
        );
        goto(`/login?signup=1&email=${encodeURIComponent(form.email)}`);
        return;
      }
      if (result.type === 'failure') {
        toast.error(((result.data as any)?.message as string | undefined) ?? 'Signup failed.');
        return;
      }
      toast.error('Signup failed.');
    };
  };
</script>

<form method="POST" action="?/register" use:enhance={signupEnhance}>
  <div class="space-y-5">
    <div class="space-y-3">
      <Label for="name" class="text-sm font-medium text-foreground">
        Username
      </Label>
      <div class="relative">
        <div class="absolute left-3 top-1/2 transform -translate-y-1/2">
          <User class="h-4 w-4 text-muted-foreground" />
        </div>
        <Input
          id="name"
          name="name"
          placeholder="yourname"
          class="pl-10 h-11 bg-background border-input focus-visible:ring-2 focus-visible:ring-offset-2"
          minlength={1}
          bind:value={form.name}
          required
          disabled={isLoading}
        />
      </div>
    </div>

    <div class="space-y-3">
      <Label for="email" class="text-sm font-medium text-foreground">
        {$_('auth.login.email')}
      </Label>
      <div class="relative">
        <div class="absolute left-3 top-1/2 transform -translate-y-1/2">
          <Mail class="h-4 w-4 text-muted-foreground" />
        </div>
        <Input
          id="email"
          name="email"
          type="email"
          placeholder="example@email.com"
          class="pl-10 h-11 bg-background border-input focus-visible:ring-2 focus-visible:ring-offset-2"
          minlength={1}
          bind:value={form.email}
          required
          disabled={isLoading}
        />
      </div>
    </div>

    <div class="space-y-3">
      <Label for="password" class="text-sm font-medium text-foreground">
        {$_('auth.login.password')}
      </Label>
      <div class="relative">
        <div class="absolute left-3 top-1/2 transform -translate-y-1/2">
          <Lock class="h-4 w-4 text-muted-foreground" />
        </div>
        <Input
          id="password"
          name="password"
          type={showPassword ? 'text' : 'password'}
          placeholder="password"
          minlength={8}
          maxlength={40}
          class="pl-10 pr-10 h-11 bg-background border-input focus-visible:ring-2 focus-visible:ring-offset-2"
          bind:value={form.password}
          required
          disabled={isLoading}
        />
        <button
          type="button"
          class="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          onclick={() => (showPassword = !showPassword)}
          aria-label={showPassword ? 'Hide password' : 'Show password'}
          disabled={isLoading}
        >
          {#if showPassword}
            <EyeOff class="h-4 w-4" />
          {:else}
            <Eye class="h-4 w-4" />
          {/if}
        </button>
      </div>
    </div>

    <div class="space-y-3">
      <Label for="confirmPassword" class="text-sm font-medium text-foreground">
        Confirm Password
      </Label>
      <div class="relative">
        <div class="absolute left-3 top-1/2 transform -translate-y-1/2">
          <Lock class="h-4 w-4 text-muted-foreground" />
        </div>
        <Input
          id="confirmPassword"
          name="confirmPassword"
          type={showConfirmPassword ? 'text' : 'password'}
          placeholder="password"
          minlength={8}
          maxlength={40}
          class="pl-10 pr-10 h-11 bg-background border-input focus-visible:ring-2 focus-visible:ring-offset-2"
          bind:value={form.confirmPassword}
          required
          disabled={isLoading}
        />
        <button
          type="button"
          class="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          onclick={() => (showConfirmPassword = !showConfirmPassword)}
          aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
          disabled={isLoading}
        >
          {#if showConfirmPassword}
            <EyeOff class="h-4 w-4" />
          {:else}
            <Eye class="h-4 w-4" />
          {/if}
        </button>
      </div>
    </div>

    <div class="flex items-start space-x-3 pt-1">
      <input
        type="hidden"
        name="agreeToTerms"
        value={form.agreeToTerms ? 'true' : 'false'}
      />
      <div class="flex items-center h-5">
        <Checkbox
          id="agreeToTerms"
          bind:checked={form.agreeToTerms}
          class="h-4 w-4 border-input data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
          disabled={isLoading}
        />
      </div>
      <div class="grid gap-1.5 leading-none">
        <Label
          for="agreeToTerms"
          class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
        >
          I agree to the Terms and Privacy Policy
        </Label>
      </div>
    </div>

    <Button
      type="submit"
      disabled={isLoading}
      class="w-full h-11 bg-primary text-primary-foreground hover:bg-primary/90 font-medium transition-colors shadow-sm hover:shadow"
    >
      {#if isLoading}
        <Loader class="mr-2 h-4 w-4 animate-spin" />
        Creating account…
      {:else}
        Create account
      {/if}
    </Button>
  </div>
</form>
