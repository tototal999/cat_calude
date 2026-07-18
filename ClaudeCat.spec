# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

_python_root = Path(sys.base_prefix)
_python_dlls = _python_root / 'DLLs'
_tk_binaries = [
    (str(_python_dlls / '_tkinter.pyd'), '.'),
    (str(_python_dlls / 'tcl86t.dll'), '.'),
    (str(_python_dlls / 'tk86t.dll'), '.'),
]

a = Analysis(
    ['cat.py'],
    pathex=[],
    binaries=_tk_binaries,
    # chat.html is a data file (not a Python import) - pywebview loads it
    # from disk by path, so PyInstaller's static import analysis can't see
    # it and it must be listed explicitly like skins/.
    datas=[('skins', 'skins'), ('frontend', 'frontend'), ('claudecat.ico', '.'),
           (str(_python_root / 'tcl'), 'tcl'),
           (str(_python_root / 'Lib' / 'tkinter'), 'tkinter')],
    hiddenimports=['tkinter', 'tkinter.ttk', 'openpyxl', 'pptx', 'xlrd'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Pulled in by other packages' PyInstaller hooks (e.g. Pillow/requests
    # detecting these installed in the build env) even though this project
    # never imports them - excluding cuts ~50MB of dead weight from the exe.
    # win32com/win32api/win32con/pythoncom/pywintypes were excluded before
    # Part 2 - pywebview's Windows (Edge WebView2) backend actually needs
    # them, so only numpy/cryptography/win32ctypes stay excluded now.
    excludes=['cryptography', 'win32ctypes', 'pandas', 'numpy', 'pyarrow',
              'onnxruntime', 'grpc', 'oracledb', 'pypdfium2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ClaudeCat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='claudecat.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ClaudeCat',
)
