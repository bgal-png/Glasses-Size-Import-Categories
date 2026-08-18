# tests/test_catalogue.py
import pandas as pd

from size_import.catalogue import load_catalogue, normalize, search

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


def test_nan_name_produces_empty_search_key_and_does_not_match():
    frame = CATALOGUE.copy()
    frame.loc[len(frame)] = [float("nan"), 999]
    frame["search_key"] = frame["name"].map(normalize)
    assert frame.loc[frame["globalId"] == 999, "search_key"].iloc[0] == ""
    result = search(frame, "nan")
    assert 999 not in list(result["globalId"])


def test_query_with_regex_metacharacters_does_not_raise_and_finds_nothing():
    result = search(_prepared(), "g5063 (")
    assert list(result["globalId"]) == []
    result = search(_prepared(), "rb4165+")
    assert list(result["globalId"]) == []


def test_load_catalogue_end_to_end(tmp_path):
    path = tmp_path / "catalogue.parquet"
    CATALOGUE.to_parquet(path)
    frame = load_catalogue(path)
    result = search(frame, "ray-ban aviator")
    assert list(result["globalId"]) == [245002]
