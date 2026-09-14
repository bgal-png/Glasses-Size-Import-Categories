# refresh_data.py
r"""Convert the source workbooks into the slim data files the app reads.

Run locally whenever either source export changes, then commit data/.

    python refresh_data.py
"""

import argparse
import json
import os
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
    destination = Path(destination)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    frame.to_csv(temporary, index=False, compression="gzip", encoding="utf-8")
    os.replace(temporary, destination)

    report = {"products": len(frame), "skipped": skipped, "destination": str(destination)}
    print(f"catalogue: {report['products']} products -> {destination}")
    print(f"catalogue: {report['skipped']} rows skipped (no name or no globalId)")
    return report


def refresh_categories(source, destination):
    """Build the deduped category lookup as JSON. Returns a report dict."""
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]

    rows = [row[:3] for row in sheet.iter_rows(min_row=2, values_only=True) if row[0]]
    lookup, build_report = build_lookup(rows)

    # Refuse to write an empty lookup. A locally refreshed file always wins over
    # the bundled one, so saving zero categories here would leave the app unable
    # to resolve anything until the file is deleted by hand. Reaching zero means
    # the wrong workbook was picked, not that the categories are gone.
    if build_report["kept"] == 0:
        raise ValueError(
            f"{source} has no 'Glasses size:' categories in it ({len(rows)} rows read). "
            "That is not the category workbook - nothing was changed."
        )

    destination = Path(destination)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(to_json_dict(lookup), indent=1, sort_keys=True), encoding="utf-8"
    )
    os.replace(temporary, destination)

    report = {
        "rows": len(rows),
        "collapsed": build_report["collapsed"],
        "dropped": build_report["dropped"],
        "kept": build_report["kept"],
        "destination": str(destination),
    }
    print(f"categories: {report['rows']} rows read")
    print(f"categories: {report['collapsed']} duplicates collapsed (lowest ID kept)")
    print(f"categories: {len(report['dropped'])} rows dropped:")
    for category_id, name, value in report["dropped"]:
        print(f"  - id={category_id} name={name!r} value={value!r}")
    print(f"categories: {report['kept']} usable categories -> {destination}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Refresh the slim data files.")
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--categories", type=Path, default=DEFAULT_CATEGORIES)
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    refresh_catalogue(args.catalogue, DATA_DIR / "catalogue.csv.gz")
    refresh_categories(args.categories, DATA_DIR / "categories.json")


if __name__ == "__main__":
    main()
