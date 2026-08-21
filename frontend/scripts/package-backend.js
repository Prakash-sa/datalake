const { spawnSync } = require('child_process');
const path = require('path');

const candidates = process.env.PYTHON ? [process.env.PYTHON] : ['python3', 'python'];
const frontendDir = path.resolve(__dirname, '..');
const backendDir = path.resolve(frontendDir, '..', 'backend');
const backendSpec = path.resolve(frontendDir, '..', 'backend', 'rag-backend.spec');
const distPath = path.resolve(frontendDir, '..', 'backend', 'dist');
const workPath = path.resolve(frontendDir, '..', 'backend', 'build');
const pyinstallerConfigPath = path.resolve(workPath, 'pyinstaller-config');
const generationModel = path.resolve(
  backendDir,
  'src',
  'rag_backend',
  'models',
  'qwen2.5-1.5b-instruct-q4_k_m.gguf',
);

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

const runtimeCheck = spawnSync(python, ['-c', 'import llama_cpp'], { encoding: 'utf8' });
if (runtimeCheck.status !== 0) {
  console.error(
    'llama-cpp-python is required to package local GGUF generation. ' +
      'Install backend extras with: python -m pip install "./backend[packaging,local-generation]"',
  );
  process.exit(1);
}

const modelCheck = spawnSync(
  python,
  [
    '-c',
    `from pathlib import Path; raise SystemExit(0 if Path(${JSON.stringify(generationModel)}).is_file() else 1)`,
  ],
  { encoding: 'utf8' },
);
if (modelCheck.status !== 0) {
  console.error(
    `Bundled generation model is missing: ${generationModel}\n` +
      'Run backend/scripts/fetch_generation_model.py with LOCAL_LLM_GGUF_URL and LOCAL_LLM_GGUF_SHA256 set before packaging.',
  );
  process.exit(1);
}

const result = spawnSync(
  python,
  [
    '-m',
    'PyInstaller',
    '--noconfirm',
    backendSpec,
    '--distpath',
    distPath,
    '--workpath',
    workPath,
  ],
  {
    stdio: 'inherit',
    env: {
      ...process.env,
      PYINSTALLER_CONFIG_DIR: process.env.PYINSTALLER_CONFIG_DIR || pyinstallerConfigPath,
    },
  },
);

process.exit(result.status ?? 1);
