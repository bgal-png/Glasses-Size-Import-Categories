"""Loading and searching the slim product catalogue."""

import unicodedata

import pandas as pd


def normalize(text):
    """Lowercase, trimmed, diacritics removed - so `crulle` finds `Crullé`."""
    if text is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().strip()


def load_catalogue(path):
    """Read catalogue.parquet and attach the precomputed search key column."""
    frame = pd.read_parquet(path)
    frame["search_key"] = frame["name"].map(normalize)
    return frame


def search(frame, query, limit=50):
    """Products whose name contains every token of the query, in any order."""
    tokens = [token for token in normalize(query).replace("-", " ").split() if token]
    if not tokens:
        return frame.head(0)

    keys = frame["search_key"].str.replace("-", " ", regex=False)
    mask = pd.Series(True, index=frame.index)
    for token in tokens:
        mask &= keys.str.contains(token, regex=False, na=False)
    return frame[mask].head(limit)
