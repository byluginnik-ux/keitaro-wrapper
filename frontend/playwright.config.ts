import { defineConfig } from '@playwright/test'

// The whole service runs for real; only Keitaro is replaced by the fake tracker of the backend tests.
const TRACKER = 'http://127.0.0.1:8791'
const BACKEND = 'http://127.0.0.1:8792'
const FRONTEND = 'http://127.0.0.1:3919'

export default defineConfig({
  testDir: 'tests/e2e',
  // the fake tracker is one for all tests, and one of them makes it fail on purpose
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: FRONTEND,
    trace: 'retain-on-failure',
    launchOptions: { executablePath: process.env.E2E_CHROMIUM || undefined },
  },
  metadata: { tracker: TRACKER },
  webServer: [
    {
      command: 'uv run uvicorn tests.fake_tracker:app --port 8791 --log-level warning',
      cwd: '../backend',
      url: `${TRACKER}/admin_api/v1/domains`,
      reuseExistingServer: false,
    },
    {
      command: 'uv run uvicorn --factory app.main:create_app --port 8792 --log-level warning',
      cwd: '../backend',
      // a failing tracker is retried: keep the pauses between attempts short
      env: { KEITARO_BASE_URL: TRACKER, KEITARO_API_KEY: 'fake-key', STORAGE_BACKEND: 'memory', TASK_RETRY_DELAY: '0.1' },
      url: `${BACKEND}/health`,
      reuseExistingServer: false,
    },
    {
      command: './node_modules/.bin/nuxt build && node .output/server/index.mjs',
      env: { NUXT_BACKEND_GRAPHQL_URL: `${BACKEND}/graphql`, HOST: '127.0.0.1', PORT: '3919' },
      url: `${FRONTEND}/api/health`,
      timeout: 240_000,
      reuseExistingServer: false,
    },
  ],
})
