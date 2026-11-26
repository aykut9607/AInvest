import { defineConfig } from 'vitest/config'

// unit tests only (API layer, session, labels); they mock fetch and never reach a service.
// End-to-end tests live in e2e/ and run with Playwright against a running stack (npm run e2e).
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
