# Glasses Size Import Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Streamlit app where the user searches a glasses product by name, types its dimensions in millimetres, collects several products in a basket, and exports a 2-column `.xlsx` (global ID, `;`-joined global category IDs) ready to import into the eshop admin.

**Architecture:** A local prep script (`refresh_data.py`) converts two fat source workbooks into two slim committed data files (`data/catalogue.parquet`, `data/categories.json`). All business logic lives in four small pure-Python modules under `size_import/` and is unit-tested without Streamlit. `app.py` is a thin Streamlit layer that wires those modules to widgets.

**Tech Stack:** Python (global interpreter, no venv), Streamlit, pandas + pyarrow (parquet), openpyxl (xlsx read/write), pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-glasses-size-import-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `size_import/__init__.py` | Empty package marker |
| `size_import/categories.py` | The six dimensions; build the `(dimension, value) -> lowest category ID` lookup; resolve a value; JSON round-trip |
| `size_import/catalogue.py` | Load `catalogue.parquet`; diacritics-insensitive multi-token product search |
| `size_import/basket.py` | Add / remove / merge basket entries; turn an entry into ordered category IDs; build export rows |
| `size_import/export.py` | Export filename from a date; build the header-less workbook; serialise to bytes |
| `refresh_data.py` | One-off local prep: fat xlsx -> slim `data/` files, with a printed report |
| `app.py` | Streamlit UI only — no business logic |
| `tests/test_categories.py` | Lookup building, lowest-ID rule, junk rejection, JSON round-trip |
| `tests/test_catalogue.py` | Normalisation and search |
| `tests/test_basket.py` | Add, merge, remove, category ID ordering, export rows |
| `tests/test_export.py` | Filename, header-less shape, bytes |
| `requirements.txt` | Loose dependency bounds (no hard pins) |
| `.gitignore` | Ignore `__pycache__`, root-level `*.xlsx`, `.pytest_cache` |
| `README.md` | How to refresh data and run the app |

The two source workbooks live outside the repo at `C:\Users\blank\Downloads\Main catalogue.xlsx` and `C:\Users\blank\Downloads\Glasses size category ids.xlsx`. They are never committed.

---

### Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `size_import/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

Loose bounds only — this machine uses a global Python install shared by other tools, so never hard-pin or downgrade.

```
streamlit>=1.30
pandas>=2.0
pyarrow>=14
openpyxl>=3.1
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
/*.xlsx
```

- [ ] **Step 3: Create empty package markers**

Create `size_import/__init__.py` and `tests/__init__.py`, both empty files.

- [ ] **Step 4: Verify the toolchain is present**

Run: `python -c "import streamlit, pandas, pyarrow, openpyxl, pytest; print('ok')"`
Expected: `ok`. If any import fails, run `python -m pip install -r requirements.txt` and retry.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore size_import/__init__.py tests/__init__.py
git commit -m "chore: project scaffold"
```

---

### Task 2: Category lookup

Builds the core `(dimension, value) -> category ID` map from the raw rows of `Glasses size category ids.xlsx`.

Facts this task must honour, measured from the real file: 648 data rows, 6 unusable rows (IDs 4602 and 4805 have value `None`; IDs 34506, 34509, 34512, 34513 have string values like `'26,3'`), 187 rows collapse away as duplicate `(dimension, value)` pairs, leaving **455** entries.

**Files:**
- Create: `size_import/categories.py`
- Test: `tests/test_categories.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_categories.py
from size_import.categories import (
    DIMENSIONS,
    build_lookup,
    from_json_dict,
    resolve,
    to_json_dict,
)


def test_six_dimensions_with_expected_keys():
    keys = [d.key for d in DIMENSIONS]
    assert keys == [
        "glasses_width",
        "lens_width",
        "lens_height",
        "bridge",
        "temple_length",
        "to_bend_length",
    ]


def test_build_lookup_maps_value_to_id():
    lookup, report = build_lookup([(4156, "Glasses size: lens width", 55)])
    assert resolve(lookup, "lens_width", 55) == 4156
    assert report["kept"] == 1
    assert report["collapsed"] == 0
    assert report["dropped"] == []


