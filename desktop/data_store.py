# -*- coding: utf-8 -*-
r"""Where the product snapshot comes from, and how it gets refreshed.

Resolution order, per file:
  1. %LOCALAPPDATA%\GlassesSizeImport\data — a snapshot the user refreshed
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
