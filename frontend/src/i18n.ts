import { browser } from '$app/environment';
import { addMessages, init, getLocaleFromNavigator } from 'svelte-i18n';
import en from '$lib/locales/en.json' with { type: 'json' };
import zh from '$lib/locales/zh.json' with { type: 'json' };

addMessages('en', en);
addMessages('zh', zh);

export const initI18n = () =>
  init({
    fallbackLocale: 'en',
    initialLocale: browser ? (getLocaleFromNavigator() ?? 'en') : 'en',
  });