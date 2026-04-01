<script lang="ts">
  import * as Card from "$lib/components/ui/card/index.js";
  import { Button } from "$lib/components/ui/button/index.js";
  import { Input } from "$lib/components/ui/input/index.js";
  import { Label } from "$lib/components/ui/label/index.js";
  import * as Alert from "$lib/components/ui/alert/index.js";
  import { AlertCircle, Mail, ArrowLeft, CheckCircle, Loader } from "@lucide/svelte";
  import { goto } from "$app/navigation";
  import { Icon, toast } from "svelte-sonner";
  import { resetPassword } from "$lib/utils/auth.js";
  import { _ } from "svelte-i18n";

  let email = $state("");
  let isLoading = $state(false);
  let isSubmitted = $state(false);

  async function handleSubmit() {
    if (!email) {
      toast.error("Please enter your email address");
      return;
    }

    isLoading = true;

    try {
      const result = await resetPassword(email);

      if (result.success) {
        isSubmitted = true;
        toast.success(result.message || "Reset instructions sent!");
      } else {
        toast.error(result.message || "Failed to send reset instructions");
      }
    } catch (error) {
      toast.error("An error occurred. Please try again.");
      console.error("Reset password error:", error);
    } finally {
      isLoading = false;
    }
  }
</script>

<div
  class="min-h-screen flex items-center justify-center bg-linear-to-br from-gray-50 to-gray-100 p-4"
>
  <div class="w-full max-w-md">
    <Card.Root class="border shadow-lg">
      <Card.Header class="text-center">
        <Button
          variant="ghost"
          size="sm"
          onclick={() => {
            goto("/login");
          }}
          class="absolute left-4 top-4"
        >
          <ArrowLeft class="mr-2 h-4 w-4" />
          {$_("common.back")}
        </Button>

        <Card.Title class="text-2xl font-bold tracking-tight">
          Forgot Password
        </Card.Title>
        <Card.Description class="text-muted-foreground">
          {#if !isSubmitted}
            Enter your email to receive reset instructions
          {:else}
            Check your email for reset instructions
          {/if}
        </Card.Description>
      </Card.Header>

      <Card.CardContent class="space-y-6">
        {#if !isSubmitted}
          <!-- Reset Form -->
          <Alert.Root variant="default" class="bg-blue-50 border-blue-200">
            <Alert.Title>Reset your password</Alert.Title>
            <Alert.Description class="text-blue-800 text-sm">
              We'll send a password reset link to your registered email address
            </Alert.Description>
          </Alert.Root>

          <div class="space-y-4">
            <div class="space-y-2">
              <Label for="email" class="text-sm font-medium">
                Email Address
              </Label>
              <div class="relative">
                <Mail
                  class="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground"
                />
                <Input
                  id="email"
                  type="email"
                  bind:value={email}
                  placeholder="you@example.com"
                  class="pl-10"
                  required
                />
              </div>
            </div>

            <Button onclick={handleSubmit} class="w-full" disabled={isLoading}>
              {#if isLoading}
                <Loader class="mr-2 h-4 w-4 animate-spin" />
                Sending...
              {:else}
                Send Reset Instructions
              {/if}
            </Button>
          </div>
        {:else}
          <!-- Success State -->
          <div class="text-center space-y-4">
            <div
              class="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center"
            >
              <CheckCircle class="h-8 w-8 text-green-600" />
            </div>

            <div class="space-y-2">
              <h3 class="font-semibold text-lg">Check your email</h3>
              <p class="text-muted-foreground text-sm">
                We've sent password reset instructions to:
                <br />
                <span class="font-medium text-foreground">{email}</span>
              </p>
            </div>

            <Alert.Root variant="default" class="bg-gray-50">
              <AlertCircle />
              <Alert.Description class="text-gray-600 text-sm">
                Didn't receive the email? Check your spam folder or
                <button
                  onclick={() => (isSubmitted = false)}
                  class="text-primary hover:underline ml-1"
                >
                  try again
                </button>
              </Alert.Description>
            </Alert.Root>

            <Button
              onclick={() => {
                goto("/login");
              }}
              variant="outline"
              class="w-full"
            >
              Return to Login
            </Button>
          </div>
        {/if}
      </Card.CardContent>
    </Card.Root>
  </div>
</div>
