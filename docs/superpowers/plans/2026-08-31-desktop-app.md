# Glasses Size Import Desktop App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Glasses Size Import Builder as a PySide6 Windows `.exe` that runs with no network and no credentials, following the house pattern of the two existing Alensa desktop tools, while the Streamlit app keeps working off the same logic modules.

**Architecture:** A new `desktop/` folder inside the existing repo. The Qt-free `size_import/*` modules stay the single source of truth for logic. `desktop/data_store.py` resolves the product snapshot (locally refreshed copy in `%LOCALAPPDATA%\GlassesSizeImport`, else the copy bundled in the .exe) and caches the parsed catalogue as a pickle. A thin Qt layer — two tabs plus a right-hand control-panel dock — sits on top, with all slow work in a `QThread` worker.

**Tech Stack:** PySide6, PyInstaller (one-file, windowed), pandas, openpyxl, pytest. Build and run from the short-path venv `C:\gv`.

**Spec:** `docs/superpowers/specs/2026-08-31-desktop-app-design.md`

**Reference implementations to port from, not re-derive:** `C:\Users\blank\Documents\GitHub\Glasses-Import-Filler\desktop\` — specifically `app_paths.py`, `theme.py`, `workers.py`, `updater.py`, `test_updater_swap.py`, `make_icon.py`, `GlassesFiller.spec`, and the shape of `main.py`.

---

## File Structure

| File | Responsibility |
|---|---|
| `refresh_data.py` (modify) | Write `catalogue.csv.gz` instead of parquet; return report dicts instead of only printing |
| `size_import/catalogue.py` (modify) | `load_catalogue` reads gzipped CSV |
| `app.py` (modify) | Point at the new filename |
| `desktop/version.py` | App name, version, release repo and tag prefix |
| `desktop/app_paths.py` | `resource_path`, `repo_root`, `cache_dir`, `is_frozen` |
| `desktop/settings.py` | `QSettings` wrapper: dark mode, update token, last-used folders |
| `desktop/theme.py` | House palette and colour constants; light/dark switch |
| `desktop/workers.py` | `Worker(QThread)` with `done` / `failed` / `progress` |
| `desktop/data_store.py` | Snapshot resolution, pickle cache, refresh-from-Excel |
| `desktop/dimension_panel.py` | The six mm fields with live category resolution (dock widget) |
| `desktop/tabs/base.py` | Tab contract: `TITLE`, `on_snapshot`, `control_panel` |
| `desktop/tabs/build_tab.py` | Search, product selection, basket table |
| `desktop/tabs/data_tab.py` | Snapshot state and the last refresh report |
| `desktop/updater.py` | GitHub Releases check and PowerShell swap |
| `desktop/settings_dialog.py` | ⚙️ Settings: update token |
| `desktop/main.py` | Window, toolbar, dock routing, dark mode, `--selftest` |
| `desktop/make_icon.py` | Generates `app_icon.ico` |
| `desktop/GlassesSizeImport.spec` | PyInstaller spec |
| `desktop/requirements.txt` | PySide6 + the web app's deps |
| `desktop/test_data_store.py` | Snapshot precedence, pickle cache, refresh |
| `desktop/test_app_paths.py` | Cache directory resolution |
| `desktop/test_updater_swap.py` | Ported swap test |
| `HANDOVER_DESKTOP.md` | How to run, refresh, build, ship |

Desktop modules import each other flat (`import theme`), matching the filler. Every `desktop/test_*.py` starts with the same three-line `sys.path` bootstrap shown in Task 3.

---

### Task 1: Switch the data format from parquet to gzipped CSV

Parquet needs pyarrow: about 40 MB in the .exe plus hidden-import trouble. The filler avoided it for exactly this reason.

**Files:**
- Modify: `refresh_data.py`
- Modify: `size_import/catalogue.py`
- Modify: `app.py`
- Test: `tests/test_catalogue.py`

- [ ] **Step 1: Update the end-to-end test to use gzipped CSV**

In `tests/test_catalogue.py`, find the test that writes a parquet file under `tmp_path` (it calls `to_parquet`) and replace that whole test function with these two:

```python
def test_load_catalogue_reads_gzipped_csv(tmp_path):
    path = tmp_path / "catalogue.csv.gz"
    CATALOGUE.to_csv(path, index=False, compression="gzip", encoding="utf-8")

    frame = load_catalogue(path)

    assert list(frame["globalId"]) == [1588262, 245001, 245002, 14]
    assert frame["globalId"].dtype.kind == "i"
    assert list(search(frame, "crulle")["globalId"]) == [1588262]


def test_load_catalogue_survives_commas_and_quotes_in_names(tmp_path):
    path = tmp_path / "catalogue.csv.gz"
    pd.DataFrame(
        {"name": ['Brand "Special", limited', "Plain Name"], "globalId": [1, 2]}
    ).to_csv(path, index=False, compression="gzip", encoding="utf-8")

    frame = load_catalogue(path)

    assert frame.loc[0, "name"] == 'Brand "Special", limited'
    assert list(search(frame, "limited")["globalId"]) == [1]
```

Make sure `load_catalogue` is imported at the top of the file alongside `normalize` and `search`.

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `python -m pytest tests/test_catalogue.py -v`
Expected: FAIL — the parquet reader chokes on a CSV (an `ArrowInvalid`/`OSError`-style error), because `load_catalogue` still calls `pd.read_parquet`.

- [ ] **Step 3: Make `load_catalogue` read gzipped CSV**

In `size_import/catalogue.py`, replace the body of `load_catalogue` with:

```python
def load_catalogue(path):
    """Read catalogue.csv.gz and attach the precomputed search key column.

    Gzipped CSV rather than parquet on purpose: parquet drags pyarrow (~40 MB)
    into the desktop .exe for no gain, since the desktop app caches the parsed
    frame as a pickle anyway.
    """
    frame = pd.read_csv(path, compression="gzip", encoding="utf-8")
    frame["globalId"] = frame["globalId"].astype("int64")
    frame["search_key"] = frame["name"].map(normalize)
    return frame
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_catalogue.py -v`
Expected: PASS, 11 passed

- [ ] **Step 5: Write the gzipped CSV in `refresh_data.py`**

In `refresh_data.py`, inside `refresh_catalogue`, replace the parquet write with:

```python
    frame = pd.DataFrame(records, columns=["name", "globalId"])
    frame.to_csv(destination, index=False, compression="gzip", encoding="utf-8")
```

and in `main()` change the destination filename:

```python
    refresh_catalogue(args.catalogue, DATA_DIR / "catalogue.csv.gz")
```

- [ ] **Step 6: Point the Streamlit app at the new file**

In `app.py`, change `get_catalogue` to:

```python
@st.cache_data
def get_catalogue():
    return load_catalogue(DATA_DIR / "catalogue.csv.gz")
```

- [ ] **Step 7: Regenerate the data and drop the parquet**

Run: `python refresh_data.py`
Expected: the same counts as always — `82690 products`, `3 rows skipped`, `648 rows read`, `187 duplicates collapsed`, `6 rows dropped`, `455 usable categories`. If any number differs, STOP and report it.

Then remove the old file and check the new one's size:

```bash
git rm --cached data/catalogue.parquet
rm data/catalogue.parquet
python -c "import os; print(round(os.path.getsize('data/catalogue.csv.gz')/1e6, 2), 'MB')"
```

Expected: roughly 1.0-1.5 MB. Over 20 MB means something is wrong — stop and report.

- [ ] **Step 8: Run everything and commit**

Run: `python -m pytest -q`
Expected: PASS, 45 passed

```bash
git add -A
git commit -m "refactor: store the catalogue as gzipped CSV so the desktop build needs no pyarrow"
```

---

### Task 2: Desktop scaffold — paths, settings, theme, worker

Straight ports from the filler, with names and colours unchanged, so the two apps stay one family.

**Files:**
- Create: `desktop/version.py`, `desktop/app_paths.py`, `desktop/settings.py`, `desktop/theme.py`, `desktop/workers.py`, `desktop/requirements.txt`
- Test: `desktop/test_app_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# desktop/test_app_paths.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app_paths  # noqa: E402


def test_cache_dir_lives_under_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    path = app_paths.cache_dir()

    assert path == os.path.join(str(tmp_path), "GlassesSizeImport")
    assert os.path.isdir(path)


