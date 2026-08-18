"""The six glasses size dimensions and the value -> category ID lookup.

The source workbook contains duplicate categories for the same (dimension, value)
pair - up to eleven IDs for `lens height 51`. The rule, matching how the user
assigns them by hand, is to keep the lowest ID.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dimension:
    key: str
    source_name: str
    label: str


DIMENSIONS = [
    Dimension("glasses_width", "Glasses size: glasses width", "Glasses width"),
    Dimension("lens_width", "Glasses size: lens width", "Lens width"),
    Dimension("lens_height", "Glasses size: lens height", "Lens height"),
    Dimension("bridge", "Glasses size: bridge", "Bridge"),
    Dimension("temple_length", "Glasses size: temple length", "Temple length"),
    Dimension(
        "to_bend_length",
        "Glasses size: glasses to bend length",
        "Glasses to bend length",
    ),
]

BY_SOURCE_NAME = {dimension.source_name: dimension for dimension in DIMENSIONS}


def _coerce_value(value):
    """Return value as an int if it represents a whole number, else None.

    Accepts plain ints and integral floats (e.g. `55.0` -> `55`, as openpyxl
    may return for numeric cells). Rejects bool, non-integral floats, strings,
    None and anything else.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _is_usable(category_id, dimension, value):
    if category_id is None or dimension is None:
        return False
    if _coerce_value(value) is None:
        return False
    return True


def build_lookup(rows):
    """Build {dimension key: {value: category ID}} from raw (id, name, value) rows.

    Returns (lookup, report). The report carries the dropped rows verbatim and a
    count of duplicates collapsed, so the prep script can print what it discarded.
    """
    lookup = {dimension.key: {} for dimension in DIMENSIONS}
    dropped = []
    collapsed = 0

    for category_id, source_name, value in rows:
        dimension = BY_SOURCE_NAME.get(source_name)
        if not _is_usable(category_id, dimension, value):
            dropped.append((category_id, source_name, value))
            continue

        coerced_value = _coerce_value(value)
        bucket = lookup[dimension.key]
        if coerced_value in bucket:
            collapsed += 1
            bucket[coerced_value] = min(bucket[coerced_value], category_id)
        else:
            bucket[coerced_value] = category_id

    report = {
        "kept": sum(len(bucket) for bucket in lookup.values()),
        "collapsed": collapsed,
        "dropped": dropped,
    }
    return lookup, report


def resolve(lookup, key, value):
    """Category ID for one dimension value, or None if no category exists."""
    return lookup.get(key, {}).get(value)


def to_json_dict(lookup):
    """JSON needs string keys; convert {value: id} to {"value": id}."""
    return {
        key: {str(value): category_id for value, category_id in bucket.items()}
        for key, bucket in lookup.items()
    }


def from_json_dict(raw):
    """Reverse of to_json_dict: convert string keys back to integer values."""
    return {
        key: {int(value): category_id for value, category_id in bucket.items()}
        for key, bucket in raw.items()
    }
