import pytest

from fapilog.core.events import LogEvent
from fapilog.core.serialization import (
    SegmentedSerialized,
    convert_json_bytes_to_jsonl,
    serialize_custom_fapilog_v1,
    serialize_mapping_to_json_bytes,
    serialize_protobuf_like,
)


class DummyProto:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def SerializeToString(self) -> bytes:  # noqa: N802 - protobuf style
        return self._data


@pytest.mark.asyncio
async def test_json_to_jsonl_segmented() -> None:
    evt = LogEvent(level="INFO", message="segmented")
    view = serialize_mapping_to_json_bytes(evt.to_mapping())
    seg = convert_json_bytes_to_jsonl(view)
    assert isinstance(seg, SegmentedSerialized)
    # Ensure newline added without copying original segment
    combined = seg.to_bytes()
    assert combined.endswith(b"\n")


def test_protobuf_like_serialization() -> None:
    payload = b"abc"
    pb = DummyProto(payload)
    view = serialize_protobuf_like(pb)
    assert bytes(view) == payload


def test_custom_framed_format() -> None:
    evt = LogEvent(level="INFO", message="frame")
    view = serialize_custom_fapilog_v1(evt.to_mapping())
    data = bytes(view)
    # 4-byte header + json
    length = int.from_bytes(data[:4], "big")
    assert length == len(data) - 4
    assert b'"message":"frame"' in data
