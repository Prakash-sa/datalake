/**
 * Captures screenshots of the running desktop app for the README.
 *
 * Not part of the CI suite: it needs a backend seeded with documents and the
 * frontend dev server running. Example:
 * `NEXT_PUBLIC_API_URL=http://127.0.0.1:8123 npm run dev`
 * `CAPTURE_API_URL=http://127.0.0.1:8123 npx playwright test e2e/capture.spec.ts`
 */
import { test, _electron as electron, type ElectronApplication, type Page } from '@playwright/test';
import * as path from 'node:path';

const OUT = path.resolve(__dirname, '..', '..', 'docs', 'assets', 'screenshots');
const ROOT = path.resolve(__dirname, '..');

let app: ElectronApplication;
let window: Page;

test.beforeAll(async () => {
  const { ELECTRON_RUN_AS_NODE: _ignored, ...cleanEnv } = process.env;
  app = await electron.launch({
    args: [ROOT],
    env: {
      ...cleanEnv,
      NEXT_PUBLIC_API_URL: process.env.CAPTURE_API_URL || 'http://127.0.0.1:8123',
      RAG_DESKTOP_URL: process.env.CAPTURE_APP_URL || 'http://localhost:3000',
      // Talk to the pre-seeded backend instead of spawning an empty one.
      RAG_START_BACKEND: 'false',
      RAG_ENABLE_UPDATES: 'false',
    },
  });
  window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');
  await window.setViewportSize({ width: 1440, height: 900 });
});

test.afterAll(async () => {
  await app?.close();
});

async function shot(name: string) {
  await window.waitForTimeout(700);
  await window.screenshot({ path: path.join(OUT, `${name}.png`) });
}

// A cold generation model can take minutes; the suite default is 60s.
test.setTimeout(900_000);

test('capture every view', async () => {
  await window.waitForTimeout(2500);

  // Setup only appears when something is missing. With a healthy backend it is
  // skipped entirely, so this must not assume it is on screen.
  const skip = window.getByText('Skip for now');
  if (await skip.isVisible().catch(() => false)) {
    await shot('01-first-run-setup');
    await skip.click();
    await window.waitForTimeout(800);
  }

  // Chat with results and expanded sources.
  await window.getByRole('button', { name: /^Fast$/ }).click();
  await window
    .getByPlaceholder('Ask a question about your documents…')
    .fill('How does the app keep document answers local and cited?');
  await window.getByRole('button', { name: /^Send$/ }).click();
  // Wait for streaming to finish rather than guessing: the Stop button is only
  // present while generating.
  await window
    .getByRole('button', { name: /Stop/ })
    .waitFor({ state: 'detached', timeout: 240_000 })
    .catch(() => {});
  await window.waitForTimeout(1200);
  const showSources = window.getByRole('button', { name: /Show \d+ sources/ }).last();
  if (await showSources.isVisible().catch(() => false)) {
    await showSources.click();
    await window.waitForTimeout(300);
  }
  await shot('02-query-and-sources');

  await window.getByRole('button', { name: /Library/ }).click();
  await shot('03-library');

  await window.getByRole('button', { name: /Activity/ }).click();
  await shot('04-activity');

  await window.getByRole('button', { name: /Diagnostics/ }).click();
  await shot('05-diagnostics');

  await window.getByRole('button', { name: /Settings/ }).click();
  await shot('06-settings');
});
