const { spawn } = require('child_process');
const net = require('net');

function findAvailablePort(preferred = 3000) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', () => {
      const fallback = net.createServer();
      fallback.once('error', reject);
      fallback.listen(0, '127.0.0.1', () => {
        const address = fallback.address();
        fallback.close(() => resolve(address.port));
      });
    });
    server.listen(preferred, () => {
      server.close(() => resolve(preferred));
    });
  });
}

async function waitForUrl(url, timeoutMs = 30000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Next is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function isUrlReady(url) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);
    return response.ok;
  } catch {
    return false;
  }
}

function spawnProcess(command, args, options = {}) {
  return spawn(command, args, {
    stdio: 'inherit',
    shell: process.platform === 'win32',
    ...options,
  });
}

function stop(processes) {
  for (const child of processes) {
    if (!child.killed) child.kill('SIGTERM');
  }
}

function electronEnv(appUrl) {
  const env = {
    ...process.env,
    RAG_DESKTOP_URL: appUrl,
    NEXT_PUBLIC_APP_URL: appUrl,
  };
  delete env.ELECTRON_RUN_AS_NODE;
  return env;
}

async function main() {
  const port = Number(process.env.PORT || process.env.NEXT_PORT || 3000);
  const preferredUrl = `http://localhost:${port}`;
  if (await isUrlReady(preferredUrl)) {
    console.log(`[electron-dev] Reusing existing Next dev server at ${preferredUrl}.`);
    const electron = spawnProcess('electron', ['.'], {
      env: electronEnv(preferredUrl),
    });
    electron.once('exit', (code) => process.exit(code || 0));
    return;
  }

  const selectedPort = await findAvailablePort(port);
  const appUrl = `http://localhost:${selectedPort}`;
  const children = [];

  if (selectedPort !== port) {
    console.log(`[electron-dev] Port ${port} is busy; using ${selectedPort}.`);
  }

  const next = spawnProcess('npm', ['run', 'dev', '--', '-p', String(selectedPort)]);
  children.push(next);

  const cleanup = () => stop(children);
  process.once('SIGINT', () => {
    cleanup();
    process.exit(130);
  });
  process.once('SIGTERM', () => {
    cleanup();
    process.exit(143);
  });

  next.once('exit', (code) => {
    cleanup();
    process.exit(code || 1);
  });

  await waitForUrl(appUrl);

  const electron = spawnProcess('electron', ['.'], {
    env: electronEnv(appUrl),
  });
  children.push(electron);

  electron.once('exit', (code) => {
    cleanup();
    process.exit(code || 0);
  });
}

main().catch((error) => {
  console.error(`[electron-dev] ${error.message}`);
  process.exit(1);
});