def test_duplicate_value_keeps_lowest_id_regardless_of_row_order():
    rows = [
        (4772, "Glasses size: lens height", 51),
        (4310, "Glasses size: lens height", 51),
        (4489, "Glasses size: lens height", 51),
    ]
    lookup, report = build_lookup(rows)
    assert resolve(lookup, "lens_height", 51) == 4310
    assert report["kept"] == 1
    assert report["collapsed"] == 2


def test_junk_rows_are_dropped_and_reported():
    rows = [
        (4602, "Glasses size: glasses to bend length", None),
        (34506, "Glasses size: lens height", "26,3"),
        (9999, "Some unrelated category", 42),
        (4157, "Glasses size: bridge", 15),
    ]
    lookup, report = build_lookup(rows)
    assert resolve(lookup, "bridge", 15) == 4157
    assert report["kept"] == 1
    assert [row[0] for row in report["dropped"]] == [4602, 34506, 9999]


def test_resolve_returns_none_for_missing_value():
    lookup, _ = build_lookup([(4157, "Glasses size: bridge", 15)])
    assert resolve(lookup, "bridge", 16) is None
    assert resolve(lookup, "lens_width", 55) is None


def test_json_round_trip_preserves_integer_keys():
    lookup, _ = build_lookup([(4156, "Glasses size: lens width", 55)])
    restored = from_json_dict(to_json_dict(lookup))
    assert restored == lookup
    assert resolve(restored, "lens_width", 55) == 4156
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_categories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'size_import.categories'`

- [ ] **Step 3: Write the implementation**

```python
# size_import/categories.py
"""The six glasses size dimensions and the value -> category ID lookup.

The source workbook contains duplicate categories for the same (dimension, value)
pair - up to eleven IDs for `lens height 51`. The rule, matching how the user
assigns them by hand, is to keep the lowest ID.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dimension:
    key: str
    source_name: str
    label: str


DIMENSIONS = [
    Dimension("glasses_width", "Glasses size: glasses width", "Glasses width"),
    Dimension("lens_width", "Glasses size: lens width", "Lens width"),
    Dimension("lens_height", "Glasses size: lens height", "Lens height"),
    Dimension("bridge", "Glasses size: bridge", "Bridge"),
    Dimension("temple_length", "Glasses size: temple length", "Temple length"),
    Dimension(
        "to_bend_length",
        "Glasses size: glasses to bend length",
        "Glasses to bend length",
    ),
]

BY_SOURCE_NAME = {dimension.source_name: dimension for dimension in DIMENSIONS}


def _is_usable(category_id, dimension, value):
    if category_id is None or dimension is None:
        return False
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return True


def build_lookup(rows):
    """Build {dimension key: {value: category ID}} from raw (id, name, value) rows.

    Returns (lookup, report). The report carries the dropped rows verbatim and a
    count of duplicates collapsed, so the prep script can print what it discarded.
    """
    lookup = {dimension.key: {} for dimension in DIMENSIONS}
    dropped = []
    collapsed = 0

    for category_id, source_name, value in rows:
        dimension = BY_SOURCE_NAME.get(source_name)
        if not _is_usable(category_id, dimension, value):
            dropped.append((category_id, source_name, value))
            continue

        bucket = lookup[dimension.key]
        if value in bucket:
            collapsed += 1
            bucket[value] = min(bucket[value], category_id)
        else:
            bucket[value] = category_id

    report = {
        "kept": sum(len(bucket) for bucket in lookup.values()),
        "collapsed": collapsed,
        "dropped": dropped,
    }
    return lookup, report


def resolve(lookup, key, value):
    """Category ID for one dimension value, or None if no category exists."""
    return lookup.get(key, {}).get(value)


def to_json_dict(lookup):
    """JSON needs string keys; convert {value: id} to {"value": id}."""
    return {
        key: {str(value): category_id for value, category_id in bucket.items()}
        for key, bucket in lookup.items()
    }


def from_json_dict(raw):
    return {
        key: {int(value): category_id for value, category_id in bucket.items()}
        for key, bucket in raw.items()
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_categories.py -v`
Expected: PASS, 6 passed

- [ ] **Step 5: Commit**

```bash
git add size_import/categories.py tests/test_categories.py
git commit -m "feat: category lookup with lowest-ID dedup"
```

---

### Task 3: Catalogue search

**Files:**
- Create: `size_import/catalogue.py`
- Test: `tests/test_catalogue.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_catalogue.py
import pandas as pd

from size_import.catalogue import normalize, search

CATALOGUE = pd.DataFrame(
    {
        "name": [
            "Crullé G5063 C3",
            "Ray-Ban Justin RB4165 601/8G",
            "Ray-Ban Aviator RB3025",
            "1 Day Acuvue Moist",
        ],
        "globalId": [1588262, 245001, 245002, 14],
    }
)


def _prepared():
    frame = CATALOGUE.copy()
    frame["search_key"] = frame["name"].map(normalize)
    return frame


def test_normalize_strips_diacritics_and_case():
    assert normalize("Crullé G5063") == "crulle g5063"
    assert normalize("  Böhm  ") == "bohm"
    assert normalize(None) == ""


def test_search_is_diacritics_insensitive():
    result = search(_prepared(), "crulle")
    assert list(result["globalId"]) == [1588262]


def test_search_requires_all_tokens_in_any_order():
    result = search(_prepared(), "justin ray")
    assert list(result["globalId"]) == [245001]


def test_search_matches_multiple_products():
    result = search(_prepared(), "ray-ban")
    assert list(result["globalId"]) == [245001, 245002]


def test_hyphen_and_space_are_interchangeable():
    assert list(search(_prepared(), "ray ban aviator")["globalId"]) == [245002]


def test_blank_query_returns_nothing():
    assert len(search(_prepared(), "   ")) == 0


def test_limit_caps_results():
    assert len(search(_prepared(), "ray", limit=1)) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_catalogue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'size_import.catalogue'`

- [ ] **Step 3: Write the implementation**

```python
# size_import/catalogue.py
"""Loading and searching the slim product catalogue."""

import unicodedata

import pandas as pd


def normalize(text):
    """Lowercase, trimmed, diacritics removed - so `crulle` finds `Crullé`."""
    if text is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().strip()


def load_catalogue(path):
    """Read catalogue.parquet and attach the precomputed search key column."""
    frame = pd.read_parquet(path)
    frame["search_key"] = frame["name"].map(normalize)
    return frame


def search(frame, query, limit=50):
    """Products whose name contains every token of the query, in any order."""
    tokens = [token for token in normalize(query).replace("-", " ").split() if token]
    if not tokens:
        return frame.head(0)

    keys = frame["search_key"].str.replace("-", " ", regex=False)
    mask = pd.Series(True, index=frame.index)
    for token in tokens:
        mask &= keys.str.contains(token, regex=False, na=False)
    return frame[mask].head(limit)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_catalogue.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add size_import/catalogue.py tests/test_catalogue.py
git commit -m "feat: diacritics-insensitive catalogue search"
```

---

### Task 4: Basket

A basket is `{global_id: {"name": str, "value_sets": [ {dimension key: int}, ... ]}}`.

Storing a *list* of value sets rather than one flat dict is deliberate: adding the same
product twice with a second size must union both sizes' categories into that product's
single export row, not overwrite the first.

**Files:**
- Create: `size_import/basket.py`
- Test: `tests/test_basket.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_basket.py
from size_import.basket import add, category_ids, export_rows, remove
from size_import.categories import build_lookup

LOOKUP, _ = build_lookup(
    [
        (4156, "Glasses size: lens width", 55),
        (4162, "Glasses size: lens width", 50),
        (4157, "Glasses size: bridge", 15),
        (4310, "Glasses size: lens height", 51),
        (4185, "Glasses size: temple length", 135),
        (4153, "Glasses size: glasses width", 138),
    ]
)


def test_add_creates_entry():
    basket = add({}, 1588262, "Crulle G5063 C3", {"lens_width": 55, "bridge": 15})
    assert basket[1588262]["name"] == "Crulle G5063 C3"
    assert basket[1588262]["value_sets"] == [{"lens_width": 55, "bridge": 15}]


def test_add_does_not_mutate_the_original_basket():
    original = add({}, 1, "A", {"bridge": 15})
    add(original, 1, "A", {"lens_width": 55})
    assert original[1]["value_sets"] == [{"bridge": 15}]


def test_adding_second_size_to_same_product_keeps_both_value_sets():
    basket = add({}, 1, "A", {"lens_width": 50})
    basket = add(basket, 1, "A", {"lens_width": 55})
    assert basket[1]["value_sets"] == [{"lens_width": 50}, {"lens_width": 55}]
    assert list(basket) == [1]


def test_adding_identical_values_twice_changes_nothing():
    basket = add({}, 1, "A", {"lens_width": 55})
    basket = add(basket, 1, "A", {"lens_width": 55})
    assert basket[1]["value_sets"] == [{"lens_width": 55}]


def test_remove_drops_only_that_product():
    basket = add(add({}, 1, "A", {"bridge": 15}), 2, "B", {"bridge": 15})
    assert list(remove(basket, 1)) == [2]


def test_category_ids_follow_dimension_order_and_never_repeat():
    basket = add({}, 1, "A", {"bridge": 15, "glasses_width": 138, "lens_width": 55})
    basket = add(basket, 1, "A", {"lens_width": 50, "bridge": 15})
    assert category_ids(basket[1], LOOKUP) == [4153, 4156, 4157, 4162]


def test_category_ids_skip_values_with_no_category():
    basket = add({}, 1, "A", {"lens_width": 55, "bridge": 99})
    assert category_ids(basket[1], LOOKUP) == [4156]


def test_export_rows_join_ids_with_semicolons():
    basket = add({}, 1588262, "A", {"lens_width": 55, "bridge": 15})
    basket = add(basket, 245001, "B", {"temple_length": 135})
    assert export_rows(basket, LOOKUP) == [
        (1588262, "4156;4157"),
        (245001, "4185"),
    ]


def test_export_rows_skip_products_that_resolved_to_nothing():
    basket = add({}, 1, "A", {"bridge": 99})
    assert export_rows(basket, LOOKUP) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_basket.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'size_import.basket'`

- [ ] **Step 3: Write the implementation**

```python
# size_import/basket.py
"""The basket of products queued for one import file.

