import { test, expect, _electron as electron, type ElectronApplication, type Page } from '@playwright/test';
import * as path from 'node:path';

let app: ElectronApplication;
let window: Page;

const ROOT = path.resolve(__dirname, '..');

test.beforeAll(async () => {
  // ELECTRON_RUN_AS_NODE makes the binary behave as plain Node, which rejects
  // the browser flags Playwright launches with. Some shells export it, so it is
  // stripped rather than assumed absent.
  const { ELECTRON_RUN_AS_NODE: _ignored, ...cleanEnv } = process.env;

  app = await electron.launch({
    args: [ROOT],
    env: {
      ...cleanEnv,
      // The renderer loads the static export over app://, so no dev server is
      // needed. The sidecar is skipped: these tests assert the shell boots and
      // its security boundary holds, not backend behaviour.
      NODE_ENV: 'production',
      // Load over app:// as a packaged build would, rather than reaching for a
      // dev server that is not running.
      RAG_FORCE_PACKAGED: 'true',
      RAG_START_BACKEND: 'false',
      RAG_ENABLE_UPDATES: 'false',
    },
  });
  window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');
});

test.afterAll(async () => {
  await app?.close();
});

test('serves the UI over the app:// protocol, not file://', async () => {
  // file:// was explicitly rejected in the plan; a regression here would
  // quietly widen the renderer's privileges.
  expect(window.url()).toMatch(/^app:\/\//);
});

test('opens a single window', async () => {
  expect(app.windows()).toHaveLength(1);
});

test('renders the application shell', async () => {
  await expect(window.locator('body')).toContainText(/Document RAG Engine|Set up your local RAG engine/);
});

test('exposes only the narrow preload surface', async () => {
  const surface = await window.evaluate(() => {
    const desktop = (window as unknown as { desktop?: Record<string, unknown> }).desktop;
    return desktop ? Object.keys(desktop).sort() : null;
  });

  expect(surface).toEqual([
    'apiRequest',
    'isElectron',
    'platform',
    'selectDocuments',
    'streamChat',
    'streamQuery',
  ]);
});

test('does not leak Node or Electron internals into the renderer', async () => {
  const leaked = await window.evaluate(() => {
    const scope = window as unknown as Record<string, unknown>;
    return {
      require: typeof scope.require,
      process: typeof scope.process,
      ipcRenderer: typeof scope.ipcRenderer,
      electron: typeof scope.electron,
    };
  });

  expect(leaked).toEqual({
    require: 'undefined',
    process: 'undefined',
    ipcRenderer: 'undefined',
    electron: 'undefined',
  });
});

