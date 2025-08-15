from __future__ import annotations

import pytest

from fapilog.core.serialization import ensure_rfc3339_utc


def test_ensure_rfc3339_from_offset() -> None:
    # Offset +02:00 should be converted to UTC Z with milliseconds
    s = ensure_rfc3339_utc("2025-08-15T12:34:56+02:00")
    assert s.endswith("Z") and "T" in s
    # 12:34:56+02:00 -> 10:34:56Z
    # Milliseconds should be present even if input lacked them
    assert "T10:34:56.000Z" in s


def test_ensure_rfc3339_invalid_raises() -> None:
    with pytest.raises(TypeError):
        ensure_rfc3339_utc("not-a-timestamp")
