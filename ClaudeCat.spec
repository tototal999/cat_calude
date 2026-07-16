# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['cat.py'],
    pathex=[],
    binaries=[],
    datas=[('skins', 'skins')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Pulled in by other packages' PyInstaller hooks (e.g. Pillow/requests
    # detecting these installed in the build env) even though this project
    # never imports them - excluding cuts ~50MB of dead weight from the exe.
    excludes=['numpy', 'cryptography', 'win32ctypes', 'win32com', 'win32api',
              'win32con', 'pythoncom', 'pywintypes'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ClaudeCat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
