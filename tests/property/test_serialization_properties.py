from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fapilog.core.serialization import (
    serialize_envelope,
    serialize_mapping_to_json_bytes,
)

from .strategies import json_dicts, json_key, json_values

pytestmark = pytest.mark.property

_TIMESTAMP_MAX = 4_102_444_800.0  # 2100-01-01 UTC

message_text = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=1,
    max_size=120,
)

envelope_logs = st.fixed_dictionaries(
    {
        "timestamp": st.floats(
            min_value=0,
            max_value=_TIMESTAMP_MAX,
            allow_nan=False,
            allow_infinity=False,
        ),
        "level": st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
        "message": message_text,
        "context": st.dictionaries(json_key, json_values, max_size=6),
        "diagnostics": st.dictionaries(json_key, json_values, max_size=6),
    },
    optional={
        "tags": st.lists(message_text, max_size=5),
        "span_id": message_text,
        "trace_id": message_text,
        "logger": message_text,
    },
)


@given(payload=json_dicts)
@settings(max_examples=200)
def test_json_serialization_round_trip(payload: dict) -> None:
    view = serialize_mapping_to_json_bytes(payload)
    parsed = json.loads(view.data)
    assert parsed == payload


@given(event=envelope_logs)
@settings(max_examples=200)
def test_serialize_envelope_preserves_required_fields(event: dict) -> None:
    view = serialize_envelope(event)
    parsed = json.loads(view.data)

    assert parsed["schema_version"] == "1.0"
    log = parsed["log"]

    assert log["level"] == str(event["level"])
    assert log["message"] == str(event["message"])
    assert log["context"] == event["context"]
    assert log["diagnostics"] == event["diagnostics"]
    assert log["timestamp"].endswith("Z")