Shape: {global_id: {"name": str, "value_sets": [{dimension key: mm value}, ...]}}
Every function returns a new basket; nothing mutates in place, which keeps
Streamlit session state predictable.
"""

from size_import.categories import DIMENSIONS, resolve


def add(basket, global_id, name, values):
    """Queue a product, or merge another size into one already queued."""
    updated = dict(basket)
    existing = updated.get(global_id)

    if existing is None:
        entry = {"name": name, "value_sets": []}
    else:
        entry = {"name": existing["name"], "value_sets": list(existing["value_sets"])}

    if values and dict(values) not in entry["value_sets"]:
        entry["value_sets"].append(dict(values))

    updated[global_id] = entry
    return updated


def remove(basket, global_id):
    return {key: value for key, value in basket.items() if key != global_id}


def category_ids(entry, lookup):
    """Ordered, repeat-free category IDs for one basket entry."""
    ids = []
    for value_set in entry["value_sets"]:
        for dimension in DIMENSIONS:
            if dimension.key not in value_set:
                continue
            category_id = resolve(lookup, dimension.key, value_set[dimension.key])
            if category_id is not None and category_id not in ids:
                ids.append(category_id)
    return ids


def export_rows(basket, lookup):
    """(global ID, ";"-joined category IDs) per product, skipping empty ones."""
    rows = []
    for global_id, entry in basket.items():
        ids = category_ids(entry, lookup)
        if ids:
            rows.append((global_id, ";".join(str(value) for value in ids)))
    return rows
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_basket.py -v`
Expected: PASS, 9 passed

- [ ] **Step 5: Commit**

```bash
git add size_import/basket.py tests/test_basket.py
git commit -m "feat: basket with per-product size merging"
```

---

### Task 5: Export

**Files:**
- Create: `size_import/export.py`
- Test: `tests/test_export.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_export.py
import datetime
from io import BytesIO

import openpyxl

from size_import.export import build_workbook, export_filename, to_bytes


def test_export_filename_uses_two_digit_date():
    assert export_filename(datetime.date(2026, 8, 18)) == "Sizes-260818-import.xlsx"


def test_workbook_has_no_header_row():
    sheet = build_workbook([(1588262, "4156;4157")]).active
    assert sheet["A1"].value == 1588262
    assert sheet["B1"].value == "4156;4157"
    assert sheet.max_row == 1


def test_workbook_writes_one_row_per_product():
    sheet = build_workbook([(1, "10"), (2, "20;30")]).active
    assert [(row[0].value, row[1].value) for row in sheet.iter_rows()] == [
        (1, "10"),
        (2, "20;30"),
    ]


def test_global_id_is_written_as_a_number():
    sheet = build_workbook([(1588262, "4156")]).active
    assert isinstance(sheet["A1"].value, int)


def test_to_bytes_produces_a_readable_workbook():
    data = to_bytes([(1588262, "4156;4157")])
    sheet = openpyxl.load_workbook(BytesIO(data)).active
    assert sheet["A1"].value == 1588262
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_export.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'size_import.export'`

- [ ] **Step 3: Write the implementation**

```python
# size_import/export.py
"""The import file: no header row, column A global ID, column B ";"-joined IDs."""

from io import BytesIO

from openpyxl import Workbook


def export_filename(today):
    return f"Sizes-{today:%y%m%d}-import.xlsx"


def build_workbook(rows):
    workbook = Workbook()
    sheet = workbook.active
    for global_id, category_ids in rows:
        sheet.append([global_id, category_ids])
    return workbook


def to_bytes(rows):
    buffer = BytesIO()
    build_workbook(rows).save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_export.py -v`
Expected: PASS, 5 passed

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -v`
Expected: PASS, 27 passed

- [ ] **Step 6: Commit**

```bash
git add size_import/export.py tests/test_export.py
git commit -m "feat: header-less xlsx export"
```

---

### Task 6: Data prep script

Turns the two fat workbooks into the two slim committed data files. Reading the 19 MB
catalogue takes about 12 seconds; this is why it happens here and not in the app.

**Files:**
- Create: `refresh_data.py`
- Creates at runtime: `data/catalogue.parquet`, `data/categories.json`

- [ ] **Step 1: Write the script**

```python
# refresh_data.py
r"""Convert the source workbooks into the slim data files the app reads.