def test_cache_dir_accepts_subfolders(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    path = app_paths.cache_dir("data")

    assert path.endswith(os.path.join("GlassesSizeImport", "data"))
    assert os.path.isdir(path)


def test_resource_path_points_next_to_the_source_when_not_frozen():
    here = os.path.dirname(os.path.abspath(app_paths.__file__))

    assert app_paths.resource_path("app_icon.ico") == os.path.join(here, "app_icon.ico")


def test_repo_root_is_the_parent_of_the_desktop_folder():
    here = os.path.dirname(os.path.abspath(app_paths.__file__))

    assert app_paths.repo_root() == os.path.dirname(here)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest desktop/test_app_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app_paths'`

- [ ] **Step 3: Write `desktop/version.py`**

```python
# -*- coding: utf-8 -*-
"""Single source of truth for the desktop app version.

Bump this, tag the repo `desktop-v<x.y.z>` and attach the built .exe to the
GitHub Release — installed copies compare against the latest tag and offer to
self-update. The repo is private, so the check needs a token in Settings.
"""

APP_NAME = "Glasses Size Import"
ORG_NAME = "Alensa"
__version__ = "1.0.0"

RELEASE_REPO = "bgal-png/Glasses-Size-Import-Categories"
RELEASE_TAG_PREFIX = "desktop-v"
```

- [ ] **Step 4: Write `desktop/app_paths.py`**

```python
# -*- coding: utf-8 -*-
"""Filesystem locations, PyInstaller-aware.

Bundled data files are located via sys._MEIPASS when frozen; the locally
refreshed snapshot lives in %LOCALAPPDATA%\\GlassesSizeImport so it survives
.exe replacement (self-update).
"""
from __future__ import annotations

import os
import sys

from version import APP_NAME


def _slug(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum()) or "App"


def resource_path(*parts: str) -> str:
    """Path to a file bundled with the app (spec `datas`), or alongside the
    source when running from a checkout."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def repo_root() -> str:
    """Repo root, so `size_import` and `refresh_data` import when running from
    source."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cache_dir(*parts: str) -> str:
    """%LOCALAPPDATA%\\GlassesSizeImport[\\parts] — created if missing."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, _slug(APP_NAME), *parts)
    os.makedirs(path, exist_ok=True)
    return path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest desktop/test_app_paths.py -v`
Expected: PASS, 4 passed

- [ ] **Step 6: Write `desktop/settings.py`**

```python
# -*- coding: utf-8 -*-
"""Persisted user settings (QSettings → Windows registry, per user).

Credentials policy: no token is ever baked into a build. `update_token` is a
fine-grained PAT with read access to this private repo's Releases, pasted by
the user in ⚙️ Settings; without it the update check simply reports that it is
not configured.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

from version import APP_NAME, ORG_NAME


class Settings:
    def __init__(self) -> None:
        self._s = QSettings(ORG_NAME, APP_NAME)

    @property
    def dark_mode(self) -> bool:
        return str(self._s.value("dark_mode", "false")).lower() in ("1", "true", "yes")

    @dark_mode.setter
    def dark_mode(self, value: bool) -> None:
        self._s.setValue("dark_mode", bool(value))

    @property
    def update_token(self) -> str:
        return str(self._s.value("update_token", "")).strip()

    @update_token.setter
    def update_token(self, value: str) -> None:
        self._s.setValue("update_token", (value or "").strip())

    @property
    def last_refresh_report(self) -> str:
        """JSON of the last refresh report, shown on the Data tab."""
        return str(self._s.value("last_refresh_report", "")).strip()

    @last_refresh_report.setter
    def last_refresh_report(self, value: str) -> None:
        self._s.setValue("last_refresh_report", value or "")

    def last_dir(self, key: str) -> str:
        return str(self._s.value(f"last_dir/{key}", "")).strip()

    def set_last_dir(self, key: str, path: str) -> None:
        self._s.setValue(f"last_dir/{key}", path or "")
```

- [ ] **Step 7: Copy `theme.py` and `workers.py` from the filler unchanged**

Copy these two files verbatim — the colours are fixed by the family convention and the worker contract is what every tab expects:

```bash
cp "/c/Users/blank/Documents/GitHub/Glasses-Import-Filler/desktop/theme.py" desktop/theme.py
cp "/c/Users/blank/Documents/GitHub/Glasses-Import-Filler/desktop/workers.py" desktop/workers.py
```

Verify both import cleanly:

Run: `python -c "import sys; sys.path.insert(0,'desktop'); import theme, workers; print(theme.COLOR_ERROR, theme.STATUS_READY)"`
Expected: `#ffb3b3 #1a7f37`

- [ ] **Step 8: Write `desktop/requirements.txt`**

```
PySide6>=6.6
pandas>=2.0
openpyxl>=3.1
```

- [ ] **Step 9: Commit**

```bash
git add desktop/version.py desktop/app_paths.py desktop/settings.py desktop/theme.py desktop/workers.py desktop/requirements.txt desktop/test_app_paths.py
git commit -m "feat: desktop scaffold - paths, settings, theme, worker"
```

---

### Task 3: Snapshot store

The heart of the desktop app: where data comes from, how it is cached, and how the user refreshes it.

**Files:**
- Modify: `refresh_data.py` (return reports instead of only printing)
- Create: `desktop/data_store.py`
- Test: `desktop/test_data_store.py`

- [ ] **Step 1: Make the refresh functions return their reports**

`refresh_data.py` currently prints and returns `None`; the desktop needs the numbers. Change both functions to build a report, print from it, and return it. Replace the two functions with:

```python
def refresh_catalogue(source, destination):
    """Extract name + globalId into a gzipped CSV. Returns a report dict."""
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]

    records = []
    skipped = 0
    for row in sheet.iter_rows(min_row=2, values_only=True):
        name = row[NAME_COLUMN]
        global_id = row[GLOBAL_ID_COLUMN]
        if global_id is None or name is None:
            skipped += 1
            continue
        records.append((str(name).strip(), int(global_id)))

    frame = pd.DataFrame(records, columns=["name", "globalId"])
    frame.to_csv(destination, index=False, compression="gzip", encoding="utf-8")

    report = {"products": len(frame), "skipped": skipped, "destination": str(destination)}
    print(f"catalogue: {report['products']} products -> {destination}")
    print(f"catalogue: {report['skipped']} rows skipped (no name or no globalId)")
    return report


def refresh_categories(source, destination):
    """Build the deduped category lookup as JSON. Returns a report dict."""
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]

    rows = [row[:3] for row in sheet.iter_rows(min_row=2, values_only=True) if row[0]]
    lookup, report = build_lookup(rows)

    destination.write_text(
        json.dumps(to_json_dict(lookup), indent=1, sort_keys=True), encoding="utf-8"
    )

    report = {
        "rows": len(rows),
        "collapsed": report["collapsed"],
        "dropped": report["dropped"],
        "kept": report["kept"],
        "destination": str(destination),
    }
    print(f"categories: {report['rows']} rows read")
    print(f"categories: {report['collapsed']} duplicates collapsed (lowest ID kept)")
    print(f"categories: {len(report['dropped'])} rows dropped:")
    for category_id, name, value in report["dropped"]:
        print(f"  - id={category_id} name={name!r} value={value!r}")
    print(f"categories: {report['kept']} usable categories -> {destination}")
    return report
```

Note `destination.write_text` requires a `Path`; `data_store` will always pass one.

- [ ] **Step 2: Write the failing tests**

```python
# desktop/test_data_store.py
import json
import os
import sys

import openpyxl
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data_store  # noqa: E402

CATALOGUE = pd.DataFrame({"name": ["Crulle G5063 C3", "Ray-Ban Justin"], "globalId": [1588262, 245001]})
CATEGORIES = {"lens_width": {"55": 4156}, "bridge": {"15": 4157}}


def _write_snapshot(folder, frame=CATALOGUE, categories=None):
    folder.mkdir(parents=True, exist_ok=True)
    frame.to_csv(folder / "catalogue.csv.gz", index=False, compression="gzip", encoding="utf-8")
    (folder / "categories.json").write_text(
        json.dumps(categories or CATEGORIES), encoding="utf-8"
    )
    return folder


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """Isolate both snapshot locations under tmp_path."""
    local = tmp_path / "local" / "data"
    bundled = tmp_path / "bundled"
    bundled.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(data_store, "local_data_dir", lambda: str(local))
    monkeypatch.setattr(data_store, "bundled_data_dir", lambda: str(bundled))
    return local, bundled


def test_bundled_snapshot_is_used_when_there_is_no_local_one(dirs):
    local, bundled = dirs
    _write_snapshot(bundled)

    snapshot = data_store.load_snapshot()

    assert snapshot.source == "bundled"
    assert list(snapshot.catalogue["globalId"]) == [1588262, 245001]
    assert snapshot.lookup["lens_width"][55] == 4156


def test_local_snapshot_wins_over_the_bundled_one(dirs):
    local, bundled = dirs
    _write_snapshot(bundled)
    _write_snapshot(
        local,
        frame=pd.DataFrame({"name": ["Fresher Product"], "globalId": [999]}),
        categories={"bridge": {"14": 4169}},
    )

    snapshot = data_store.load_snapshot()

    assert snapshot.source == "local"
    assert list(snapshot.catalogue["globalId"]) == [999]
    assert snapshot.lookup["bridge"][14] == 4169


def test_missing_snapshot_raises_a_clear_error(dirs):
    with pytest.raises(FileNotFoundError) as excinfo:
        data_store.load_snapshot()

    assert "catalogue.csv.gz" in str(excinfo.value)


def test_parsed_catalogue_is_cached_and_reused(dirs, monkeypatch):
    local, bundled = dirs
    _write_snapshot(bundled)
    calls = []
    real_load = data_store.load_catalogue

    def counting_load(path):
        calls.append(path)
        return real_load(path)

    monkeypatch.setattr(data_store, "load_catalogue", counting_load)

    data_store.load_snapshot()
    data_store.load_snapshot()

    assert len(calls) == 1, "second load should come from the pickle cache"


def test_cache_is_rebuilt_when_the_snapshot_changes(dirs, monkeypatch):
    local, bundled = dirs
    _write_snapshot(bundled)
    calls = []
    real_load = data_store.load_catalogue
    monkeypatch.setattr(
        data_store, "load_catalogue", lambda path: (calls.append(path), real_load(path))[1]
    )

    data_store.load_snapshot()
    _write_snapshot(bundled, frame=pd.DataFrame({"name": ["Changed"], "globalId": [7]}))
    snapshot = data_store.load_snapshot()

    assert len(calls) == 2
    assert list(snapshot.catalogue["globalId"]) == [7]


def _catalogue_workbook(path):
    """A 104-column workbook shaped like the real Main catalogue export."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    header = ["col"] * 104
    header[2] = "name"
    header[103] = "globalId"
    sheet.append(header)
    for name, global_id in (("Product One", 111), ("Product Two", 222), (None, 333)):
        row = ["decoy"] * 104
        row[2] = name
        row[103] = global_id
        sheet.append(row)
    workbook.save(path)


def _categories_workbook(path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["ID", "Global category name", "Value"])
    sheet.append([4156, "Glasses size: lens width", 55])
    sheet.append([7440, "Glasses size: lens width", 55])
    sheet.append([4602, "Glasses size: bridge", None])
    workbook.save(path)


def test_refresh_from_excel_writes_a_local_snapshot_and_reports_counts(dirs, tmp_path):
    local, bundled = dirs
    catalogue_xlsx = tmp_path / "Main catalogue.xlsx"
    categories_xlsx = tmp_path / "Glasses size category ids.xlsx"
    _catalogue_workbook(catalogue_xlsx)
    _categories_workbook(categories_xlsx)

    report = data_store.refresh_from_excel(str(catalogue_xlsx), str(categories_xlsx))

    assert report["catalogue"]["products"] == 2
    assert report["catalogue"]["skipped"] == 1
    assert report["categories"]["kept"] == 1
    assert report["categories"]["collapsed"] == 1
    assert [row[0] for row in report["categories"]["dropped"]] == [4602]
    assert os.path.exists(os.path.join(local, "catalogue.csv.gz"))

    snapshot = data_store.load_snapshot()
    assert snapshot.source == "local"
    assert snapshot.lookup["lens_width"][55] == 4156


def test_refresh_can_update_the_catalogue_alone(dirs, tmp_path):
    local, bundled = dirs
    _write_snapshot(bundled)
    catalogue_xlsx = tmp_path / "Main catalogue.xlsx"
    _catalogue_workbook(catalogue_xlsx)

    report = data_store.refresh_from_excel(str(catalogue_xlsx), None)

    assert report["categories"] is None
    snapshot = data_store.load_snapshot()
    assert list(snapshot.catalogue["globalId"]) == [111, 222]
    assert snapshot.lookup["lens_width"][55] == 4156, "categories fall back to the bundled copy"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest desktop/test_data_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_store'`

- [ ] **Step 4: Write `desktop/data_store.py`**

```python
# -*- coding: utf-8 -*-
"""Where the product snapshot comes from, and how it gets refreshed.

Resolution order, per file:
  1. %LOCALAPPDATA%\\GlassesSizeImport\\data — a snapshot the user refreshed
  2. the snapshot bundled in the .exe (spec `datas`)

The two files resolve independently, so refreshing only the catalogue keeps the
bundled categories. Parsing the 82,690-row CSV is the slow part, so the parsed
frame is pickled next to it and reused until the CSV changes.

Nothing here touches the network: the desktop app has no startup fetch, and so
no background thread that could outlive the process.
"""
from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass
from datetime import datetime

from app_paths import cache_dir, resource_path
from size_import.catalogue import load_catalogue
from size_import.categories import from_json_dict

CATALOGUE_FILE = "catalogue.csv.gz"
CATEGORIES_FILE = "categories.json"
CACHE_FILE = "catalogue.pkl"


@dataclass
class Snapshot:
    catalogue: object          # DataFrame: name, globalId, search_key
    lookup: dict               # {dimension key: {mm value: category ID}}
    source: str                # "local" or "bundled"
    catalogue_path: str
    categories_path: str
    updated_at: datetime       # mtime of the catalogue file


def local_data_dir() -> str:
    return cache_dir("data")


def bundled_data_dir() -> str:
    return resource_path("data")


def _resolve(filename: str) -> tuple[str, str]:
    """(path, source) for one snapshot file. Raises if neither copy exists."""
    local = os.path.join(local_data_dir(), filename)
    if os.path.exists(local):
        return local, "local"
    bundled = os.path.join(bundled_data_dir(), filename)
    if os.path.exists(bundled):
        return bundled, "bundled"
    raise FileNotFoundError(
        f"No {filename} found. Use 'Refresh from Excel' to build one from "
        f"Main catalogue.xlsx."
    )


def _cache_key(path: str) -> tuple:
    stat = os.stat(path)
    return (int(stat.st_mtime), stat.st_size)


def _load_catalogue_cached(path: str):
    """Parse the CSV, or reuse the pickle when the CSV has not changed."""
    cache_path = os.path.join(cache_dir(), CACHE_FILE)
    key = _cache_key(path)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as handle:
                cached = pickle.load(handle)
            if cached.get("key") == key and cached.get("path") == path:
                return cached["frame"]
        except Exception:
            pass  # a corrupt cache is not worth a crash; reparse instead

    frame = load_catalogue(path)
    temporary = cache_path + ".tmp"
    try:
        with open(temporary, "wb") as handle:
            pickle.dump(
                {"key": key, "path": path, "frame": frame},
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        os.replace(temporary, cache_path)
    except Exception:
        pass  # caching is an optimisation, never a requirement
    return frame


def load_snapshot() -> Snapshot:
    catalogue_path, catalogue_source = _resolve(CATALOGUE_FILE)
    categories_path, categories_source = _resolve(CATEGORIES_FILE)

    frame = _load_catalogue_cached(catalogue_path)
    lookup = from_json_dict(json.loads(open(categories_path, encoding="utf-8").read()))

    source = "local" if "local" in (catalogue_source, categories_source) else "bundled"
    return Snapshot(
        catalogue=frame,
        lookup=lookup,
        source=source,
        catalogue_path=catalogue_path,
        categories_path=categories_path,
        updated_at=datetime.fromtimestamp(os.path.getmtime(catalogue_path)),
    )


def refresh_from_excel(catalogue_xlsx: str | None, categories_xlsx: str | None,
                       progress=None) -> dict:
    """Re-prep the snapshot from the source workbooks into %LOCALAPPDATA%.

    Either workbook may be None: they go stale independently, so refreshing one
    leaves the other in place. Returns
    {"catalogue": report | None, "categories": report | None}.
    """
    from pathlib import Path

    import refresh_data

    target = Path(local_data_dir())
    target.mkdir(parents=True, exist_ok=True)
    result = {"catalogue": None, "categories": None}

    if catalogue_xlsx:
        if progress:
            progress(0.1, "Reading the catalogue workbook…")
        result["catalogue"] = refresh_data.refresh_catalogue(
            catalogue_xlsx, target / CATALOGUE_FILE
        )
    if categories_xlsx:
        if progress:
            progress(0.8, "Reading the category workbook…")
        result["categories"] = refresh_data.refresh_categories(
            categories_xlsx, target / CATEGORIES_FILE
        )
    if progress:
        progress(1.0, "Done")
    return result
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest desktop/test_data_store.py -v`
Expected: PASS, 7 passed

- [ ] **Step 6: Run everything and commit**

Run: `python -m pytest -q`
Expected: PASS, 56 passed

```bash
git add refresh_data.py desktop/data_store.py desktop/test_data_store.py
git commit -m "feat: snapshot store with local-over-bundled resolution and a parsed cache"
```

---

### Task 4: Dimension panel (the dock widget)

**Files:**
- Create: `desktop/dimension_panel.py`

This is UI, so it is verified by the selftest in Task 6 rather than by unit tests.

- [ ] **Step 1: Write `desktop/dimension_panel.py`**

```python
# -*- coding: utf-8 -*-
"""The six millimetre fields, shown in the right-hand 'Control panel' dock.

Each field resolves live to its global category ID, or says plainly that no
category exists for that value — the same feedback the web version gives, in
the house colours.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

import theme
from size_import.categories import DIMENSIONS, resolve

MAX_MM = 300


class DimensionPanel(QWidget):
    """Emits `add_requested` when the user commits the entered values."""

    add_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lookup = {}
        self._spins = {}
        self._notes = {}
        self._product_selected = False

        layout = QVBoxLayout(self)
        box = QGroupBox("Dimensions (mm)")
        box_layout = QVBoxLayout(box)

        for dimension in DIMENSIONS:
            spin = QSpinBox()
            spin.setRange(0, MAX_MM)
            spin.setSpecialValueText(" ")   # 0 reads as empty, never as a value
            spin.valueChanged.connect(self._refresh_notes)
            note = QLabel("")
            note.setWordWrap(True)

            box_layout.addWidget(QLabel(dimension.label))
            box_layout.addWidget(spin)
            box_layout.addWidget(note)

            self._spins[dimension.key] = spin
            self._notes[dimension.key] = note

        layout.addWidget(box)

        self.add_button = QPushButton("Add to basket")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self.add_requested)
        layout.addWidget(self.add_button)

        self.hint = QLabel("Pick a product first.")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addStretch(1)

    # --- state in ---
    def set_lookup(self, lookup: dict) -> None:
        self._lookup = lookup or {}
        self._refresh_notes()

    def set_product_selected(self, selected: bool) -> None:
        self._product_selected = selected
        self._refresh_notes()

    # --- state out ---
    def values(self) -> dict:
        """{dimension key: mm} for every field the user actually filled.

        0 means "not entered": no dimension has a category for 0 (the minimums
        are bridge 1, temple 1, lens height 4, to-bend 10, lens width 14,
        glasses width 45), so treating it as blank is safe.
        """
        return {key: spin.value() for key, spin in self._spins.items() if spin.value()}

    def clear(self) -> None:
        for spin in self._spins.values():
            spin.blockSignals(True)
            spin.setValue(0)
            spin.blockSignals(False)
        self._refresh_notes()

    # --- live feedback ---
    def _refresh_notes(self) -> None:
        for dimension in DIMENSIONS:
            spin = self._spins[dimension.key]
            note = self._notes[dimension.key]
            value = spin.value()
            if not value:
                note.setText("")
                note.setStyleSheet("")
                continue
            category_id = resolve(self._lookup, dimension.key, value)
            if category_id is None:
                note.setText(f"No category for {value} — will be skipped")
                note.setStyleSheet(
                    f"background-color: {theme.COLOR_ERROR};"
                    f"color: {theme.COLOR_FORCED_TEXT}; padding: 2px 4px; border-radius: 3px;"
                )
            else:
                note.setText(f"category {category_id}")
                note.setStyleSheet(f"color: {theme.STATUS_READY};")

        selected = getattr(self, "_product_selected", False)
        has_values = bool(self.values())
        self.add_button.setEnabled(selected and has_values)
        if not selected:
            self.hint.setText("Pick a product first.")
        elif not has_values:
            self.hint.setText("Enter at least one dimension.")
        else:
            self.hint.setText("")
```

- [ ] **Step 2: Verify it constructs headlessly**

Run:

```bash
QT_QPA_PLATFORM=offscreen "C:/gv/Scripts/python.exe" -c "import sys; sys.path[:0]=['desktop','.']; from PySide6.QtWidgets import QApplication; app=QApplication([]); import dimension_panel as d; p=d.DimensionPanel(); p.set_lookup({'lens_width':{55:4156}}); p._spins['lens_width'].setValue(55); print(p.values(), p._notes['lens_width'].text()); p._spins['bridge'].setValue(99); print(p._notes['bridge'].text())"
```

Expected: `{'lens_width': 55} category 4156` then `No category for 99 — will be skipped`

- [ ] **Step 3: Commit**

```bash
git add desktop/dimension_panel.py
git commit -m "feat: dimension panel with live category resolution"
```

---

### Task 5: Tabs

**Files:**
- Create: `desktop/tabs/__init__.py`, `desktop/tabs/base.py`, `desktop/tabs/build_tab.py`, `desktop/tabs/data_tab.py`

- [ ] **Step 1: Write `desktop/tabs/base.py`**

```python
# -*- coding: utf-8 -*-
"""Common contract for every tab.

Tabs are plain QWidgets. The main window owns the toolbar and the right dock;
it asks the current tab for its control panel and hides the dock entirely on
tabs that return None.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class BaseTab(QWidget):
    TITLE = "Tab"

    status_message = Signal(str)
    busy = Signal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.snapshot = None

    def set_snapshot(self, snapshot) -> None:
        self.snapshot = snapshot
        self.on_snapshot(snapshot)

    def on_snapshot(self, snapshot) -> None:
        """Called whenever a snapshot is loaded or refreshed."""

    def control_panel(self) -> QWidget | None:
        return None

    def has_unsaved_changes(self) -> bool:
        return False
```

- [ ] **Step 2: Write `desktop/tabs/build_tab.py`**

```python
# -*- coding: utf-8 -*-
"""Build import — search a product, collect a basket, export the import file."""
from __future__ import annotations

import datetime
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from dimension_panel import DimensionPanel
from size_import import basket as basket_module
from size_import.catalogue import search
from size_import.categories import DIMENSIONS
from size_import.export import export_filename, to_bytes
from tabs.base import BaseTab

SEARCH_LIMIT = 50
COLUMNS = ["Product", "Global ID", "Sizes", "Category IDs"]


class BuildTab(BaseTab):
    TITLE = "🧱 Build import"

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.basket = {}
        self._selected_id = None
        self._selected_name = None

        self.panel = DimensionPanel()
        self.panel.add_requested.connect(self.add_to_basket)

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by name, e.g. crulle g5063")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        self.results = QListWidget()
        self.results.setMaximumHeight(180)
        self.results.currentItemChanged.connect(self._on_pick)
        layout.addWidget(self.results)

        self.selected_label = QLabel("No product selected.")
        self.selected_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.selected_label)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        # Qt table headers are not selectable text, so offer copying explicitly.
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        layout.addWidget(self.table, 1)

    # --- snapshot ---
    def on_snapshot(self, snapshot) -> None:
        self.panel.set_lookup(snapshot.lookup if snapshot else {})
        self._on_search(self.search_box.text())
        self._render_basket()

    def control_panel(self):
        return self.panel

    # --- search ---
    def _on_search(self, text: str) -> None:
        self.results.clear()
        if not self.snapshot or not text.strip():
            return
        matches = search(self.snapshot.catalogue, text, limit=SEARCH_LIMIT)
        for row in matches.itertuples(index=False):
            # row.name / row.globalId rely on the column names written by
            # refresh_data.py and read by size_import/catalogue.py.
            item = QListWidgetItem(f"{row.name}  —  {row.globalId}")
            item.setData(Qt.UserRole, (int(row.globalId), str(row.name)))
            self.results.addItem(item)
        if self.results.count() == SEARCH_LIMIT:
            self.status_message.emit(
                f"Showing the first {SEARCH_LIMIT} matches — refine the search if needed."
            )

    def _on_pick(self, current, _previous) -> None:
        if current is None:
            self._selected_id = None
            self._selected_name = None
            self.selected_label.setText("No product selected.")
            self.panel.set_product_selected(False)
            return
        self._selected_id, self._selected_name = current.data(Qt.UserRole)
        self.selected_label.setText(
            f"Selected: {self._selected_name}   ·   Global ID {self._selected_id}"
        )
        self.panel.set_product_selected(True)

    # --- basket ---
    def add_to_basket(self) -> None:
        values = self.panel.values()
        if self._selected_id is None or not values:
            return
        self.basket = basket_module.add(
            self.basket, self._selected_id, self._selected_name, values
        )
        self.panel.clear()
        self._render_basket()
        self.status_message.emit(f"Added {self._selected_name}.")

    def _render_basket(self) -> None:
        lookup = self.snapshot.lookup if self.snapshot else {}
        self.table.setRowCount(0)
        for global_id, entry in self.basket.items():
            ids = basket_module.category_ids(entry, lookup)
            sizes = " | ".join(
                ", ".join(
                    f"{dimension.label} {value_set[dimension.key]}"
                    for dimension in DIMENSIONS
                    if dimension.key in value_set
                )
                for value_set in entry["value_sets"]
            )
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, text in enumerate(
                [entry["name"], str(global_id), sizes, ";".join(str(i) for i in ids)]
            ):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, global_id)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def selected_global_ids(self) -> list:
        rows = {index.row() for index in self.table.selectedIndexes()}
        return [int(self.table.item(row, 1).text()) for row in sorted(rows)]

    def remove_selected(self) -> None:
        ids = self.selected_global_ids()
        if not ids:
            self.status_message.emit("Select a basket row first.")
            return
        answer = QMessageBox.question(
            self, "Remove", f"Remove {len(ids)} product(s) from the basket?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        for global_id in ids:
            self.basket = basket_module.remove(self.basket, global_id)
        self._render_basket()

    def clear_basket(self) -> None:
        if not self.basket:
            return
        answer = QMessageBox.question(
            self, "Clear basket", f"Clear all {len(self.basket)} product(s)?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.basket = {}
        self._render_basket()

    # --- copying ---
    def _table_menu(self, point) -> None:
        menu = QMenu(self)
        menu.addAction("Copy selected rows", self._copy_selected)
        menu.addAction("Copy whole table (TSV)", self._copy_all)
        menu.exec(self.table.viewport().mapToGlobal(point))

    def _copy_selected(self) -> None:
        self._copy_rows(sorted({index.row() for index in self.table.selectedIndexes()}))

    def _copy_all(self) -> None:
        self._copy_rows(range(self.table.rowCount()))

    def _copy_rows(self, rows) -> None:
        lines = ["	".join(COLUMNS)]
        for row in rows:
            lines.append(
                "	".join(
                    self.table.item(row, column).text() for column in range(len(COLUMNS))
                )
            )
        QApplication.clipboard().setText("
".join(lines))
        self.status_message.emit("Copied — paste straight into Excel.")

    # --- export ---
    def export(self) -> None:
        lookup = self.snapshot.lookup if self.snapshot else {}
        rows = basket_module.export_rows(self.basket, lookup)
        if not rows:
            QMessageBox.information(
                self, "Nothing to export",
                "The basket has no product with a resolvable category yet.",
            )
            return

        suggested = os.path.join(
            self.settings.last_dir("export") or os.path.expanduser("~"),
            export_filename(datetime.date.today()),
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save import file", suggested, "Excel files (*.xlsx)"
        )
        if not path:
            return
        with open(path, "wb") as handle:
            handle.write(to_bytes(rows))
        self.settings.set_last_dir("export", os.path.dirname(path))
        self.status_message.emit(f"Exported {len(rows)} product(s) to {path}")
        QMessageBox.information(
            self, "Exported", f"{len(rows)} product(s) written to:\n{path}"
        )

    def has_unsaved_changes(self) -> bool:
        return bool(self.basket)
```

- [ ] **Step 3: Write `desktop/tabs/data_tab.py`**

```python
# -*- coding: utf-8 -*-
"""Data — which snapshot is loaded, how old it is, and what the last refresh
dropped. Empty or surprising results must explain themselves, so the six junk
category rows stay visible rather than being summarised away.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout

import theme
from tabs.base import BaseTab


class DataTab(BaseTab):
    TITLE = "🗄 Data"

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        layout = QVBoxLayout(self)

        self.status = QLabel("No snapshot loaded.")
        self.status.setStyleSheet(theme.status_style("loading"))
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

        self.details = QLabel("")
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details.setWordWrap(True)
        layout.addWidget(self.details)

        layout.addWidget(QLabel("Last refresh report"))
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 1)

        self._render_report()

    def on_snapshot(self, snapshot) -> None:
        if snapshot is None:
            self.status.setText("No snapshot loaded.")
            self.status.setStyleSheet(theme.status_style("error"))
            return
        origin = "refreshed locally" if snapshot.source == "local" else "bundled with the app"
        self.status.setText(
            f"Snapshot ready — {origin}, {len(snapshot.catalogue):,} products, "
            f"{sum(len(v) for v in snapshot.lookup.values())} categories"
        )
        self.status.setStyleSheet(theme.status_style("ready"))
        self.details.setText(
            f"Catalogue: {snapshot.catalogue_path}\n"
            f"Categories: {snapshot.categories_path}\n"
            f"Updated: {snapshot.updated_at:%Y-%m-%d %H:%M}"
        )
        self._render_report()

    def show_report(self, report: dict) -> None:
        self.settings.last_refresh_report = json.dumps(report, default=str)
        self._render_report()

    def _render_report(self) -> None:
        raw = self.settings.last_refresh_report
        if not raw:
            self.report.setPlainText(
                "No refresh run on this machine yet — the bundled snapshot is in use.\n"
                "Use 🔁 Refresh from Excel after re-exporting Main catalogue.xlsx."
            )
            return
        try:
            report = json.loads(raw)
        except ValueError:
            self.report.setPlainText(raw)
            return

        lines = []
        catalogue = report.get("catalogue")
        if catalogue:
            lines.append(f"catalogue: {catalogue['products']} products")
            lines.append(f"catalogue: {catalogue['skipped']} rows skipped (no name or no globalId)")
        categories = report.get("categories")
        if categories:
            lines.append(f"categories: {categories['rows']} rows read")
            lines.append(
                f"categories: {categories['collapsed']} duplicates collapsed (lowest ID kept)"
            )
            lines.append(f"categories: {len(categories['dropped'])} rows dropped:")
            for row in categories["dropped"]:
                lines.append(f"  - id={row[0]} name={row[1]!r} value={row[2]!r}")
            lines.append(f"categories: {categories['kept']} usable categories")
        self.report.setPlainText("\n".join(lines) or "Nothing recorded.")
```

- [ ] **Step 4: Write `desktop/tabs/__init__.py`**

```python
# -*- coding: utf-8 -*-
"""Tab registry — order here is the order in the QTabWidget."""
from tabs.build_tab import BuildTab
from tabs.data_tab import DataTab

ALL_TABS = [BuildTab, DataTab]
```

- [ ] **Step 5: Verify both tabs construct headlessly**

Run:

```bash
QT_QPA_PLATFORM=offscreen "C:/gv/Scripts/python.exe" -c "import sys; sys.path[:0]=['desktop','.']; from PySide6.QtWidgets import QApplication; app=QApplication([]); from settings import Settings; from tabs import ALL_TABS; ts=[c(Settings()) for c in ALL_TABS]; print([t.TITLE for t in ts]); print('dock:', [t.control_panel() is not None for t in ts])"
```

Expected: the two titles, then `dock: [True, False]`

- [ ] **Step 6: Commit**

```bash
git add desktop/tabs
git commit -m "feat: build and data tabs"
```

---

### Task 6: Main window and selftest

**Files:**
- Create: `desktop/main.py`

- [ ] **Step 1: Write `desktop/main.py`**

```python
# -*- coding: utf-8 -*-
"""Glasses Size Import — desktop entry point.

Run from source:   "C:\\gv\\Scripts\\python.exe" desktop\\main.py
Selftest:          "C:\\gv\\Scripts\\python.exe" desktop\\main.py --selftest
Build:             "C:\\gv\\Scripts\\pyinstaller.exe" desktop\\GlassesSizeImport.spec
"""
from __future__ import annotations

import os
import sys

# --- import bootstrap ------------------------------------------------------
# size_import/ and refresh_data.py live in the repo root; the desktop modules
# import each other flat. Make both work from source and from a bundle.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# ---------------------------------------------------------------------------

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QAction, QIcon  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QTabWidget, QVBoxLayout, QWidget,
)

import data_store  # noqa: E402
import theme  # noqa: E402
import updater  # noqa: E402
from app_paths import resource_path  # noqa: E402
from settings import Settings  # noqa: E402
from settings_dialog import SettingsDialog  # noqa: E402
from tabs import ALL_TABS  # noqa: E402
from version import APP_NAME, ORG_NAME, __version__  # noqa: E402
from workers import Worker  # noqa: E402


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.snapshot = None
        self._worker = None
        self._update_worker = None

        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1200, 780)

        self.tabs = QTabWidget()
        self.tab_widgets = []
        for cls in ALL_TABS:
            tab = cls(self.settings, self)
            tab.status_message.connect(self.show_status)
            tab.busy.connect(self.set_busy)
            self.tabs.addTab(tab, cls.TITLE)
            self.tab_widgets.append(tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)
        self.build_tab, self.data_tab = self.tab_widgets

        self.dock = QDockWidget("Control panel", self)
        self.dock.setObjectName("control_panel")
        self.dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self._empty_dock = QWidget()
        QVBoxLayout(self._empty_dock)
        self.dock.setWidget(self._empty_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.resizeDocks([self.dock], [320], Qt.Horizontal)

        self._build_toolbar()

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setMaximumWidth(180)
        self.statusBar().addPermanentWidget(self.progress)
        self.data_status = QLabel("")
        self.statusBar().addPermanentWidget(self.data_status)

        self._on_tab_changed(self.tabs.currentIndex())
        # The basket only changes through actions that emit a status message,
        # so that is enough to keep the unsaved-marker in the title honest.
        self.build_tab.status_message.connect(lambda _message: self._update_title())
        self.load_snapshot()

    # ------------------------------------------------------------- toolbar
    def _build_toolbar(self) -> None:
        bar = self.addToolBar("Main")
        bar.setObjectName("main_toolbar")

        self.act_refresh = QAction("🔁 Refresh from Excel", self)
        self.act_refresh.triggered.connect(self.refresh_from_excel)
        bar.addAction(self.act_refresh)

        self.act_remove = QAction("🗑 Remove selected", self)
        self.act_remove.triggered.connect(lambda: self.build_tab.remove_selected())
        bar.addAction(self.act_remove)

        self.act_clear = QAction("🧹 Clear basket", self)
        self.act_clear.triggered.connect(lambda: self.build_tab.clear_basket())
        bar.addAction(self.act_clear)

        self.act_export = QAction("💾 Export import file", self)
        self.act_export.triggered.connect(lambda: self.build_tab.export())
        bar.addAction(self.act_export)

        bar.addSeparator()

        self.act_settings = QAction("⚙️ Settings", self)
        self.act_settings.triggered.connect(self.open_settings)
        bar.addAction(self.act_settings)

        self.act_update = QAction("⬆️ Check updates", self)
        self.act_update.triggered.connect(self.check_updates)
        bar.addAction(self.act_update)

        self.act_dark = QAction("🌙 Dark mode", self)
        self.act_dark.setCheckable(True)
        self.act_dark.setChecked(self.settings.dark_mode)
        self.act_dark.toggled.connect(self.toggle_dark)
        bar.addAction(self.act_dark)

    def _on_tab_changed(self, index: int) -> None:
        tab = self.tabs.widget(index)
        panel = tab.control_panel() if tab else None
        if panel is None:
            self.dock.setWidget(self._empty_dock)
            self.dock.hide()
        else:
            self.dock.setWidget(panel)
            self.dock.show()
        on_build = tab is self.build_tab
        for action in (self.act_remove, self.act_clear, self.act_export):
            action.setEnabled(on_build)

    # -------------------------------------------------------------- status
    def show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    def set_busy(self, busy: bool) -> None:
        self.progress.setVisible(bool(busy))
        for action in (self.act_refresh, self.act_export, self.act_update):
            action.setEnabled(not busy)

    def _update_title(self) -> None:
        mark = " •" if self.build_tab.has_unsaved_changes() else ""
        self.setWindowTitle(f"{APP_NAME} {__version__}{mark}")

    # ------------------------------------------------------------ snapshot
    def load_snapshot(self) -> None:
        try:
            self.snapshot = data_store.load_snapshot()
        except FileNotFoundError as error:
            self.snapshot = None
            self.data_status.setText("No data")
            self.data_status.setStyleSheet(theme.status_style("error"))
            QMessageBox.warning(self, "No product data", str(error))
            for tab in self.tab_widgets:
                tab.set_snapshot(None)
            return

        for tab in self.tab_widgets:
            tab.set_snapshot(self.snapshot)
        origin = "local" if self.snapshot.source == "local" else "bundled"
        self.data_status.setText(
            f"{len(self.snapshot.catalogue):,} products ({origin}, "
            f"{self.snapshot.updated_at:%Y-%m-%d})"
        )
        self.data_status.setStyleSheet(theme.status_style("ready"))

    def refresh_from_excel(self) -> None:
        catalogue_xlsx, _ = QFileDialog.getOpenFileName(
            self, "Select Main catalogue.xlsx",
            self.settings.last_dir("source") or os.path.expanduser("~"),
            "Excel files (*.xlsx *.xlsm)",
        )
        if not catalogue_xlsx:
            return
        self.settings.set_last_dir("source", os.path.dirname(catalogue_xlsx))

        categories_xlsx, _ = QFileDialog.getOpenFileName(
            self, "Select Glasses size category ids.xlsx (Cancel to keep the current one)",
            os.path.dirname(catalogue_xlsx), "Excel files (*.xlsx *.xlsm)",
        )

        self.set_busy(True)
        self.show_status("Refreshing from Excel — this takes about 15 seconds…")
        worker = Worker(
            data_store.refresh_from_excel, catalogue_xlsx, categories_xlsx or None
        )

        def done(report):
            self.set_busy(False)
            self.data_tab.show_report(report)
            self.load_snapshot()
            catalogue = report.get("catalogue") or {}
            QMessageBox.information(
                self, "Refreshed",
                f"{catalogue.get('products', 0)} products loaded.\n"
                "See the Data tab for the full report.",
            )

        worker.done.connect(done)
        worker.failed.connect(
            lambda message: (self.set_busy(False),
                             QMessageBox.warning(self, "Refresh failed", message))
        )
        worker.start()
        self._worker = worker

    # ------------------------------------------------------------ settings
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        dialog.exec()

    def toggle_dark(self, enabled: bool) -> None:
        self.settings.dark_mode = bool(enabled)
        theme.apply_theme(QApplication.instance(), bool(enabled))

    # ------------------------------------------------------------- updates
    def check_updates(self) -> None:
        if not self.settings.update_token:
            QMessageBox.information(
                self, "Updates not configured",
                "This repo is private, so the update check needs a GitHub token "
                "with read access to its Releases.\nAdd one in ⚙️ Settings.",
            )
            return
        self.set_busy(True)
        worker = Worker(updater.update_available, self.settings.update_token)

        def done(release):
            self.set_busy(False)
            if not release:
                QMessageBox.information(
                    self, "Up to date", f"You are on the latest version ({__version__})."
                )
                return
            answer = QMessageBox.question(
                self, "Update available",
                f"Version {release['version']} is available (you have {__version__}).\n"
                "Download and install it now?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self._download_update(release)

        worker.done.connect(done)
        worker.failed.connect(
            lambda message: (self.set_busy(False),
                             QMessageBox.warning(self, "Update check failed", message))
        )
        worker.start()
        self._update_worker = worker

    def _download_update(self, release: dict) -> None:
        self.set_busy(True)
        worker = Worker(
            updater.download_and_swap, release, self.settings.update_token
        )

        def done(_path):
            self.set_busy(False)
            QMessageBox.information(
                self, "Restarting",
                "The update was downloaded. The app will now close and reopen.",
            )
            QApplication.instance().quit()

        worker.done.connect(done)
        worker.failed.connect(
            lambda message: (self.set_busy(False),
                             QMessageBox.warning(self, "Update failed", message))
        )
        worker.start()
        self._update_worker = worker

    # --------------------------------------------------------------- close
    def closeEvent(self, event) -> None:
        if self.build_tab.has_unsaved_changes():
            answer = QMessageBox.question(
                self, "Basket not exported",
                f"{len(self.build_tab.basket)} product(s) are still in the basket "
                "and will be lost. Close anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()


def _selftest(win) -> int:
    """--selftest: build the whole UI headlessly, print a report, exit."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    problems = []
    print(f"{APP_NAME} {__version__}")
    print(f"tabs: {win.tabs.count()}")
    for index in range(win.tabs.count()):
        tab = win.tabs.widget(index)
        win.tabs.setCurrentIndex(index)
        QApplication.processEvents()
        panel = tab.control_panel()
        print(
            f"  [{index}] {win.tabs.tabText(index)!r:20} "
            f"dock={'yes' if panel is not None else 'no'}"
        )
        for name in ("set_snapshot", "control_panel", "has_unsaved_changes"):
            if not callable(getattr(tab, name, None)):
                problems.append(f"{tab.__class__.__name__} missing {name}")

    snapshot = win.snapshot
    print(f"snapshot: {'none' if snapshot is None else snapshot.source}")
    if snapshot is not None:
        print(f"products: {len(snapshot.catalogue)}")
        print(f"categories: {sum(len(v) for v in snapshot.lookup.values())}")
    else:
        problems.append("no snapshot loaded — is data/ bundled or refreshed?")
    print(f"data status: {win.data_status.text()!r}")
    print(f"dock shown on current tab: {not win.dock.isHidden()}")
    print(f"update token configured: {bool(win.settings.update_token)}")

    if problems:
        print("PROBLEMS:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("SELFTEST OK — UI built, snapshot loaded.")
    return 0


def main() -> int:
    selftest = "--selftest" in sys.argv
    if selftest:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)

    icon_path = resource_path("app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    settings = Settings()
    theme.apply_theme(app, settings.dark_mode)

    win = MainWindow()
    if selftest:
        QApplication.processEvents()
        code = _selftest(win)
        # Never leave a QThread alive at interpreter exit — Qt hangs on it.
        for attr in ("_worker", "_update_worker"):
            worker = getattr(win, attr, None)
            if worker is not None and worker.isRunning():
                worker.wait(5000)
        return code

    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the selftest — it will fail until Task 7 exists**

Run: `"C:/gv/Scripts/python.exe" desktop/main.py --selftest`
Expected: FAIL — `ModuleNotFoundError: No module named 'updater'` (and `settings_dialog`). That is expected; Task 7 supplies both.

- [ ] **Step 3: Commit**

```bash
git add desktop/main.py
git commit -m "feat: main window, toolbar, dock routing and selftest"
```

---

### Task 7: Updater and settings dialog

**Files:**
- Create: `desktop/updater.py`, `desktop/test_updater_swap.py`, `desktop/settings_dialog.py`

- [ ] **Step 1: Port the swap test**

Copy the filler's test, which proves the PowerShell swap actually replaces a file and relaunches:

```bash
cp "/c/Users/blank/Documents/GitHub/Glasses-Import-Filler/desktop/test_updater_swap.py" desktop/test_updater_swap.py
```

Open it and fix anything that names the filler: the `sys.path` bootstrap must point at this `desktop/` folder, and any reference to `glassesfiller_update.log` becomes `glassessizeimport_update.log`.

- [ ] **Step 2: Run it to see it fail**

It is a standalone script with its own `check()` assertions, not a pytest module — pytest collects nothing from it, so run it directly:

Run: `"C:/gv/Scripts/python.exe" desktop/test_updater_swap.py; echo "exit=$?"`
Expected: FAIL — `ModuleNotFoundError: No module named 'updater'`

- [ ] **Step 3: Port `updater.py` with token support**

Copy the filler's `desktop/updater.py`, then make exactly these changes — the repo here is private, so both the API call and the asset download need an `Authorization` header, and the asset download needs GitHub's API URL rather than the browser URL:

```bash
cp "/c/Users/blank/Documents/GitHub/Glasses-Import-Filler/desktop/updater.py" desktop/updater.py
```

1. Change the log name constant:

```python
SWAP_LOG_NAME = "glassessizeimport_update.log"
```

2. Replace the request-header helper and the two functions that make HTTP calls:

```python
def _request(url: str, token: str, accept: str) -> urllib.request.Request:
    """A GitHub request. This repo is private, so a token is required; without
    one the caller reports 'not configured' rather than failing."""
    request = urllib.request.Request(url)
    request.add_header("User-Agent", "GlassesSizeImport-Desktop")
    request.add_header("Accept", accept)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return request


def latest_release(token: str = "") -> dict | None:
    """Newest desktop release as {'version','tag','url','name'} or None."""
    url = f"https://api.github.com/repos/{RELEASE_REPO}/releases"
    with urllib.request.urlopen(
        _request(url, token, "application/vnd.github+json"), timeout=_TIMEOUT
    ) as response:
        releases = json.loads(response.read().decode("utf-8"))

    best = None
    for release in releases:
        tag = str(release.get("tag_name", ""))
        if not tag.startswith(RELEASE_TAG_PREFIX) or release.get("draft"):
            continue
        version = tag[len(RELEASE_TAG_PREFIX):]
        asset = next(
            (a for a in release.get("assets", [])
             if str(a.get("name", "")).lower().endswith(".exe")),
            None,
        )
        if not asset:
            continue
        candidate = {
            "version": version,
            "tag": tag,
            # The API asset URL works for private repos; browser_download_url
            # does not without a session.
            "url": asset["url"],
            "name": asset["name"],
        }
        if best is None or _version_tuple(version) > _version_tuple(best["version"]):
            best = candidate
    return best


def update_available(token: str = "") -> dict | None:
    """The newer release, or None if we're current / can't tell."""
    try:
        release = latest_release(token)
    except Exception:
        return None
    if release and _version_tuple(release["version"]) > _version_tuple(__version__):
        return release
    return None
```

3. Change `download_and_swap` to take the token and use it, leaving the swap-script logic untouched:

```python
def download_and_swap(release: dict, token: str = "", progress=None) -> str:
    """Download the new .exe and hand over to the swap script. Returns the path
    of the downloaded file. The swap only happens when running frozen."""
    target_dir = os.path.dirname(
        sys.executable if is_frozen() else os.path.abspath(__file__)
    )
    new_path = os.path.join(target_dir, f"_update_{release['name']}")

    request = _request(release["url"], token, "application/octet-stream")
    with urllib.request.urlopen(request, timeout=300) as response:
        total = int(response.headers.get("Content-Length") or 0)
        read = 0
        with open(new_path, "wb") as handle:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                read += len(chunk)
                if progress and total:
                    progress(read / total, f"Downloading update… {read // 1048576} MB")

    if total and read < total:
        os.remove(new_path)
        raise IOError(f"Download incomplete ({read} of {total} bytes) — update aborted.")

    if not is_frozen():
        return new_path  # nothing to swap when running from source

    script = build_swap_script(os.getpid(), new_path, sys.executable, swap_log_path())
    subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )
    return new_path
