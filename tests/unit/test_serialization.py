from __future__ import annotations

import json
from typing import Any

import pytest

from fapilog.core.errors import ErrorCategory, FapilogError
from fapilog.core.serialization import (
    SegmentedSerialized,
    SerializedView,
    convert_json_bytes_to_jsonl,
    serialize_custom_fapilog_v1,
    serialize_mapping_to_json_bytes,
    serialize_protobuf_like,
)


def test_serialize_mapping_to_json_bytes_basic_and_callback() -> None:
    payload = {"a": 1, "b": "x"}
    called: list[int] = []

    def on_mem(n: int) -> None:
        called.append(n)

    view: SerializedView = serialize_mapping_to_json_bytes(
        payload, on_memory_usage_bytes=on_mem
    )
    assert isinstance(view.data, (bytes, bytearray))
    # round-trip with stdlib json
    obj = json.loads(view.data)
    assert obj == payload
    assert called and called[0] == len(view.data)


def test_serialize_mapping_to_json_bytes_callback_error_swallowed() -> None:
    payload = {"k": "v"}

    def bad_cb(_n: int) -> None:
        raise RuntimeError("boom")

    # Should not raise
    view = serialize_mapping_to_json_bytes(payload, on_memory_usage_bytes=bad_cb)
    assert json.loads(view.data) == payload


def test_serialize_mapping_with_model_dump_object() -> None:
    class HasModelDump:
        def model_dump(self, exclude_none: bool = True) -> dict[str, Any]:
            return {"z": 3}

    view = serialize_mapping_to_json_bytes({"obj": HasModelDump()})
    assert json.loads(view.data) == {"obj": {"z": 3}}


def test_serialize_mapping_non_serializable_raises() -> None:
    class NotSerializable:
        pass

    with pytest.raises(FapilogError) as ei:
        _ = serialize_mapping_to_json_bytes({"x": NotSerializable()})
    err = ei.value
    assert isinstance(err, FapilogError)
    assert err.context.category == ErrorCategory.SERIALIZATION


def test_serialize_protobuf_like_variants() -> None:
    class WithSerializeToString:
        def SerializeToString(self) -> bytes:  # noqa: N802
            return b"abc"

    class WithToBytes:
        def to_bytes(self) -> bytes:
            return b"def"

    v1 = serialize_protobuf_like(WithSerializeToString())
    assert v1.data == b"abc"
    v2 = serialize_protobuf_like(WithToBytes())
    assert v2.data == b"def"
    v3 = serialize_protobuf_like(b"ghi")
    assert v3.data == b"ghi"
    v4 = serialize_protobuf_like(memoryview(b"jkl"))
    assert v4.data == b"jkl"

    with pytest.raises(FapilogError) as ei:
        _ = serialize_protobuf_like(object())
    assert ei.value.context.category == ErrorCategory.SERIALIZATION


def test_convert_json_bytes_to_jsonl_no_copy_and_segmented() -> None:
    view = serialize_mapping_to_json_bytes({"a": 1})
    seg: SegmentedSerialized = convert_json_bytes_to_jsonl(view)
    # Segments should represent original bytes + newline without copying
    seg_bytes = seg.to_bytes()
    assert seg_bytes.endswith(b"\n")
    assert seg.total_length == len(seg_bytes)
    # First segment equals original JSON, second is newline
    parts = list(seg.iter_memoryviews())
    assert len(parts) == 2
    assert bytes(parts[0]) == view.data
    assert bytes(parts[1]) == b"\n"


def test_serialize_custom_fapilog_v1_length_prefixed() -> None:
    payload = {"m": "n"}
    json_view = serialize_mapping_to_json_bytes(payload)
    framed = serialize_custom_fapilog_v1(payload)
    data = framed.data
    assert len(data) >= 5
    length = int.from_bytes(data[:4], byteorder="big", signed=False)
    assert length == len(json_view.data)
    assert data[4:] == json_view.data
