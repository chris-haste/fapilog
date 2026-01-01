from __future__ import annotations

import json

import pytest

from fapilog.core.audit import (
    AuditEvent,
    AuditEventType,
    AuditTrail,
    CompliancePolicy,
)


@pytest.mark.asyncio
async def test_audit_stop_drains_queue(tmp_path) -> None:
    audit = AuditTrail(policy=CompliancePolicy(), storage_path=tmp_path)
    await audit.start()
    await audit.log_security_event(
        AuditEventType.AUTHENTICATION_FAILED,
        "login failed",
        user_id="user@example.com",
    )

    await audit.stop()

    files = list(tmp_path.glob("audit_*.jsonl"))
    assert files, "Expected audit file to be written after stop() drains the queue"
    content = files[0].read_text().strip().splitlines()
    assert content, "Audit file should contain at least one event"


@pytest.mark.asyncio
async def test_audit_chain_fields_and_verify(tmp_path) -> None:
    audit_dir = tmp_path / "chain"
    audit = AuditTrail(policy=CompliancePolicy(), storage_path=audit_dir)
    await audit.start()
    await audit.log_data_access(
        resource="customers",
        operation="read",
        user_id="admin@example.com",
        contains_pii=True,
    )
    await audit.log_security_event(
        AuditEventType.SECURITY_VIOLATION, "violation", user_id="attacker"
    )
    await audit.stop()

    files = sorted(audit_dir.glob("audit_*.jsonl"))
    assert files, "Expected persisted audit log files"
    lines = []
    for f in files:
        lines.extend([ln for ln in f.read_text().splitlines() if ln.strip()])
    events = [json.loads(line) for line in lines]
    assert all("sequence_number" in e for e in events)
    assert all("previous_hash" in e for e in events)
    assert all(e.get("checksum") for e in events)

    verify_result = await audit.verify_chain_from_storage()
    assert verify_result.valid
    assert verify_result.events_checked == len(events)

    # Tamper with checksum to ensure verification fails
    tampered_events = [AuditEvent(**e) for e in events]
    tampered_events[0].checksum = "deadbeef"
    tampered = AuditTrail.verify_chain(tampered_events)
    assert not tampered.valid