```

Keep `_version_tuple`, `build_swap_script`, `swap_log_path` and `_ps_quote` exactly as they are — `build_swap_script` is what the ported test exercises.

- [ ] **Step 4: Run the swap test**

Run: `"C:/gv/Scripts/python.exe" desktop/test_updater_swap.py; echo "exit=$?"`
Expected: every `check` line reports OK, the script prints that the file was replaced and the replacement launched, and `exit=0`. This is the test that caught the original `.bat` swap closing the app without reopening it.

- [ ] **Step 5: Write `desktop/settings_dialog.py`**

```python
# -*- coding: utf-8 -*-
"""⚙️ Settings — the optional update token.

No token is ever baked into a build: a token-carrying .exe must not be attached
to a Release, and private distribution would break self-update.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.resize(520, 200)

        layout = QVBoxLayout(self)
        explanation = QLabel(
            "This repo is private, so checking for updates needs a GitHub "
            "fine-grained token with read access to its Contents and Releases. "
            "It is stored per user and never included in a build."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        self.token = QLineEdit(settings.update_token)
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("github_pat_… (optional)")
        form.addRow("Update token", self.token)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.settings.update_token = self.token.text()
        super().accept()
```

- [ ] **Step 6: Run the selftest for real**

The bundled snapshot lives at `desktop/data` when running from source, so link the repo's data folder first:

```bash
python -c "import os,shutil; os.makedirs('desktop/data', exist_ok=True); [shutil.copy(f'data/{f}', f'desktop/data/{f}') for f in ('catalogue.csv.gz','categories.json')]; print('copied')"
"C:/gv/Scripts/python.exe" desktop/main.py --selftest
```

Expected output ends with `SELFTEST OK — UI built, snapshot loaded.`, and reports `tabs: 2`, `products: 82690`, `categories: 455`, `dock=yes` on the Build tab and `dock=no` on the Data tab. Exit code must be 0 (`echo $?`).

Add `desktop/data/` to `.gitignore` — it is a build-time copy, not source:

```
desktop/data/
```

- [ ] **Step 7: Run the full suite and commit**

Run: `python -m pytest -q`
Expected: PASS, 56 passed (the swap script is not collected by pytest — it was run directly in Step 4)

```bash
git add desktop/updater.py desktop/test_updater_swap.py desktop/settings_dialog.py .gitignore
git commit -m "feat: private-repo self-update and settings dialog"
```

---

### Task 8: Icon, build, verification, handover

**Files:**
- Create: `desktop/make_icon.py`, `desktop/app_icon.ico`, `desktop/GlassesSizeImport.spec`, `HANDOVER_DESKTOP.md`

- [ ] **Step 1: Adapt the icon script**

```bash
cp "/c/Users/blank/Documents/GitHub/Glasses-Import-Filler/desktop/make_icon.py" desktop/make_icon.py
```

Edit it so the family reads as one set but this app is distinguishable: keep the slate-blue glasses and the badge position exactly as they are, and change only the badge — replace the amber disc and white pencil with a **teal disc (`(0, 150, 145, 255)`) and a white measuring bar**: a horizontal white rounded bar across the disc with three short white ticks below it, drawn with the same stroke width the pencil used. Update the module docstring to say this is the size-import app (teal disc + measure) rather than the filler (amber + pencil).

Run: `"C:/gv/Scripts/python.exe" desktop/make_icon.py`
Expected: writes `desktop/app_icon.ico` and `desktop/app_icon.png`. Open the .png and confirm the glasses match the other two apps and the badge is teal.

- [ ] **Step 2: Write `desktop/GlassesSizeImport.spec`**

```python
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
```

- [ ] **Step 3: Show the tests and the selftest before building**

Run: `python -m pytest -q`
Then: `"C:/gv/Scripts/python.exe" desktop/main.py --selftest; echo "exit=$?"`
Expected: all tests pass, selftest prints `SELFTEST OK` and `exit=0`. Report both outputs before continuing — the build is slow and pointless if either fails.

- [ ] **Step 4: Build the .exe**

Run: `"C:/gv/Scripts/pyinstaller.exe" desktop/GlassesSizeImport.spec`
Expected: `dist/GlassesSizeImport.exe` exists. Report its size:

```bash
python -c "import os; print(round(os.path.getsize('dist/GlassesSizeImport.exe')/1e6, 1), 'MB')"
```

Roughly 150-250 MB is normal for a PySide6 one-file build.

- [ ] **Step 5: Scan the build for secrets before it goes anywhere**

```bash
python -c "
import re
blob = open('dist/GlassesSizeImport.exe','rb').read()
hits = [p for p in (b'ghp_', b'github_pat', b'postgresql://', b'sk-ant') if p in blob]
print('SECRET PATTERNS FOUND:', hits if hits else 'none')
"
```

Expected: `none`. Anything else means STOP — do not publish that build.

- [ ] **Step 6: Verify the built app by hand**

Launch `dist/GlassesSizeImport.exe` and confirm, reporting each result:

1. It opens with the Data tab showing a bundled snapshot, 82,690 products, 455 categories
2. Searching `crulle g5063` lists matches with their global IDs
3. Entering lens width 55, bridge 15, temple length 140 shows `category 4156`, `category 4157`, `category 4266`
4. Entering glasses-to-bend 118 shows the red "No category … will be skipped"
5. **Add to basket** adds one row whose Category IDs read `4156;4157;4266`, and clears the fields
6. Re-adding the same product with lens width 52 keeps one row and grows it to `4156;4157;4266;4188`
7. **Export import file** writes an .xlsx; opening it shows no header row, the global ID in A1 as a number and the IDs in B1 as text
8. Right-clicking the basket offers "Copy whole table (TSV)", and the copy pastes into Excel as four columns
9. 🌙 Dark mode switches, and survives a restart
10. Closing with a non-empty basket prompts first

- [ ] **Step 7: Write `HANDOVER_DESKTOP.md`**

```markdown
# Glasses Size Import — desktop app

A Windows `.exe` build of the size-category import builder. Same logic as the
Streamlit app (`size_import/*`), no network, no credentials.

## Run from source

    "C:\gv\Scripts\python.exe" desktop\main.py

`C:\gv` is a venv at a short path — the Microsoft Store Python's path is long
enough that installing PySide6 fails with "enable-long-paths".

## Selftest

    "C:\gv\Scripts\python.exe" desktop\main.py --selftest

Builds both tabs headlessly and exits 0. Run it before every build.

## Build

    python -c "import os,shutil; os.makedirs('desktop/data', exist_ok=True); [shutil.copy(f'data/{f}', f'desktop/data/{f}') for f in ('catalogue.csv.gz','categories.json')]"
    "C:\gv\Scripts\pyinstaller.exe" desktop\GlassesSizeImport.spec

Output: `dist\GlassesSizeImport.exe`. Unsigned, so SmartScreen warns once.

## Where the data comes from

1. `%LOCALAPPDATA%\GlassesSizeImport\data` — written by 🔁 Refresh from Excel
2. otherwise the snapshot bundled in the .exe

The two files resolve independently, so refreshing only the catalogue keeps the
existing categories. The parsed catalogue is cached as `catalogue.pkl` in
`%LOCALAPPDATA%\GlassesSizeImport` and reused until the CSV changes.

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
```

- [ ] **Step 8: Commit and push**

```bash
git add desktop/make_icon.py desktop/app_icon.ico desktop/app_icon.png desktop/GlassesSizeImport.spec HANDOVER_DESKTOP.md
git commit -m "feat: icon, PyInstaller spec and desktop handover"
git push
```

`dist/` is not committed; the .exe is attached to a Release instead.

---

## Definition of Done

- `python -m pytest` passes: 56 tests (the original 44, plus the new catalogue, app-paths and data-store tests)
- `desktop/test_updater_swap.py` run directly exits 0
- `desktop/main.py --selftest` prints `SELFTEST OK` and exits 0
- `dist/GlassesSizeImport.exe` launches, searches, resolves, baskets, merges a second size into one row, and exports a file that matches the import format
- The binary contains none of `ghp_`, `github_pat`, `postgresql://`, `sk-ant`
- The Streamlit app still runs against `catalogue.csv.gz`
- `HANDOVER_DESKTOP.md` exists and a project memory is written
