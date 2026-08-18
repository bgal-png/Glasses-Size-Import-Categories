# Glasses Size Import Builder

Builds the 2-column import file that attaches size categories to glasses products:
column A = product global ID, column B = global category IDs joined by `;`, no header row.
The file is named `Sizes-<YYMMDD>-import.xlsx`.

## Run

```bash
streamlit run app.py
```

Search a product by name, type the dimensions you know (mm), click **Add to basket**,
repeat for as many products as you need, then **Export**.

Adding the same product again with different values merges into its single row — that is
how a frame sold in two sizes gets both sizes' categories.

## Refresh the data

Run whenever `Main catalogue.xlsx` or `Glasses size category ids.xlsx` is re-exported,
then commit the changed files in `data/`.

```bash
python refresh_data.py
```

Defaults read both workbooks from `C:\Users\blank\Downloads\`. Override with
`--catalogue` and `--categories`.

The script prints what it dropped and how many duplicate categories it collapsed. As of
the last refresh: 82,690 products, 648 category rows in, 187 duplicates collapsed, 6 junk
rows dropped, 455 usable categories.

## Tests

```bash
python -m pytest
```

## Notes

- The import **adds** categories; it does not replace existing ones, so a category the
  product already has simply ends up assigned twice, which is harmless.
- Duplicate `(dimension, value)` categories in the source always resolve to the **lowest**
  ID. Some values have up to eleven IDs.
- A typed value with no matching category (e.g. glasses-to-bend 118) is flagged in the UI
  and left out of the export; the product's other values still export.
- The basket lives in browser session state — refreshing the page clears it.
- Design: `docs/superpowers/specs/2026-08-18-glasses-size-import-design.md`
  Plan: `docs/superpowers/plans/2026-08-18-glasses-size-import.md`
