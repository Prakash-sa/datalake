const { app, BrowserWindow, ipcMain, protocol, shell, session } = require('electron');
const { spawn } = require('child_process');
const crypto = require('crypto');
const fs = require('fs/promises');
const net = require('net');
const path = require('path');

const DEFAULT_APP_URL = 'http://localhost:3000';
const APP_PROTOCOL = 'app';
const isDev = !app.isPackaged;

let backendProcess = null;
let backendBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
let backendToken = null;

protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_PROTOCOL,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
    },
  },
]);

function getAppUrl() {
  if (process.env.RAG_DESKTOP_URL || process.env.NEXT_PUBLIC_APP_URL) {
    return process.env.RAG_DESKTOP_URL || process.env.NEXT_PUBLIC_APP_URL;
  }

  return isDev ? DEFAULT_APP_URL : `${APP_PROTOCOL}://local/index.html`;
}

function getStaticRoot() {
  return path.join(__dirname, '..', 'out');
}

function getContentType(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  const contentTypes = {
    '.css': 'text/css',
    '.html': 'text/html',
    '.ico': 'image/x-icon',
    '.js': 'text/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.txt': 'text/plain',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
  };

  return contentTypes[extension] || 'application/octet-stream';
}

async function resolveStaticPath(url) {
  const requestUrl = new URL(url);
  const requestedPath = decodeURIComponent(requestUrl.pathname);
  const relativePath = requestedPath === '/' ? 'index.html' : requestedPath.slice(1);
  const staticRoot = getStaticRoot();
  const filePath = path.normalize(path.join(staticRoot, relativePath));

  if (!filePath.startsWith(staticRoot)) {
    throw new Error('Blocked invalid asset path');
  }

  return filePath;
}

function registerAppProtocol() {
  protocol.handle(APP_PROTOCOL, async (request) => {
    try {
      const filePath = await resolveStaticPath(request.url);
      const data = await fs.readFile(filePath);
      return new Response(data, {
        headers: { 'content-type': getContentType(filePath) },
      });
    } catch {
      const fallback = path.join(getStaticRoot(), 'index.html');
      const data = await fs.readFile(fallback);
      return new Response(data, {
        headers: { 'content-type': 'text/html' },
      });
    }
  });
}

function findAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
  });
}

function getBackendCommand() {
  if (process.env.RAG_BACKEND_COMMAND) {
    return {
      command: process.env.RAG_BACKEND_COMMAND,
      args: process.env.RAG_BACKEND_ARGS ? process.env.RAG_BACKEND_ARGS.split(' ') : [],
      cwd: process.cwd(),
    };
  }

  if (isDev) {
    return {
      command: process.env.PYTHON || 'python3',
      args: ['main.py'],
      cwd: path.join(__dirname, '..', '..', 'backend'),
    };
  }

  const executable = process.platform === 'win32' ? 'rag-backend.exe' : 'rag-backend';
  return {
    command: path.join(process.resourcesPath, 'backend', 'rag-backend', executable),
    args: [],
    cwd: path.join(process.resourcesPath, 'backend', 'rag-backend'),
  };
}

async function waitForBackend(timeoutMs = 30000) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(`${backendBaseUrl}/health`, {
        headers: backendToken ? { Authorization: `Bearer ${backendToken}` } : {},
      });
      if (response.ok) return;
    } catch {
      // Keep polling until the sidecar opens the selected port.
    }

    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error('Backend did not become healthy before timeout');
}

async function startBackend() {
  if (process.env.RAG_START_BACKEND === 'false') return;

  const port = await findAvailablePort();
  backendBaseUrl = `http://127.0.0.1:${port}`;
  backendToken = crypto.randomBytes(32).toString('hex');

  const backend = getBackendCommand();
  backendProcess = spawn(backend.command, backend.args, {
    cwd: backend.cwd,
    env: {
      ...process.env,
      ENV: 'production',
      HOST: '127.0.0.1',
      PORT: String(port),
      WORKERS: '1',
      RAG_API_TOKEN: backendToken,
      CHROMA_PATH: path.join(app.getPath('userData'), 'vector', 'chroma'),
      ALLOWED_ORIGINS: `${APP_PROTOCOL}://local,http://localhost:3000`,
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  backendProcess.on('exit', (code, signal) => {
    backendProcess = null;
    if (code !== 0 && signal !== 'SIGTERM') {
      console.error(`RAG backend exited with code ${code || 'unknown'}`);
    }
  });

  backendProcess.on('error', (error) => {
    console.error(`Failed to start RAG backend: ${error.message}`);
  });

  backendProcess.stderr.on('data', (chunk) => {
    console.error(`[rag-backend] ${chunk.toString().trim()}`);
  });

  await waitForBackend();
}

function stopBackend() {
  if (!backendProcess) return;

  backendProcess.kill('SIGTERM');
  setTimeout(() => {
    if (backendProcess) backendProcess.kill('SIGKILL');
  }, 5000).unref();
}

function registerApiProxy() {
  ipcMain.handle('api:request', async (_event, request) => {
    const method = request?.method || 'GET';
    const requestPath = request?.path;

    if (!['GET', 'POST'].includes(method) || typeof requestPath !== 'string' || !requestPath.startsWith('/')) {
      return { ok: false, status: 400, error: 'Invalid API request' };
    }

    const response = await fetch(`${backendBaseUrl}${requestPath}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(backendToken ? { Authorization: `Bearer ${backendToken}` } : {}),
      },
      body: request.body === undefined ? undefined : JSON.stringify(request.body),
    });

    const text = await response.text();
    let data;
    try {
      data = text ? JSON.parse(text) : undefined;
    } catch {
      data = undefined;
    }

    return {
      ok: response.ok,
      status: response.status,
      data,
      error: response.ok ? undefined : data?.detail || text || 'API request failed',
    };
  });
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: 'RAG Query Engine',
    backgroundColor: '#0f172a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  window.once('ready-to-show', () => window.show());

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://') || url.startsWith('mailto:')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  window.webContents.on('will-navigate', (event, url) => {
    const allowed = url.startsWith(`${APP_PROTOCOL}://local`) || url.startsWith(DEFAULT_APP_URL);
    if (!allowed) event.preventDefault();
  });

  window.loadURL(getAppUrl());
}

app.whenReady().then(async () => {
  registerAppProtocol();
  registerApiProxy();
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  try {
    await startBackend();
  } catch (error) {
    console.error(error);
  }
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', stopBackend);
