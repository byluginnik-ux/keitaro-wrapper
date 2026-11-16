import { THEME_BOOT_SCRIPT } from './app/composables/theme'

export default defineNuxtConfig({
  modules: ['@nuxt/eslint'],
  devtools: { enabled: true },
  app: {
    head: {
      htmlAttrs: { lang: 'ru' },
      title: 'Keitaro Wrapper',
      meta: [{ name: 'description', content: 'Создание кампаний Keitaro и редактор офферов в потоках' }],
      script: [{ innerHTML: THEME_BOOT_SCRIPT, tagPosition: 'head' }],
    },
  },
  css: [
    '@fontsource-variable/montserrat/index.css',
    '@fontsource/jetbrains-mono/400.css',
    '@fontsource/jetbrains-mono/700.css',
    '~/assets/styles/tokens.css',
    '~/assets/styles/base.css',
  ],
  runtimeConfig: {
    // server-only: the browser never learns where the backend lives (R-ARCH-04)
    backendGraphqlUrl: 'http://127.0.0.1:8000/graphql',
  },
  compatibilityDate: '2026-11-01',
  typescript: { strict: true },
  eslint: { config: { stylistic: true } },
})
