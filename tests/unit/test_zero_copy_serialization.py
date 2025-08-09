import json
from typing import Any, Dict

import pytest

from fapilog.core.errors import FapilogError
from fapilog.core.events import LogEvent
from fapilog.core.serialization import serialize_mapping_to_json_bytes


def test_log_event_to_mapping_and_zero_copy_bytes_roundtrip() -> None:
    event = LogEvent(level="INFO", message="hello", metadata={"a": 1})

    mapping = event.to_mapping()
    view = serialize_mapping_to_json_bytes(mapping)

    # Expose zero-copy memoryview
    mv = view.view
    assert isinstance(mv, memoryview)
    assert mv.readonly is True or mv.readonly is False  # property exists

    # Roundtrip to Python object to validate structure
    loaded = json.loads(bytes(view).decode("utf-8"))
    assert loaded["level"] == "INFO"
    assert loaded["message"] == "hello"
    assert loaded["metadata"] == {"a": 1}


def test_serializer_handles_pydantic_models_via_default() -> None:
    nested = LogEvent(level="DEBUG", message="nested")
    outer: Dict[str, Any] = {"outer": nested}

    view = serialize_mapping_to_json_bytes(outer)
    loaded = json.loads(bytes(view).decode("utf-8"))
    assert "outer" in loaded
    assert loaded["outer"]["message"] == "nested"


def test_serializer_raises_on_unknown_types() -> None:
    class NotSerializable:
        pass

    with pytest.raises(FapilogError):
        serialize_mapping_to_json_bytes({"bad": NotSerializable()})


def test_memory_usage_callback_invoked() -> None:
    event = LogEvent(level="INFO", message="cb")
    mapping = event.to_mapping()

    captured: list[int] = []

    def observer(n: int) -> None:
        captured.append(n)

    _ = serialize_mapping_to_json_bytes(mapping, on_memory_usage_bytes=observer)

    assert len(captured) == 1
    assert captured[0] > 0
