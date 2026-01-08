from __future__ import annotations

import json

from fapilog.core.serialization import (
    convert_json_bytes_to_jsonl,
    serialize_custom_fapilog_v1,
    serialize_mapping_to_json_bytes,
    serialize_protobuf_like,
)


def test_serialize_protobuf_like_bytes_and_memoryview() -> None:
    out1 = serialize_protobuf_like(b"abc")
    assert bytes(out1) == b"abc"

    mv = memoryview(b"xyz")
    out2 = serialize_protobuf_like(mv)
    assert bytes(out2) == b"xyz"


def test_serialize_custom_fapilog_v1_header_and_payload() -> None:
    payload = {"b": 2, "a": 1}
    framed = serialize_custom_fapilog_v1(payload)
    data = bytes(framed)
    assert len(data) >= 4
    length = int.from_bytes(data[:4], byteorder="big", signed=False)
    body = data[4:]
    assert length == len(body)
    # Body is JSON with sorted keys
    parsed = json.loads(body)
    assert parsed["a"] == 1 and parsed["b"] == 2


def test_convert_json_bytes_to_jsonl_roundtrip() -> None:
    view = serialize_mapping_to_json_bytes({"k": "v"})
    seg = convert_json_bytes_to_jsonl(view)
    buf = seg.to_bytes()
    assert buf.endswith(b"\n")
