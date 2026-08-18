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
