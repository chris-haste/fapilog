from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from fapilog.core.serialization import ensure_rfc3339_utc, serialize_envelope


@pytest.mark.parametrize(
    "ts",
    [
        1723734312.123,
        datetime(2025, 8, 15, 12, 34, 56, 123000, tzinfo=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    ],
)
def test_envelope_invariants(ts) -> None:
    log = {
        "timestamp": ensure_rfc3339_utc(ts),
        "level": "INFO",
        "message": "ok",
        "context": {},
        "diagnostics": {},
    }
    env = json.loads(serialize_envelope(log).data)
    assert set(env.keys()) == {"schema_version", "log"}
    assert env["schema_version"] == "1.0"
    assert env["log"]["timestamp"].endswith("Z") and "T" in env["log"]["timestamp"]
    assert env["log"]["level"] == "INFO"
    assert env["log"]["message"] == "ok"
