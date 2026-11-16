import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// Server tests run in node; component tests ask for a DOM with `// @vitest-environment happy-dom`.
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    exclude: ['tests/e2e/**'],
  },
})
