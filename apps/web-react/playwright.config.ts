import { defineConfig, devices } from '@playwright/test'

// Runs against a stack that is already up (no webServer block on purpose): Identity, Finance Profile, Financial IQ,
// the Edge Gateway and `npm run dev` on :5173, with the demo accounts from infra/seed/seed_demo_users.py.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  // POST /auth/login is limited to 5 attempts per minute per IP at the gateway; retries would eat into that
  retries: 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5173',
    locale: 'tr-TR',
    screenshot: 'on',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
