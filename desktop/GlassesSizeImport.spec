# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — single-file, windowed .exe.

Build from the SHORT-PATH venv (the Store Python's path is long enough that
installing PySide6 fails with "enable-long-paths"), from the repo root:

    "C:\\gv\\Scripts\\pyinstaller.exe" desktop\\GlassesSizeImport.spec

Output: dist\\GlassesSizeImport.exe — needs nothing installed on the target
machine. It is large and unsigned, so SmartScreen warns once.
"""
import os

ROOT = os.path.abspath(os.getcwd())
DESKTOP = os.path.join(ROOT, "desktop")
DATA = os.path.join(ROOT, "data")

a = Analysis(
    [os.path.join(DESKTOP, "main.py")],
    pathex=[DESKTOP, ROOT],   # desktop modules + the shared size_import package
    binaries=[],
    datas=[
        (os.path.join(DESKTOP, "app_icon.ico"), "."),
        # The snapshot ships with the app; "Refresh from Excel" writes a newer
        # one into %LOCALAPPDATA% which takes precedence at runtime.
        (os.path.join(DATA, "catalogue.csv.gz"), "data"),
        (os.path.join(DATA, "categories.json"), "data"),
    ],
    hiddenimports=["openpyxl.cell._writer"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # pyarrow is excluded on purpose: the catalogue is gzipped CSV, not parquet.
    excludes=["tkinter", "matplotlib", "sklearn", "scipy", "streamlit", "pyarrow"],
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
    name="GlassesSizeImport",
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
    icon=os.path.join(DESKTOP, "app_icon.ico"),
)
