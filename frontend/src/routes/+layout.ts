import { waitLocale } from 'svelte-i18n';
import { initI18n } from '../i18n';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async () => {
  initI18n();
  await waitLocale();
};
