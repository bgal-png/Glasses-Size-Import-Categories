# Glasses Size Import — Desktop App Design

Date: 2026-08-31
Status: approved

## Goal

Ship the Glasses Size Import Builder as a PySide6 Windows `.exe`, following the house
pattern in memory `reference-desktop-tool-conventions` (established by the Glasses
Validator desktop app and the Glasses Filler desktop app). Match the family; do not
invent a new style.

The Streamlit app stays alive and keeps working off the same logic modules.

## Starting point

The web app already satisfies the pattern's first non-negotiable: the logic lives in
Qt-free modules with headless tests that need no database and no network.

| Module | Responsibility |
|---|---|
| `size_import/categories.py` | `DIMENSIONS`, `build_lookup` (lowest-ID dedup), `resolve`, JSON round-trip |
| `size_import/catalogue.py` | `load_catalogue`, diacritics-insensitive `search` |
| `size_import/basket.py` | `add` / `remove` / `category_ids` / `export_rows` |
| `size_import/export.py` | `export_filename`, `build_workbook`, `to_bytes` |
| `refresh_data.py` | `refresh_catalogue`, `refresh_categories` — plain functions, reusable |

44 tests pass. No logic extraction is needed; the desktop UI sits directly on top.

## Decisions taken

1. **Location:** `desktop/` inside the existing repo `bgal-png/Glasses-Size-Import-Categories`,
   the filler's pattern rather than the validator's separate repo — the four `size_import`
   modules are shared and change together, so a second repo would mean permanent resync.
2. **Data delivery: bundled snapshot + local re-prep.** No snapshot repo, no token, no
   network at startup. Rejected: fetching from the repo with an ETag request, because this
   repo is private and every user would first have to paste a read-only PAT for data the
   user can regenerate locally in fifteen seconds.
3. **Feature scope: straight port.** No persistent basket, no bulk paste. Both were offered
   and declined.
4. **Audience: the user only.** Self-update is still built (pattern non-negotiable) but,
   because release assets of a private repo need authentication, the check reports
   "not configured" until a PAT is set in Settings.

## Data format change: parquet to gzipped CSV

`data/catalogue.parquet` requires pyarrow, which costs roughly 40 MB in the .exe plus
hidden-import trouble — the same cost the filler deliberately avoided. `refresh_data.py`
therefore writes `data/catalogue.csv.gz`, and both the Streamlit app and the desktop app
read that. `data/categories.json` is unchanged.

Parse cost is hidden by `st.cache_data` on the web side and by a parsed pickle cache on
the desktop side.

## Runtime data resolution

`desktop/data_store.py` resolves the snapshot in this order:

1. `%LOCALAPPDATA%\GlassesSizeImport\` — a snapshot the user refreshed locally, alongside
   `catalogue.pkl`, a parsed cache keyed by the source file's mtime and size
2. otherwise the snapshot bundled in the .exe, located via
   `getattr(sys, "_MEIPASS", dirname(__file__))`

Nothing is fetched at startup, so no background thread can outlive the process — the
failure that hung the filler's selftest cannot occur here.

### Refresh from Excel

`🔁 Refresh from Excel…` asks for `Main catalogue.xlsx` and `Glasses size category ids.xlsx`,
then runs `refresh_catalogue` and `refresh_categories` in a `QThread` worker with
`done` / `failed` / `progress` signals, writing into `%LOCALAPPDATA%\GlassesSizeImport\`.
It reports the same counts the CLI prints, and the Data tab keeps them visible:

```
82,690 products - 3 rows skipped
648 category rows - 187 duplicates collapsed (lowest ID kept) - 6 dropped - 455 usable
```

The six dropped rows are listed, not summarised away.

## UI

`QTabWidget` central widget, two tabs, plus a right-hand `QDockWidget` "Control panel"
hidden on the tab that does not use it.

**Tab 1 — Build import**
- Search field; results list of up to 50 matches, diacritics- and hyphen-insensitive
- The selected product's name and global ID shown plainly
- Basket table: Name · Global ID · Sizes · Category IDs

**Tab 2 — Data**
- Which snapshot is loaded (local or bundled) and its age
- Counts from the last refresh and the full dropped-row report

**Control panel dock** (Build import tab only)
- The six dimension fields in `DIMENSIONS` order
- Live resolution under each field: `category 4156`, or the red `#ffb3b3` message
  "No category for Glasses to bend length 118 - will be skipped"
- **Add to basket**, disabled until a product is selected and at least one value entered

**Toolbar** (emoji-prefixed `QAction`s, per the pattern)
`🔁 Refresh from Excel` · `🗑 Remove selected` · `🧹 Clear basket` · `💾 Export import file` ·
`⚙️ Settings` · `⬆️ Check updates` · `🌙 Dark mode`

**Conventions carried over**
- Remove and Clear confirm first, with a count
- Export writes into a folder the user picks, defaulting to `Sizes-<YYMMDD>-import.xlsx`,
  no header row, column A global ID, column B `;`-joined category IDs
- Dark mode: Fusion style plus the house palette, persisted in
  `QSettings("Alensa", "GlassesSizeImport")`
- Indeterminate `QProgressBar` in the status bar during a refresh; coloured status label
  for snapshot state (loading `#a06f00`, ready `#1a7f37`, error `#b30000`)
- Basket table headers copyable by click and by right-click menu
- A non-empty basket marks the title with `•` and prompts on close

The basket stays in memory for the session, as in the web version.

## Build, selftest, shipping

- Build and run from the short-path venv `C:\gv`; the Store Python's path breaks PySide6
- PyInstaller one-file windowed spec: `console=False`,
  `excludes=["tkinter", "matplotlib", "sklearn", "scipy"]`, no pyarrow
- `datas`: the bundled `catalogue.csv.gz`, `categories.json`, and the `.ico`
- `desktop/version.py` plus `desktop/updater.py` ported from the filler, including its
  PowerShell `Wait-Process` swap and `test_updater_swap.py`. Tag prefix `desktop-v`,
  `.exe` attached to the Release. Without a PAT in Settings the check reports
  "not configured" rather than failing
- `--selftest` constructs both tabs headlessly, exits 0, leaves no live thread, and
  reconfigures stdout to UTF-8 (the Windows console is cp1250 and emoji titles raise)
- Icon from an adapted `make_icon.py`: the family's slate-blue glasses with a teal
  measuring accent, wired as both the spec `icon=` and a bundled `.ico` for the window

## Credentials

No token is baked into any build. The optional update PAT lives only in `QSettings`.
Before publishing a build, scan the binary for `ghp_`, `github_pat`, `postgresql://`,
`sk-ant` and the private repo name.

## Testing

- The existing 44 tests keep passing, with the catalogue fixtures moved to `csv.gz`
- New headless tests: a local snapshot wins over the bundled one; the pickle cache is
  rebuilt when the source file changes and reused when it does not; a refresh into a
  temporary directory produces the expected files and counts; the updater swap test
  ported from the filler
- `--selftest` is run and shown before the `.exe` is built

## Deliverables

- `desktop/` in the repo, Streamlit app still working
- A built `.exe`, verified by launching it and exporting one real file
- `HANDOVER_DESKTOP.md`
- A project memory, as written for the other two desktop apps

## Out of scope

- Persistent basket across restarts, bulk paste entry (declined)
- Any snapshot repo, GitHub Action, or database access
- Changes to the import format or the lowest-ID dedup rule
