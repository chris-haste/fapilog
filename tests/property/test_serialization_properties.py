from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fapilog.core.envelope import build_envelope
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
        "data": st.dictionaries(json_key, json_values, max_size=6),
    },
    optional={
        "tags": st.lists(message_text, max_size=5),
        "logger": message_text,
    },
)


@given(payload=json_dicts)
def test_json_serialization_round_trip(payload: dict) -> None:
    view = serialize_mapping_to_json_bytes(payload)
    parsed = json.loads(view.data)
    assert parsed == payload


@given(event=envelope_logs)
def test_serialize_envelope_preserves_required_fields(event: dict) -> None:
    view = serialize_envelope(event)
    parsed = json.loads(view.data)

    assert parsed["schema_version"] == "1.1"
    log = parsed["log"]

    assert log["level"] == str(event["level"])
    assert log["message"] == str(event["message"])
    assert log["context"] == event["context"]
    assert log["diagnostics"] == event["diagnostics"]
    assert log["data"] == event["data"]
    assert log["timestamp"].endswith("Z")


# Contract property test: uses real build_envelope() output
@given(
    level=st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    message=st.text(min_size=1, max_size=200),
    extra=st.dictionaries(
        st.text(min_size=1, max_size=20).filter(lambda x: x.isidentifier()),
        st.text(max_size=50),
        max_size=5,
    ),
)
def test_build_then_serialize_never_raises(
    level: str, message: str, extra: dict[str, str]
) -> None:
    """Property: serialize_envelope(build_envelope(...)) never raises.

    This contract property test verifies that the producer/consumer contract
    holds for any valid input combination. Unlike synthetic envelope_logs
    strategy, this uses actual build_envelope() output.

    If this test fails, schemas have drifted between build_envelope() and
    serialize_envelope(). See Story 10.17 for context.
    """
    envelope = build_envelope(level=level, message=message, extra=extra)

    # Must not raise for any valid input combination
    view = serialize_envelope(envelope)
    parsed = json.loads(view.data)
    assert parsed["schema_version"] == "1.1"
    assert parsed["log"]["level"] == level


@given(
    level=st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    message=st.text(min_size=1, max_size=200),
    correlation_id=st.text(min_size=1, max_size=36).filter(lambda x: x.strip()),
    logger_name=st.text(min_size=1, max_size=50).filter(lambda x: x.isidentifier()),
)
def test_build_with_options_then_serialize_never_raises(
    level: str, message: str, correlation_id: str, logger_name: str
) -> None:
    """Property: build_envelope() with all options produces valid output.

    Tests the roundtrip with correlation_id and logger_name options.
    """
    envelope = build_envelope(
        level=level,
        message=message,
        correlation_id=correlation_id,
        logger_name=logger_name,
    )

    view = serialize_envelope(envelope)
    parsed = json.loads(view.data)
    assert parsed["schema_version"] == "1.1"
    assert parsed["log"]["logger"] == logger_name
