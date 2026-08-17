# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller bundle for the desktop sidecar.

Entry point is the package's __main__, with src/ on the analysis path so
`rag_backend.*` resolves without the package being pip-installed.
"""

from pathlib import Path

block_cipher = None
backend_dir = Path(SPECPATH).resolve()
src_dir = backend_dir / 'src'

a = Analysis(
    [str(src_dir / 'rag_backend' / '__main__.py')],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'chromadb',
        'langchain_ollama',
        'pydantic_settings',
        'uvicorn.logging',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
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
