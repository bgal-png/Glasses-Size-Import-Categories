# app.py
"""Glasses Size Import Builder - search a product, type its dimensions, export."""

import datetime
import json
from pathlib import Path

import streamlit as st

from size_import import basket as basket_module
from size_import.catalogue import load_catalogue, search
from size_import.categories import DIMENSIONS, from_json_dict, resolve
from size_import.export import export_filename, to_bytes

DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(page_title="Glasses Size Import", page_icon="👓", layout="wide")


@st.cache_data
def get_catalogue():
    return load_catalogue(DATA_DIR / "catalogue.parquet")


@st.cache_data
def get_lookup():
    raw = json.loads((DATA_DIR / "categories.json").read_text(encoding="utf-8"))
    return from_json_dict(raw)


catalogue = get_catalogue()
lookup = get_lookup()

if "basket" not in st.session_state:
    st.session_state.basket = {}

# Bumped after every add. It is part of every number_input key, which is how the
# fields get cleared - Streamlit forbids writing to a widget's session state after
# that widget has been instantiated, so a fresh key is the way to reset them.
if "field_nonce" not in st.session_state:
    st.session_state.field_nonce = 0

st.title("Glasses Size Import Builder")

# --- Zone 1: pick a product ------------------------------------------------
st.subheader("1. Product")
query = st.text_input("Search by name", placeholder="e.g. crulle g5063")

selected_id = None
selected_name = None

if query:
    matches = search(catalogue, query, limit=50)
    if matches.empty:
        st.warning("No product matches that name.")
    else:
        options = list(matches.itertuples(index=False))
        label = f"{len(options)} match(es)"
        if len(options) == 50:
            label += " - showing first 50, refine the search if needed"
        choice = st.selectbox(
            label,
            options,
            format_func=lambda row: f"{row.name} - {row.globalId}",
        )
        selected_id = int(choice.globalId)
        selected_name = str(choice.name)
        st.caption(f"Global ID: **{selected_id}**")

# --- Zone 2: dimensions ----------------------------------------------------
st.subheader("2. Dimensions (mm)")
columns = st.columns(3)
values = {}

for index, dimension in enumerate(DIMENSIONS):
    with columns[index % 3]:
        entered = st.number_input(
            dimension.label,
            min_value=0,
            max_value=300,
            value=0,
            step=1,
            key=f"input_{dimension.key}_{st.session_state.field_nonce}",
        )
        if entered:
            values[dimension.key] = int(entered)
            category_id = resolve(lookup, dimension.key, int(entered))
            if category_id is None:
                st.error(f"No category for {entered} - will be skipped")
            else:
                st.caption(f"category {category_id}")

add_disabled = selected_id is None or not values
if st.button("Add to basket", type="primary", disabled=add_disabled):
    st.session_state.basket = basket_module.add(
        st.session_state.basket, selected_id, selected_name, values
    )
    st.session_state.field_nonce += 1
    st.rerun()

if selected_id is None:
    st.caption("Pick a product first.")
elif not values:
    st.caption("Enter at least one dimension.")

# --- Zone 3: basket --------------------------------------------------------
st.subheader("3. Basket")
current = st.session_state.basket

if not current:
    st.info("Basket is empty.")
else:
    for global_id, entry in list(current.items()):
        ids = basket_module.category_ids(entry, lookup)
        left, right = st.columns([9, 1])
        with left:
            sizes = " | ".join(
                ", ".join(
                    f"{dimension.label} {value_set[dimension.key]}"
                    for dimension in DIMENSIONS
                    if dimension.key in value_set
                )
                for value_set in entry["value_sets"]
            )
            st.markdown(f"**{entry['name']}** - `{global_id}`")
            st.caption(sizes)
            st.code(";".join(str(value) for value in ids), language=None)
        with right:
            if st.button("Remove", key=f"remove_{global_id}"):
                st.session_state.basket = basket_module.remove(current, global_id)
                st.rerun()

    rows = basket_module.export_rows(current, lookup)
    st.download_button(
        f"Export {len(rows)} product(s)",
        data=to_bytes(rows),
        file_name=export_filename(datetime.date.today()),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        disabled=not rows,
    )
