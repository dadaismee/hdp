# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import shutil
import os

from PyInstaller.utils.hooks import collect_all

datas = [
    ('system_prompt.txt', '.'),
    ('config.yml', '.')
]
binaries = []
hiddenimports = ['pandas', 'litellm', 'yaml', 'docx', 'bs4', 'tiktoken_ext.openai_public', 'tiktoken_ext']

# Collect all tiktoken resources
tmp_ret = collect_all('tiktoken')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Collect all litellm resources
tmp_ret_lite = collect_all('litellm')
datas += tmp_ret_lite[0]
binaries += tmp_ret_lite[1]
hiddenimports += tmp_ret_lite[2]

# Helper to find pandoc
# Helper to find pandoc
# Helper to find pandoc
pandoc_path = None

# 1. Try resolving via shutil.which
which_path = shutil.which("pandoc")

# 2. Define heuristic for "real" binary (size > 1MB)
def is_real_pandoc(path):
    if not path or not os.path.exists(path):
        return False
    # Pandoc is usually ~50-100MB. Shims are ~10-20KB.
    # Let's set a safe threshold of 5MB.
    try:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"Checking {path}: {size_mb:.2f} MB")
        return size_mb > 5
    except OSError:
        return False

# 3. Known locations on Windows (Chocolatey/Standard)
known_paths = [
    r"C:\Program Files\Pandoc\pandoc.exe",
    r"C:\Program Files (x86)\Pandoc\pandoc.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Pandoc\pandoc.exe"),
    os.path.expandvars(r"%ProgramData%\chocolatey\lib\pandoc\tools\pandoc.exe"),
    os.path.expandvars(r"%ProgramData%\chocolatey\bin\pandoc.exe"), # Might be shim
]

# Check which_path first, if it fails size check, look in known_paths
candidates = []
if which_path: candidates.append(which_path)
candidates.extend(known_paths)

found = False
for path in candidates:
    if is_real_pandoc(path):
        pandoc_path = path
        found = True
        break
    else:
        # If it's a shim, maybe we can resolve it? 
        # But usually standard paths are better.
        pass

if pandoc_path:
    print(f"Found REAL pandoc at: {pandoc_path}")
    binaries.append((pandoc_path, '.'))
else:
    print(f"Candidates checked: {candidates}")
    raise FileNotFoundError("CRITICAL: Real Pandoc binary (size > 5MB) not found! Ensure Pandoc is installed properly.")

a = Analysis(
    ['scripts/process_pipeline.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
