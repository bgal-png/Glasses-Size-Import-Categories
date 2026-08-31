"""Loading and searching the slim product catalogue."""

import unicodedata

import pandas as pd


def normalize(text):
    """Lowercase, trimmed, diacritics removed, hyphens treated as spaces -

    so `crulle` finds `Crullé` and `ray ban` finds `Ray-Ban`.
    """
    if pd.isna(text):
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().replace("-", " ").strip()


def load_catalogue(path):
    """Read catalogue.csv.gz and attach the precomputed search key column.

    Gzipped CSV rather than parquet on purpose: parquet drags pyarrow (~40 MB)
    into the desktop .exe for no gain, since the desktop app caches the parsed
    frame as a pickle anyway.
    """
    frame = pd.read_csv(path, compression="gzip", encoding="utf-8")
    frame["globalId"] = frame["globalId"].astype("int64")
    frame["search_key"] = frame["name"].map(normalize)
    return frame


def search(frame, query, limit=50):
    """Products whose name contains every token of the query, in any order."""
    tokens = [token for token in normalize(query).split() if token]
    if not tokens:
        return frame.head(0)

    keys = frame["search_key"]
    mask = pd.Series(True, index=frame.index)
    for token in tokens:
        mask &= keys.str.contains(token, regex=False, na=False)
    return frame[mask].head(limit)
