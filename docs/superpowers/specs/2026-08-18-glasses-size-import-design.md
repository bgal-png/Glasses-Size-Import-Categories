# Glasses Size Import Builder — Design

Date: 2026-08-18
Status: approved

## Problem

Glasses on the eshop often show no dimensions because the product's global ID has no
size categories assigned. Dimensions are attached to a product by importing a 2-column
Excel file: column A = product global ID, column B = one or more global category IDs
separated by `;`.

Building that file by hand means looking up the product's global ID in an 82,690-row
catalogue and looking up a category ID for every millimetre value in a 648-row category
list — where 244 of the categories are duplicates. It is slow and error-prone.

## Goal

A Streamlit app: search a product by name, type its dimensions, add it to a basket,
export an import-ready `.xlsx`.

## Sources

**`Main catalogue.xlsx`** (~19 MB, 82,693 rows, 104 columns). Only two columns are used:

| Column | Header | Meaning |
|---|---|---|
| C | `name` | Product name shown in search |
| CZ | `globalId` | Product global ID, unique per row (3 rows have no value) |

**`Glasses size category ids.xlsx`** (648 rows): `ID`, `Global category name`, `Value`.

Six dimensions, all values in whole millimetres:

- `Glasses size: glasses width`
- `Glasses size: lens width`
- `Glasses size: lens height`
- `Glasses size: bridge`
- `Glasses size: temple length`
- `Glasses size: glasses to bend length`

Two known defects in this file, both handled at prep time:

1. **Duplicates.** 244 rows belong to duplicate groups; collapsing them removes 187
   redundant rows. Worst case: `lens height 51` has 11 IDs. **Rule: keep the lowest ID.**
   This matches how the user assigns them manually today.
2. **Junk rows.** Six rows are unusable — IDs 4602 and 4805 have value `None`; IDs 34506,
   34509, 34512, 34513 have comma-decimal values (`26,3`, `40,2`, `131,8`, `37,1`).
   They are dropped, and `refresh_data.py` prints them so nothing disappears silently.

After dedup and cleaning: **455 usable categories** (648 rows - 6 junk - 187 collapsed
duplicates), broken down as: bridge 64, glasses to bend length 72, glasses width 89,
lens height 85, lens width 84, temple length 61.

Coverage inside real-world ranges is complete except `glasses to bend length`, which has
no category for 88, 118 or 119.

## Import semantics

The import **adds** categories to whatever the product already has. It does not replace.
Existing non-size categories are therefore safe and do not need to be included. If an
imported category is one the product already has, a duplicate assignment results; the
user has confirmed this is harmless.

## Architecture

### `refresh_data.py` — local prep, run only when a source file changes

- `Main catalogue.xlsx` → `data/catalogue.parquet` (name, globalId; ~1.2 MB)
- `Glasses size category ids.xlsx` → `data/categories.json` (deduped, cleaned)
- Prints a summary: rows read, duplicates collapsed, junk rows dropped

Rationale: parsing the 19 MB xlsx takes 12.5 s; loading the derived parquet takes 0.07 s.
Both derived files are committed, so the deployed app starts instantly and never reads
the fat source files.

### `app.py` — Streamlit, deployed to Streamlit Cloud (private repo), single user

Core lookup is a dict `(dimension, value) -> category ID`.

**Zone 1 — Pick a product.** Substring search over `name`, case- and diacritics-insensitive
(`crulle` matches `Crullé`). Selecting a match displays its global ID for visual confirmation.

**Zone 2 — Enter dimensions.** Six numeric fields, one per dimension. Blank fields are
skipped. Resolved category IDs are shown live as values are typed, so a wrong number is
visible before it is committed.

**Zone 3 — Basket.** "Add" appends a row: product name, global ID, entered values,
resulting category IDs. Rows can be removed or edited. Adding a product already in the
basket **merges** into its existing row — the export is one row per global ID.

**Export.** Writes `Sizes-<YYMMDD>-import.xlsx`, date defaulted to today:

- No header row; data starts at row 1
- Column A = global ID
- Column B = category IDs joined by `;`
- Default sheet name

### Multiple sizes

A frame sold in several sizes is one product with one global ID. All of its size
categories go into that single row, merged. The tool does not model sizes separately.

## Edge cases

| Case | Behaviour |
|---|---|
| Typed value has no category (e.g. to-bend 118) | Field flagged; that one value dropped; all other values still export |
| All six fields blank | "Add" disabled |
| Empty basket | "Export" disabled |
| Same product added twice | Merged into the existing basket row |
| Page refreshed mid-session | Basket lost — see below |

## Known limitation (accepted)

The basket lives in Streamlit session state. Refreshing the page loses it. Acceptable for
sessions of ~5–20 products. If longer sessions become normal, add a save-draft file then.

## Testing

pytest over the pure logic, no UI framework in the tests:

- value → category ID mapping, including a miss
- dedup keeps the lowest ID; junk rows are dropped
- duplicate product merges into one basket row
- export shape: no header, column A global ID, column B `;`-joined
- diacritics-insensitive search

## Out of scope

- Sourcing the dimension values themselves (user types them)
- Editing or deduplicating the global categories in the admin
- Any write path back to the eshop — the deliverable is a file the user imports manually
