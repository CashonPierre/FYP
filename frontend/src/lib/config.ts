/**
 * Central config for runtime values that differ between local dev and production.
 * All client-side code should import BACKEND from here instead of hardcoding the URL.
 *
 * PUBLIC_BACKEND_URL must be set in .env (local) and in the hosting provider's env
 * vars (prod). SvelteKit's $env/static/public fails the build if it's missing, so
 * there is no silent localhost fallback.
 */
import { PUBLIC_BACKEND_URL } from '$env/static/public';

export const BACKEND: string = PUBLIC_BACKEND_URL;
