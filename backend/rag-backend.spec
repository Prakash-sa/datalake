# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller bundle for the desktop sidecar.

Entry point is the package's __main__, with src/ on the analysis path so
`rag_backend.*` resolves without the package being pip-installed.
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None
backend_dir = Path(SPECPATH).resolve()
src_dir = backend_dir / 'src'
llama_datas = collect_data_files('llama_cpp')
llama_binaries = collect_dynamic_libs('llama_cpp')
llama_hiddenimports = collect_submodules('llama_cpp')
chroma_hiddenimports = []
for module in (
    'chromadb.api',
    'chromadb.auth',
    'chromadb.db',
    'chromadb.migrations',
    'chromadb.proto',
    'chromadb.quota',
    'chromadb.rate_limit',
    'chromadb.segment',
    'chromadb.telemetry',
    'chromadb.utils',
):
    chroma_hiddenimports.extend(collect_submodules(module))

a = Analysis(
    [str(src_dir / 'rag_backend' / '__main__.py')],
    pathex=[str(src_dir)],
    binaries=llama_binaries,
    # The embedding model ships inside the sidecar; without it the app would
    # need Ollama to index anything.
    datas=[(str(src_dir / 'rag_backend' / 'models'), 'rag_backend/models'), *llama_datas],
    hiddenimports=[
        'chromadb',
        'onnxruntime',
        'tokenizers',
        'langchain_ollama',
        'pydantic_settings',
        'uvicorn.logging',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        *chroma_hiddenimports,
        *llama_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='rag-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='rag-backend',
)
