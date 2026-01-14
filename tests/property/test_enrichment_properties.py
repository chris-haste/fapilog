from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fapilog.plugins.enrichers import enrich_parallel

from .strategies import json_values

pytestmark = pytest.mark.property

_key_chars = st.characters(min_codepoint=97, max_codepoint=122)


def prefixed_dict(prefix: str) -> st.SearchStrategy[dict[str, object]]:
    keys = st.text(alphabet=_key_chars, min_size=1, max_size=8).map(
        lambda value: f"{prefix}{value}"
    )
    return st.dictionaries(keys, json_values, max_size=6)


class _StaticEnricher:
    name = "static"

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    async def enrich(self, event: dict) -> dict:
        return dict(self._payload)


@pytest.mark.asyncio
@given(event=prefixed_dict("orig_"), extra=prefixed_dict("extra_"))
async def test_enrichment_preserves_original_fields(
    event: dict[str, object], extra: dict[str, object]
) -> None:
    enricher = _StaticEnricher(extra)
    original = dict(event)

    enriched = await enrich_parallel(event, [enricher])

    for key, value in original.items():
        assert enriched[key] == value
    for key, value in extra.items():
        assert enriched[key] == value

    assert event == original
