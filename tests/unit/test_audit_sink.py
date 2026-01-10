from __future__ import annotations

import json
from pathlib import Path

import pytest

from fapilog.core.audit import AuditEventType
from fapilog.plugins import loader
from fapilog.plugins.sinks.audit import AuditSink, AuditSinkConfig

pytestmark = pytest.mark.security


def test_audit_sink_is_registered() -> None:
    names = loader.list_available_plugins("fapilog.sinks")
    assert "audit" in names
    assert "audit" in {n.replace("-", "_") for n in names}


@pytest.mark.asyncio
async def test_audit_sink_writes_and_verifies_chain(tmp_path: Path) -> None:
    sink = AuditSink(
        AuditSinkConfig(
            storage_path=str(tmp_path),
            compliance_level="sox",
            require_integrity=True,
        )
    )

    await sink.start()
    await sink.write(
        {
            "level": "ERROR",
            "message": "access denied",
            "logger": "auth",
            "metadata": {
                "user_id": "user-123",
                "contains_pii": True,
            },
        }
    )
    await sink.write(
        {
            "level": "INFO",
            "message": "read customer record",
            "logger": "crm",
            "metadata": {"audit_event_type": AuditEventType.DATA_ACCESS},
        }
    )
    await sink.stop()

    trail = sink._trail
    assert trail is not None

    verification = await trail.verify_chain_from_storage()
    assert verification.valid

    # Protocol-compliant health_check returns bool
    assert await sink.health_check() is True

    # Direct access to trail stats for monitoring/compliance
    stats = await trail.get_statistics()
    assert stats["total_events"] == 2
    assert stats["policy"]["compliance_level"] == "sox"

    files = list(tmp_path.glob("audit_*.jsonl"))
    assert files, "expected audit log file to be written"
    with open(files[0], encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    event_types = {e["event_type"] for e in events}
    assert AuditEventType.ERROR_OCCURRED in event_types
    assert AuditEventType.DATA_ACCESS in event_types


@pytest.mark.asyncio
async def test_health_check_before_start_returns_false() -> None:
    """health_check() should return False when sink not started."""
    sink = AuditSink()
    assert await sink.health_check() is False


@pytest.mark.asyncio
async def test_write_before_start_is_noop(tmp_path: Path) -> None:
    """write() should silently return when sink not started."""
    sink = AuditSink(AuditSinkConfig(storage_path=str(tmp_path)))
    # Should not raise
    await sink.write({"level": "INFO", "message": "ignored"})
    # No files should be created
    files = list(tmp_path.glob("audit_*.jsonl"))
    assert not files


@pytest.mark.asyncio
async def test_empty_message_is_accepted(tmp_path: Path) -> None:
    """Sink should accept entries with empty message."""
    sink = AuditSink(AuditSinkConfig(storage_path=str(tmp_path)))
    await sink.start()
    await sink.write({"level": "INFO", "message": "", "logger": "test"})
    await sink.stop()

    files = list(tmp_path.glob("audit_*.jsonl"))
    assert files
    with open(files[0], encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    assert len(events) == 1
    assert events[0]["message"] == ""


@pytest.mark.asyncio
async def test_invalid_compliance_level_falls_back_to_basic(tmp_path: Path) -> None:
    """Invalid compliance_level should fall back to BASIC without error."""
    sink = AuditSink(
        AuditSinkConfig(
            storage_path=str(tmp_path),
            compliance_level="invalid_level",
        )
    )
    await sink.start()
    await sink.write({"level": "INFO", "message": "test"})

    # Verify fallback via trail stats
    assert sink._trail is not None
    stats = await sink._trail.get_statistics()
    assert stats["policy"]["compliance_level"] == "basic"

    await sink.stop()


@pytest.mark.asyncio
async def test_stop_is_idempotent(tmp_path: Path) -> None:
    """Calling stop() multiple times should not raise."""
    sink = AuditSink(AuditSinkConfig(storage_path=str(tmp_path)))
    await sink.start()
    await sink.write({"level": "INFO", "message": "test"})

    # First stop
    await sink.stop()
    # Second stop should not raise
    await sink.stop()
    # Third stop should not raise
    await sink.stop()


@pytest.mark.asyncio
async def test_start_is_idempotent(tmp_path: Path) -> None:
    """Calling start() multiple times should not recreate the trail."""
    sink = AuditSink(AuditSinkConfig(storage_path=str(tmp_path)))
    await sink.start()
    trail_after_first_start = sink._trail

    await sink.start()
    trail_after_second_start = sink._trail

    assert trail_after_first_start is trail_after_second_start
    await sink.stop()


@pytest.mark.asyncio
async def test_event_type_override_via_metadata(tmp_path: Path) -> None:
    """audit_event_type in metadata should override automatic mapping."""
    sink = AuditSink(AuditSinkConfig(storage_path=str(tmp_path)))
    await sink.start()
    await sink.write(
        {
            "level": "INFO",  # Would normally map to DATA_ACCESS
            "message": "security check",
            "metadata": {"audit_event_type": "security_violation"},
        }
    )
    await sink.stop()

    files = list(tmp_path.glob("audit_*.jsonl"))
    with open(files[0], encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    assert events[0]["event_type"] == "security_violation"


@pytest.mark.asyncio
async def test_warning_level_maps_to_compliance_check(tmp_path: Path) -> None:
    """WARNING level should map to COMPLIANCE_CHECK event type."""
    sink = AuditSink(AuditSinkConfig(storage_path=str(tmp_path)))
    await sink.start()
    await sink.write({"level": "WARNING", "message": "policy warning"})
    await sink.stop()

    files = list(tmp_path.glob("audit_*.jsonl"))
    with open(files[0], encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    assert events[0]["event_type"] == "compliance_check"


@pytest.mark.asyncio
async def test_metadata_fields_propagated(tmp_path: Path) -> None:
    """Metadata fields like user_id, session_id, contains_pii should propagate."""
    sink = AuditSink(AuditSinkConfig(storage_path=str(tmp_path)))
    await sink.start()
    await sink.write(
        {
            "level": "INFO",
            "message": "data access",
            "correlation_id": "req-123",
            "metadata": {
                "user_id": "user-abc",
                "session_id": "sess-xyz",
                "contains_pii": True,
                "contains_phi": True,
                "data_classification": "confidential",
            },
        }
    )
    await sink.stop()

    files = list(tmp_path.glob("audit_*.jsonl"))
    with open(files[0], encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]

    event = events[0]
    assert event["user_id"] == "user-abc"
    assert event["session_id"] == "sess-xyz"
    assert event["request_id"] == "req-123"
    assert event["contains_pii"] is True
    assert event["contains_phi"] is True
    assert event["data_classification"] == "confidential"
