import { defineConfig } from '@playwright/test';

/**
 * Electron end-to-end tests.
 *
 * These exercise the packaged shell: the app:// protocol, the preload bridge,
 * and the sidecar lifecycle. They are separate from the Vitest suite, which
 * covers components in isolation with a stubbed backend.
 */
export default defineConfig({
  testDir: './e2e',
  // The capture spec drives a backend seeded with documents and is run by
  // hand to refresh the README screenshots; CI has no such backend.
  testIgnore: process.env.CAPTURE_SCREENSHOTS === 'true' ? [] : ['**/capture.spec.ts'],
  // Electron launches one app instance per worker; serial keeps the window and
  // the sidecar port predictable.
  workers: 1,
  fullyParallel: false,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? 'github' : 'list',
  use: { trace: 'retain-on-failure' },
});
