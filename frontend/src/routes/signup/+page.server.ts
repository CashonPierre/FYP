import type { Actions } from './$types.js'
import { fail } from '@sveltejs/kit'
import { env } from '$env/dynamic/private'
import { PUBLIC_BACKEND_URL } from '$env/static/public'

import { signupSchema } from '$lib/schemas/SignupSchema.js'

const backendOrigin = env.BACKEND_ORIGIN ?? PUBLIC_BACKEND_URL

export const actions: Actions = {
  register: async ({ request, fetch }) => {
    const data = await request.formData()

    const username = String(data.get('name') ?? '').trim()
    const email = String(data.get('email') ?? '').trim()
    const password = String(data.get('password') ?? '')
    const confirmPassword = String(data.get('confirmPassword') ?? '')
    const agreeToTermsRaw = String(data.get('agreeToTerms') ?? 'false').toLowerCase()
    const agreeToTerms =
      agreeToTermsRaw === 'true' || agreeToTermsRaw === '1' || agreeToTermsRaw === 'on'

    const parsed = signupSchema.safeParse({
      username,
      email,
      password,
      confirmPassword,
      agreeToTerms,
    })
    if (!parsed.success) {
      return fail(400, { message: parsed.error.issues[0]?.message ?? 'Invalid signup form.' })
    }

    let res: Response
    try {
      res = await fetch(`${backendOrigin}/auth/register`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          username: parsed.data.username,
          email: parsed.data.email,
          password: parsed.data.password,
        }),
      })
    } catch {
      return fail(503, { message: `Backend unavailable at ${backendOrigin}` })
    }

    if (!res.ok) {
      const text = await res.text()
      try {
        const json = JSON.parse(text) as { detail?: string }
        return fail(res.status, { message: json.detail ?? 'Signup failed.' })
      } catch {
        return fail(res.status, { message: text || 'Signup failed.' })
      }
    }

    const message = await res.text()
    return { message: message || 'Registered. Please verify your email, then login.' }
  },
}

