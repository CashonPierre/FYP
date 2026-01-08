<script lang="ts">
  import * as Form from '$lib/components/ui/form/index.js';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { Checkbox } from '$lib/components/ui/checkbox/index.js';
  import { Lock, Mail, User, Eye, EyeOff, Loader } from '@lucide/svelte';
  import { signupUser, validateEmail, validatePassword } from '$lib/utils/auth.js';
  import { goto } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import type { SignupFormData } from '$lib/types/auth.js';
  import { _ } from 'svelte-i18n';

  let showPassword = $state(false);
  let showConfirmPassword = $state(false);
  let isLoading = $state(false);

  const validateConfirmPassword = (confirmPassword: string, values: SignupFormData): string | null => {
    if (!confirmPassword) return 'Please confirm your password';
    if (confirmPassword !== values.password) return 'Passwords do not match';
    return null;
  };

  const validateTerms = (agreeToTerms: boolean): string | null => {
    if (!agreeToTerms) return 'You must agree to the terms';
    return null;
  };

  </script>

<form method="POST">
<p>hello</p>
</form>
