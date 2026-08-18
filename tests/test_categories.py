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


def test_bool_value_is_dropped():
    lookup, report = build_lookup([(4157, "Glasses size: bridge", True)])
    assert resolve(lookup, "bridge", True) is None
    assert resolve(lookup, "bridge", 1) is None
    assert report["kept"] == 0
    assert report["dropped"] == [(4157, "Glasses size: bridge", True)]


def test_integral_float_value_resolves_same_as_int():
    rows = [
        (4156, "Glasses size: lens width", 55.0),
        (5000, "Glasses size: lens width", 55),
    ]
    lookup, report = build_lookup(rows)
    assert resolve(lookup, "lens_width", 55) == 4156
    assert report["kept"] == 1
    assert report["collapsed"] == 1


def test_non_integral_float_value_is_dropped():
    lookup, report = build_lookup([(34506, "Glasses size: lens height", 26.3)])
    assert resolve(lookup, "lens_height", 26.3) is None
    assert report["kept"] == 0
    assert report["dropped"] == [(34506, "Glasses size: lens height", 26.3)]


def test_build_lookup_of_empty_rows_returns_empty_lookup():
    lookup, report = build_lookup([])
    assert report["kept"] == 0
    assert report["collapsed"] == 0
    assert report["dropped"] == []
    assert resolve(lookup, "lens_width", 55) is None
