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
    monkeypatch.setattr(data_store, "cache_dir", lambda *parts: str(tmp_path / "cache"))
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
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
