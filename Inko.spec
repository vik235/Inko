# PyInstaller spec for Inko
# Build:  pyinstaller --noconfirm Inko.spec
# Output: dist/Inko/Inko.exe (one-folder bundle)
# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path


def _find_openssl_dlls():
    """Locate OpenSSL DLLs that Python's _ssl.pyd / _hashlib.pyd depend on.

    Anaconda ships Python with stdlib .pyd files in <anaconda>\\DLLs\\ but the
    OpenSSL libraries themselves live in <anaconda>\\Library\\bin\\, which is
    NOT on Python's DLL search path inside a frozen build. PyInstaller has to
    pick them up explicitly.
    """
    needed = (
        # OpenSSL — _ssl.pyd, _hashlib.pyd
        "libssl-3-x64.dll",
        "libcrypto-3-x64.dll",
        # ctypes
        "libffi-8.dll",
        # _sqlite3.pyd
        "sqlite3.dll",
        # _bz2.pyd (Anaconda dynamically links bz2)
        "libbz2.dll",
        # _lzma.pyd
        "liblzma.dll",
        # zlib
        "zlib.dll",
    )
    candidates: list[Path] = []
    # 1. The interpreter's own DLLs dir
    candidates.append(Path(sys.executable).parent / "DLLs")
    # 2. Anaconda's Library\bin (most common cause of this issue)
    candidates.append(Path(sys.executable).parent / "Library" / "bin")
    # 3. Walk back two levels from a venv launcher
    candidates.append(Path(sys.executable).parent.parent.parent / "Library" / "bin")
    # 4. Default Anaconda install
    user_anaconda = Path(os.environ.get("LOCALAPPDATA", "")) / "anaconda3" / "Library" / "bin"
    candidates.append(user_anaconda)

    found = []
    seen = set()
    for d in candidates:
        if not d.exists():
            continue
        for name in needed:
            p = d / name
            if p.exists() and str(p).lower() not in seen:
                seen.add(str(p).lower())
                found.append((str(p), "."))  # dest "." -> bundle next to the .exe
    return found


extra_binaries = _find_openssl_dlls()
print(f"[Inko.spec] Bundling extra binaries: {[b[0] for b in extra_binaries]}")

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=extra_binaries,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[],
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
    name='Inko',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    upx=False,
    upx_exclude=[],
    name='Inko',
)
