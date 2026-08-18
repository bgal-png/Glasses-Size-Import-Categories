# tests/test_refresh_data.py
"""refresh_catalogue must read name/globalId from the exact column offsets
(column C / index 2, column CZ / index 103) of a 104-column workbook, and
skip rows missing either value."""

import openpyxl
import pandas as pd

from refresh_data import refresh_catalogue

NAME_COLUMN = 2
GLOBAL_ID_COLUMN = 103
TOTAL_COLUMNS = 104


def _make_row(name=None, global_id=None, decoy="decoy"):
    """Build a full-width row with `name`/`global_id` at their real offsets and
    a recognisable decoy value everywhere else, so a wrong column offset would
    pick up the decoy instead and the test would fail."""
    row = [decoy] * TOTAL_COLUMNS
    row[NAME_COLUMN] = name
    row[GLOBAL_ID_COLUMN] = global_id
    return row


def _build_workbook(path, rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    header = [f"col{i}" for i in range(TOTAL_COLUMNS)]
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_extracts_name_and_global_id_from_correct_columns(tmp_path):
    source = tmp_path / "catalogue.xlsx"
    destination = tmp_path / "catalogue.parquet"
    rows = [
        _make_row(name="Crulle G5063", global_id=1001),
        _make_row(name="Ray-Ban RB2140", global_id=1002),
    ]
    _build_workbook(source, rows)

    refresh_catalogue(source, destination)

    frame = pd.read_parquet(destination)
    pairs = set(zip(frame["name"], frame["globalId"]))
    assert pairs == {("Crulle G5063", 1001), ("Ray-Ban RB2140", 1002)}
    assert list(frame.columns) == ["name", "globalId"]


def test_row_missing_global_id_is_skipped(tmp_path):
    source = tmp_path / "catalogue.xlsx"
    destination = tmp_path / "catalogue.parquet"
    rows = [
        _make_row(name="Has both", global_id=2001),
        _make_row(name="No global id", global_id=None),
    ]
    _build_workbook(source, rows)

    refresh_catalogue(source, destination)

    frame = pd.read_parquet(destination)
    assert len(frame) == 1
    assert frame.iloc[0]["name"] == "Has both"
    assert int(frame.iloc[0]["globalId"]) == 2001


def test_row_missing_name_is_skipped(tmp_path):
    source = tmp_path / "catalogue.xlsx"
    destination = tmp_path / "catalogue.parquet"
    rows = [
        _make_row(name=None, global_id=3001),
        _make_row(name="Has both", global_id=3002),
    ]
    _build_workbook(source, rows)

    refresh_catalogue(source, destination)

    frame = pd.read_parquet(destination)
    assert len(frame) == 1
    assert frame.iloc[0]["name"] == "Has both"
    assert int(frame.iloc[0]["globalId"]) == 3002


def test_skipped_count_matches_printed_summary(tmp_path, capsys):
    source = tmp_path / "catalogue.xlsx"
    destination = tmp_path / "catalogue.parquet"
    rows = [
        _make_row(name="Kept one", global_id=4001),
        _make_row(name="Kept two", global_id=4002),
        _make_row(name=None, global_id=4003),
        _make_row(name="No id", global_id=None),
        _make_row(name=None, global_id=None),
    ]
    _build_workbook(source, rows)

    refresh_catalogue(source, destination)

    captured = capsys.readouterr()
    frame = pd.read_parquet(destination)
    assert len(frame) == 2
    assert "catalogue: 2 products" in captured.out
    assert "catalogue: 3 rows skipped (no name or no globalId)" in captured.out
