<script lang="ts">
  import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
  } from "$lib/components/ui/card/index.js";
  import { Separator } from "$lib/components/ui/separator/index.js";
  import { goto } from "$app/navigation";
  import { _ } from "svelte-i18n";
  import { Lock, Mail, Eye, EyeOff, Loader } from "@lucide/svelte";
  import { toast } from "svelte-sonner";
  import { Button } from "$lib/components/ui/button/index.js";
  import { Input } from "$lib/components/ui/input/index.js";
  import { Label } from "$lib/components/ui/label/index.js";
  import { enhance } from "$app/forms";
  import { Checkbox } from "$lib/components/ui/checkbox/index.js";
  import type { LoginFormData } from "$lib/types/auth.js";
  import { fromAction } from "svelte/attachments";

  let { data } = $props();

  let form: LoginFormData = $state({
    email: "",
    password: "",
    rememberMe: false,
  });


  let showPassword = $state(false);
  let isLoading = $state(false);
</script>
<div
  class="min-h-screen flex items-center justify-center bg-linear-to-br from-gray-50 to-gray-100 p-4"
>
  <div class="w-full max-w-md">
    <Card class="border shadow-lg">
      <CardHeader class="text-center">
        <CardTitle class="text-2xl font-bold tracking-tight">
          {$_("auth.login.description")}
        </CardTitle>
        <CardDescription class="text-muted-foreground">
          {$_("auth.login.title")}
        </CardDescription>
      </CardHeader>
      <CardContent class="space-y-6">
        <form method="POST" action="?/login" use:enhance>
          <div class="space-y-5">
            <!-- Email Field -->
            <div class="space-y-3">
              <Label for="email" class="text-sm font-medium text-foreground">
                {$_("auth.login.email")}
              </Label>
              <div class="relative">
                <div class="absolute left-3 top-1/2 transform -translate-y-1/2">
                  <Mail class="h-4 w-4 text-muted-foreground" />
                </div>
                <Input
                  id="email"
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

            <!-- Password Field -->
            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <Label
                  for="password"
                  class="text-sm font-medium text-foreground"
                >
                  {$_("auth.login.password")}
                </Label>
                <a
                  href="/forget-password"
                  class="text-sm font-medium text-primary hover:text-primary/80 underline-offset-4 hover:underline transition-colors"
                  onclick={() => goto("/forget-password")}
                >
                  {$_("auth.login.forgotPassword")}
                </a>
              </div>

              <div class="relative">
                <div class="absolute left-3 top-1/2 transform -translate-y-1/2">
                  <Lock class="h-4 w-4 text-muted-foreground" />
                </div>
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
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
                  aria-label={showPassword ? "Hide password" : "Show password"}
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

            <!-- Remember Me Checkbox -->
            <div class="flex items-start space-x-3 pt-1">
              <div class="flex items-center h-5">
                <Checkbox

                  id="rememberMe"
                  bind:checked={form.rememberMe}
                  class="h-4 w-4 border-input data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
                  disabled={isLoading}
                />
              </div>
              <div class="grid gap-1.5 leading-none">
                <Label
                  for="rememberMe"
                  class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                >
                  {$_("auth.login.rememberMe")}
                </Label>
                <p class="text-xs text-muted-foreground">
                  Stay signed in on this device
                </p>
              </div>
            </div>

            <!-- Submit Button -->
            <Button
              type="submit"
              disabled={isLoading}
              class="w-full h-11 bg-primary text-primary-foreground hover:bg-primary/90 font-medium transition-colors shadow-sm hover:shadow"
            >
              {#if isLoading}
                <Loader class="mr-2 h-4 w-4 animate-spin" />
                {$_("auth.login.logging_in")}
              {:else}
                {$_("auth.login.login")}
              {/if}
            </Button>
          </div>
        </form>

        <Separator class="my-6" />

        <div class="text-center space-y-4">
          <p class="text-sm text-muted-foreground">
            {$_("auth.login.noAccount")}
            <button
              onclick={() => goto("/signup")}
              class="ml-2 font-medium text-primary hover:text-primary/80 underline-offset-2 hover:underline transition-colors"
            >
              {$_("auth.login.signup")}
            </button>
          </p>
          <p class="text-xs text-muted-foreground">
            {$_("continue")}
            <a href="/terms" class="text-primary hover:underline ml-1"
              >{$_("term")}</a
            >
            {$_("and")}
            <a href="/privacy" class="text-primary hover:underline ml-1"
              >{$_("privacy")}</a
            >
          </p>
        </div>
      </CardContent>
    </Card>
  </div>
</div>
