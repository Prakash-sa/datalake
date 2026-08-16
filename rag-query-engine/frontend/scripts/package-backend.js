const { spawnSync } = require('child_process');
const path = require('path');

const candidates = process.env.PYTHON ? [process.env.PYTHON] : ['python3', 'python'];
const frontendDir = path.resolve(__dirname, '..');
const backendSpec = path.resolve(frontendDir, '..', 'backend', 'rag-backend.spec');
const distPath = path.resolve(frontendDir, '..', 'backend', 'dist');
const workPath = path.resolve(frontendDir, '..', 'backend', 'build');

function getVersion(command) {
  const result = spawnSync(command, ['-c', 'import sys; print(".".join(map(str, sys.version_info[:3])))'], {
    encoding: 'utf8',
  });

  if (result.status !== 0) return null;
  return result.stdout.trim();
}

function isSupported(version) {
  const [major, minor] = version.split('.').map(Number);
  return major > 3 || (major === 3 && minor >= 12);
}

const python = candidates.find((command) => {
  const version = getVersion(command);
  return version && isSupported(version);
});

if (!python) {
  console.error('Python 3.12+ is required to package the backend sidecar. Set PYTHON=/path/to/python3 if needed.');
  process.exit(1);
}

const result = spawnSync(
  python,
  ['-m', 'PyInstaller', backendSpec, '--distpath', distPath, '--workpath', workPath],
  { stdio: 'inherit' },
);

process.exit(result.status ?? 1);
