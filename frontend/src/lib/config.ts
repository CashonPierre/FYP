/**
 * Central config for runtime values that differ between local dev and production.
 * All client-side code should import BACKEND from here instead of hardcoding the URL.
 *
 * Set PUBLIC_BACKEND_URL in .env (local) or your hosting provider's env vars (prod).
 * Vite exposes PUBLIC_-prefixed vars via import.meta.env at build time.
 */
export const BACKEND: string =
  (import.meta.env.PUBLIC_BACKEND_URL as string | undefined) ?? 'http://localhost:8000';
