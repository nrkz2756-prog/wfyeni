# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

# Proje kök dizini (spec dosyasının bulunduğu yer)
BASE_DIR = os.path.dirname(os.path.abspath(SPEC))
OBF_DIR  = os.path.join(BASE_DIR, 'obf')

datas = [
    (os.path.join(OBF_DIR, 'pyarmor_runtime_000000'), 'pyarmor_runtime_000000'),
]
binaries = []
hiddenimports = [
    'launcher',
    'license_manager',
    'comtypes',
    'comtypes.gen',
    'comtypes.client._generate',
    'comtypes.client._events',
    'comtypes.typeinfo',
    'comtypes._memberspec',
    'comtypes.automation',
    'comtypes._comobject',
    'comtypes._vtbl',
    'comtypes.connectionpoints',
    'pyperclip',
    'psutil',
    'win32gui',
    'win32con',
    'win32process',
    'win32api',
    'win32clipboard',
    'pyarmor_runtime_000000',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
]
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    [os.path.join(BASE_DIR, 'gui.py')],
    pathex=[BASE_DIR, OBF_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
        'pyautogui', 'pyscreeze', 'mouseinfo', 'pygetwindow',
        'numpy', 'numpy.core', 'numpy.linalg',
        'unittest', 'doctest', 'lib2to3', 'pydoc',
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure, key='F0rZa_W0lfT3aM_2026!')

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Forza_Wolfteam',
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
