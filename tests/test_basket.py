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
