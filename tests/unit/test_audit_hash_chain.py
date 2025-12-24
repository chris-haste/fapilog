import asyncio
from typing import List

import pytest

from fapilog.core.audit import (
    GENESIS_HASH,
    AuditEvent,
    AuditEventType,
    AuditTrail,
    ChainVerificationResult,
)


@pytest.mark.asyncio
async def test_chain_fields_and_checksum_populated():
    trail = AuditTrail()

    await trail.log_event(AuditEventType.SYSTEM_STARTUP, "start")
    await trail.log_event(AuditEventType.SYSTEM_SHUTDOWN, "stop")

    events: List[AuditEvent] = []
    while not trail._event_queue.empty():  # noqa: SLF001
        events.append(await trail._event_queue.get())  # noqa: SLF001

    assert len(events) == 2
    first, second = events

    assert first.sequence_number == 1
    assert first.previous_hash == GENESIS_HASH
    assert isinstance(first.checksum, str) and len(first.checksum) == 64

    assert second.sequence_number == 2
    assert second.previous_hash == first.checksum
    assert isinstance(second.checksum, str) and len(second.checksum) == 64


def test_verify_checksum_valid_and_invalid():
    event = AuditEvent(event_type=AuditEventType.SYSTEM_STARTUP, message="ok")
    event.checksum = event.compute_checksum()
    assert event.verify_checksum() is True

    # Tamper
    event.metadata["tampered"] = True
    assert event.verify_checksum() is False


def test_verify_chain_valid_gap_and_tamper():
    events = []
    prev_hash = GENESIS_HASH
    for i in range(3):
        ev = AuditEvent(event_type=AuditEventType.SYSTEM_STARTUP, message=f"e{i + 1}")
        ev.sequence_number = i + 1
        ev.previous_hash = prev_hash
        ev.checksum = ev.compute_checksum()
        prev_hash = ev.checksum
        events.append(ev)

    result = AuditTrail.verify_chain(events)
    assert isinstance(result, ChainVerificationResult)
    assert result.valid is True
    assert result.events_checked == 3

    # Gap
    events_gap = events.copy()
    events_gap[-1].sequence_number = 5
    result_gap = AuditTrail.verify_chain(events_gap)
    assert result_gap.valid is False

    # Tamper checksum
    events_tamper = events.copy()
    events_tamper[1].metadata["tampered"] = True
    result_tamper = AuditTrail.verify_chain(events_tamper)
    assert result_tamper.valid is False

    # Tamper previous hash
    events_hash = events.copy()
    events_hash[2].previous_hash = "1" * 64
    result_hash = AuditTrail.verify_chain(events_hash)
    assert result_hash.valid is False


@pytest.mark.asyncio
async def test_concurrent_logging_sequences_unique():
    trail = AuditTrail()

    async def emit(idx: int) -> None:
        await trail.log_event(AuditEventType.DATA_ACCESS, f"event {idx}")

    await asyncio.gather(*(emit(i) for i in range(50)))

    events: List[AuditEvent] = []
    while not trail._event_queue.empty():  # noqa: SLF001
        events.append(await trail._event_queue.get())  # noqa: SLF001

    seqs = [e.sequence_number for e in events]
    assert len(seqs) == len(set(seqs))
    assert min(seqs) == 1
    assert max(seqs) == len(events)

    # Check linkage
    events_sorted = sorted(events, key=lambda e: e.sequence_number)
    expected_prev = GENESIS_HASH
    for ev in events_sorted:
        assert ev.previous_hash == expected_prev
        assert ev.verify_checksum() is True
        expected_prev = ev.checksum
