# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import shutil
import os

# Helper to find pandoc
pandoc_path = shutil.which("pandoc")
binaries = []
if pandoc_path:
    print(f"Found pandoc at: {pandoc_path}")
    binaries.append((pandoc_path, '.'))
else:
    print("WARNING: Pandoc not found!")

a = Analysis(
    ['scripts/process_pipeline.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=['pandas', 'litellm', 'yaml', 'docx', 'bs4'],
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
    name='process_pipeline',
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
    name='process_pipeline',
)
