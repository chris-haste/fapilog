from __future__ import annotations

from hypothesis import strategies as st

_ASCII_CHARS = st.characters(min_codepoint=32, max_codepoint=126)

json_text = st.text(alphabet=_ASCII_CHARS, max_size=40)
json_key = st.text(alphabet=_ASCII_CHARS, min_size=1, max_size=20)

json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10_000, max_value=10_000),
    st.floats(
        min_value=-1_000_000,
        max_value=1_000_000,
        allow_nan=False,
        allow_infinity=False,
        width=32,
    ),
    json_text,
)

json_values = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=6),
        st.dictionaries(json_key, children, max_size=6),
    ),
    max_leaves=30,
)

json_dicts = st.dictionaries(json_key, json_values, max_size=10)
