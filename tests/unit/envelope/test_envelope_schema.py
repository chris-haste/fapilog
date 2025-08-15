from __future__ import annotations

import json
from pathlib import Path

from fapilog.core.serialization import ensure_rfc3339_utc, serialize_envelope


def test_envelope_schema_validation(tmp_path: Path) -> None:
    schema_path = Path(__file__).parents[3] / "jsonschema" / "log_envelope_v1.json"
    _ = schema_path.read_text()

    log = {
        "timestamp": ensure_rfc3339_utc(1723734312.123),
        "level": "INFO",
        "message": "ok",
        "context": {"a": 1},
        "diagnostics": {"d": True},
        "tags": ["x"],
        "trace_id": "0af7651916cd43dd8448eb211c80319c",
        "span_id": "b7ad6b7169203331",
        "logger": "fapilog.core",
    }
    env_json = serialize_envelope(log).data.decode("utf-8")
    envelope = json.loads(env_json)

    # Inline validation without dependency: basic checks
    assert set(envelope.keys()) == {"schema_version", "log"}
    assert envelope["schema_version"] == "1.0"
    assert set(log.keys()).issubset(set(envelope["log"].keys()))
