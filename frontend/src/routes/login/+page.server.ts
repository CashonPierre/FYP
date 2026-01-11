import type { Actions } from './$types.js';
import { fail } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

import { loginSchema } from '$lib/schemas/LoginSchema.js';

const backendOrigin = env.BACKEND_ORIGIN ?? 'http://localhost:8000';

export const actions: Actions = {
  login: async ({ request, fetch }) => {
    const data = await request.formData();
    const email = String(data.get('email') ?? '').trim();
    const password = String(data.get('password') ?? '');
    const rememberMeRaw = String(data.get('rememberMe') ?? 'false').toLowerCase();
    const rememberMe = rememberMeRaw === 'true' || rememberMeRaw === '1' || rememberMeRaw === 'on';

    const parsed = loginSchema.safeParse({ email, password });
    if (!parsed.success) {
      return fail(400, { message: 'Invalid email or password format.' });
    }

    let res: Response;
    try {
      res = await fetch(`${backendOrigin}/auth/login`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ email, password, rememberMe }),
      });
    } catch {
      return fail(503, { message: `Backend unavailable at ${backendOrigin}` });
    }

    if (!res.ok) {
      const text = await res.text();
      try {
        const json = JSON.parse(text) as { detail?: string };
        return fail(res.status, { message: json.detail ?? 'Login failed.' });
      } catch {
        return fail(res.status, { message: text || 'Login failed.' });
      }
    }

    const json = (await res.json()) as { access_token?: string; token_type?: string };
    if (!json.access_token) {
      return fail(500, { message: 'Login succeeded but no token returned.' });
    }

    return { access_token: json.access_token, token_type: json.token_type ?? 'bearer' };
  },
};
