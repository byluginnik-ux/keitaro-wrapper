export default defineNuxtConfig({
  modules: ['@nuxt/eslint'],
  devtools: { enabled: true },
  runtimeConfig: {
    // server-only: the browser never learns where the backend lives (R-ARCH-04)
    backendGraphqlUrl: 'http://127.0.0.1:8000/graphql',
  },
  compatibilityDate: '2026-11-01',
  typescript: { strict: true },
  eslint: { config: { stylistic: true } },
})
