# Glasses Size Import — desktop app

A Windows `.exe` build of the size-category import builder. Same logic as the
Streamlit app (`size_import/*`), no network, no credentials.

## Run from source

    "C:\gv\Scripts\python.exe" desktop\main.py

`C:\gv` is a venv at a short path — the Microsoft Store Python's path is long
enough that installing PySide6 fails with "enable-long-paths".

## Selftest

    "C:\gv\Scripts\python.exe" desktop\main.py --selftest

Builds both tabs headlessly and exits 0. Run it before every build. The built
.exe accepts the same flag.

## Build

    python -c "import os,shutil; os.makedirs('desktop/data', exist_ok=True); [shutil.copy(f'data/{f}', f'desktop/data/{f}') for f in ('catalogue.csv.gz','categories.json')]"
    "C:\gv\Scripts\pyinstaller.exe" desktop\GlassesSizeImport.spec

Output: `dist\GlassesSizeImport.exe`. Unsigned, so SmartScreen warns once.

## Where the data comes from

1. `%LOCALAPPDATA%\GlassesSizeImport\data` — written by 🔁 Refresh from Excel
2. otherwise the snapshot bundled in the .exe

The two files resolve independently, so refreshing only the catalogue keeps the
existing categories; the Data tab says so when the two disagree. The parsed
catalogue is cached as `catalogue.pkl` in `%LOCALAPPDATA%\GlassesSizeImport`
and reused until the CSV changes. Refresh writes to a temp file and renames, so
an interrupted refresh cannot leave a half-written snapshot behind.

Refreshing runs the same code as `python refresh_data.py`, against
`Main catalogue.xlsx` and `Glasses size category ids.xlsx`.

## Shipping an update

1. Bump `desktop/version.py`
2. Rebuild with the spec
3. Scan the .exe for `ghp_`, `github_pat`, `postgresql://`, `sk-ant`
4. Tag `desktop-v<x.y.z>` and attach the .exe to a GitHub Release

The repo is private, so the in-app update check needs a fine-grained token with
read access to Contents and Releases, pasted into ⚙️ Settings. Without one the
check says it is not configured. No token is ever baked into a build.