Run locally whenever either source export changes, then commit data/.

    python refresh_data.py
"""

import argparse
import json
from pathlib import Path

import openpyxl
import pandas as pd

from size_import.categories import build_lookup, to_json_dict

DEFAULT_CATALOGUE = Path(r"C:\Users\blank\Downloads\Main catalogue.xlsx")
DEFAULT_CATEGORIES = Path(r"C:\Users\blank\Downloads\Glasses size category ids.xlsx")
DATA_DIR = Path(__file__).parent / "data"

NAME_COLUMN = 2         # column C, zero-based
GLOBAL_ID_COLUMN = 103  # column CZ, zero-based


def refresh_catalogue(source, destination):
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
    frame.to_parquet(destination, index=False)
    print(f"catalogue: {len(frame)} products -> {destination}")
    print(f"catalogue: {skipped} rows skipped (no name or no globalId)")


def refresh_categories(source, destination):
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]

    rows = [row[:3] for row in sheet.iter_rows(min_row=2, values_only=True) if row[0]]
    lookup, report = build_lookup(rows)

    destination.write_text(
        json.dumps(to_json_dict(lookup), indent=1, sort_keys=True), encoding="utf-8"
    )

    print(f"categories: {len(rows)} rows read")
    print(f"categories: {report['collapsed']} duplicates collapsed (lowest ID kept)")
    print(f"categories: {len(report['dropped'])} rows dropped:")
    for category_id, name, value in report["dropped"]:
        print(f"  - id={category_id} name={name!r} value={value!r}")
    print(f"categories: {report['kept']} usable categories -> {destination}")


def main():
    parser = argparse.ArgumentParser(description="Refresh the slim data files.")
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--categories", type=Path, default=DEFAULT_CATEGORIES)
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    refresh_catalogue(args.catalogue, DATA_DIR / "catalogue.parquet")
    refresh_categories(args.categories, DATA_DIR / "categories.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it against the real sources**

Run: `python refresh_data.py`

Expected output — these numbers were measured from the real files and are the acceptance
check for this task:

```
catalogue: 82690 products -> ...\data\catalogue.parquet
catalogue: 3 rows skipped (no name or no globalId)
categories: 648 rows read
categories: 187 duplicates collapsed (lowest ID kept)
categories: 6 rows dropped:
  - id=4602 name='Glasses size: glasses to bend length' value=None
  - id=4805 name='Glasses size: glasses width' value=None
  - id=34506 name='Glasses size: lens height' value='26,3'
  - id=34509 name='Glasses size: lens height' value='40,2'
  - id=34512 name='Glasses size: glasses width' value='131,8'
  - id=34513 name='Glasses size: lens height' value='37,1'
categories: 455 usable categories -> ...\data\categories.json
```

If a count differs, stop and investigate before continuing — either a source file changed
or the column indices are wrong.

- [ ] **Step 3: Spot-check the generated files**

Run:

```bash
python -c "import json,pandas as pd; c=pd.read_parquet('data/catalogue.parquet'); print(c.shape); k=json.load(open('data/categories.json')); print(k['lens_width']['55'], k['lens_height']['51'])"
```

Expected: shape `(82690, 2)`, then `4156 4310`. The 4310 proves the lowest-ID rule beat
the ten other `lens height 51` categories.

- [ ] **Step 4: Confirm the parquet is small enough to commit**

Run: `python -c "import os; print(round(os.path.getsize('data/catalogue.parquet')/1e6, 2), 'MB')"`
Expected: about `1.22 MB`. Anything over 20 MB should not be committed — stop and ask.

- [ ] **Step 5: Commit the script and the generated data**

```bash
git add refresh_data.py data/catalogue.parquet data/categories.json
git commit -m "feat: data prep script and generated catalogue/category data"
```

---

### Task 7: Streamlit app

The UI holds no business logic — it loads the data files, calls the modules, and renders.

**Files:**
- Create: `app.py`

- [ ] **Step 1: Write the app**

```python
# app.py
"""Glasses Size Import Builder - search a product, type its dimensions, export."""

import datetime
import json
from pathlib import Path

import streamlit as st

from size_import import basket as basket_module
from size_import.catalogue import load_catalogue, search
from size_import.categories import DIMENSIONS, from_json_dict, resolve
from size_import.export import export_filename, to_bytes

DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(page_title="Glasses Size Import", page_icon="👓", layout="wide")


@st.cache_data
def get_catalogue():
    return load_catalogue(DATA_DIR / "catalogue.parquet")


@st.cache_data
def get_lookup():
    raw = json.loads((DATA_DIR / "categories.json").read_text(encoding="utf-8"))
    return from_json_dict(raw)


catalogue = get_catalogue()
lookup = get_lookup()

if "basket" not in st.session_state:
    st.session_state.basket = {}

# Bumped after every add. It is part of every number_input key, which is how the
# fields get cleared - Streamlit forbids writing to a widget's session state after
# that widget has been instantiated, so a fresh key is the way to reset them.
if "field_nonce" not in st.session_state:
    st.session_state.field_nonce = 0

st.title("Glasses Size Import Builder")

# --- Zone 1: pick a product ------------------------------------------------
st.subheader("1. Product")
query = st.text_input("Search by name", placeholder="e.g. crulle g5063")

selected_id = None
selected_name = None

if query:
    matches = search(catalogue, query, limit=50)
    if matches.empty:
        st.warning("No product matches that name.")
    else:
        options = list(matches.itertuples(index=False))
        label = f"{len(options)} match(es)"
        if len(options) == 50:
            label += " - showing first 50, refine the search if needed"
        choice = st.selectbox(
            label,
            options,
            format_func=lambda row: f"{row.name} - {row.globalId}",
        )
        selected_id = int(choice.globalId)
        selected_name = str(choice.name)
        st.caption(f"Global ID: **{selected_id}**")

# --- Zone 2: dimensions ----------------------------------------------------
st.subheader("2. Dimensions (mm)")
columns = st.columns(3)
values = {}

for index, dimension in enumerate(DIMENSIONS):
    with columns[index % 3]:
        entered = st.number_input(
            dimension.label,
            min_value=0,
            max_value=300,
            value=0,
            step=1,
            key=f"input_{dimension.key}_{st.session_state.field_nonce}",
        )
        if entered:
            values[dimension.key] = int(entered)
            category_id = resolve(lookup, dimension.key, int(entered))
            if category_id is None:
                st.error(f"No category for {entered} - will be skipped")
            else:
                st.caption(f"category {category_id}")

add_disabled = selected_id is None or not values
if st.button("Add to basket", type="primary", disabled=add_disabled):
    st.session_state.basket = basket_module.add(
        st.session_state.basket, selected_id, selected_name, values
    )
    st.session_state.field_nonce += 1
    st.rerun()

if selected_id is None:
    st.caption("Pick a product first.")
elif not values:
    st.caption("Enter at least one dimension.")

# --- Zone 3: basket --------------------------------------------------------
st.subheader("3. Basket")
current = st.session_state.basket

if not current:
    st.info("Basket is empty.")
else:
    for global_id, entry in list(current.items()):
        ids = basket_module.category_ids(entry, lookup)
        left, right = st.columns([9, 1])
        with left:
            sizes = " | ".join(
                ", ".join(f"{key}={value}" for key, value in value_set.items())
                for value_set in entry["value_sets"]
            )
            st.markdown(f"**{entry['name']}** - `{global_id}`")
            st.caption(sizes)
            st.code(";".join(str(value) for value in ids), language=None)
        with right:
            if st.button("Remove", key=f"remove_{global_id}"):
                st.session_state.basket = basket_module.remove(current, global_id)
                st.rerun()

    rows = basket_module.export_rows(current, lookup)
    st.download_button(
        f"Export {len(rows)} product(s)",
        data=to_bytes(rows),
        file_name=export_filename(datetime.date.today()),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        disabled=not rows,
    )
```

- [ ] **Step 2: Run the app**

Run: `streamlit run app.py`
Expected: opens in a browser showing the three zones and an empty basket.

- [ ] **Step 3: Manual smoke test**

Do each of these in the browser and confirm the stated result:

1. Search `crulle` → matches appear, each showing a global ID
2. Select one, enter lens width `55`, bridge `15`, temple length `140` → each field shows `category NNNN`
3. Enter glasses-to-bend `118` → red "No category for 118 - will be skipped"
4. Click **Add to basket** → the product appears with its `;`-joined IDs, and 118 contributed nothing
5. Search a second product, add it → the basket has two rows
6. Re-add the first product with a *different* lens width → still two rows; the first row's ID list grew
7. Click **Export** → downloads `Sizes-<today>-import.xlsx`
8. Open the downloaded file → row 1 is data, not a header; column A is the global ID; column B is the ID list

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: streamlit UI"
```

---

### Task 8: README and final verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# Glasses Size Import Builder

Builds the 2-column import file that attaches size categories to glasses products:
column A = product global ID, column B = global category IDs joined by `;`.

## Run

```bash
streamlit run app.py
```

## Refresh the data

Run whenever `Main catalogue.xlsx` or `Glasses size category ids.xlsx` is re-exported,
then commit the changed files in `data/`.

```bash
python refresh_data.py
```

Defaults read both workbooks from `C:\Users\blank\Downloads\`. Override with
`--catalogue` and `--categories`.

The script prints what it dropped and how many duplicate categories it collapsed.
Duplicate `(dimension, value)` categories always resolve to the **lowest** ID.

## Tests

```bash
python -m pytest
```

## Notes

- The import **adds** categories; it does not replace existing ones.
- The basket lives in browser session state - refreshing the page clears it.
- Design: `docs/superpowers/specs/2026-08-18-glasses-size-import-design.md`
````

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS, 27 passed

- [ ] **Step 3: Confirm nothing is left uncommitted**

Run: `git status --short`
Expected: only `README.md` untracked; nothing else outstanding.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: readme"
```

---

## Definition of Done

- `python -m pytest` passes, 27 tests
- `python refresh_data.py` reports 82690 products and 455 usable categories
- The app searches, resolves values to IDs, baskets, merges a second size into one row, and exports
- The exported file has no header row, column A = global ID, column B = `;`-joined category IDs

## Deployment (after the plan is done, on request)

Streamlit Cloud from a private GitHub repo. `data/` is committed, so no upload step is
needed and startup is fast. Not part of this plan — do it when the user asks.
