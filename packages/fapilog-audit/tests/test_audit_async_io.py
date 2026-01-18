"""Tests for non-blocking audit trail file I/O (Story 4.28)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from fapilog_audit import AuditEventType, AuditTrail, CompliancePolicy


@pytest.mark.asyncio
async def test_store_event_uses_to_thread(tmp_path: Path) -> None:
    """Verify _store_event offloads file I/O to thread pool via asyncio.to_thread."""
    trail = AuditTrail(policy=CompliancePolicy(), storage_path=tmp_path)
    await trail.start()

    patch_target = "fapilog_audit.audit.asyncio.to_thread"
    with patch(patch_target, new_callable=AsyncMock) as mock_to_thread:
        # Configure mock to actually write the file so the test doesn't break state
        def side_effect(func: Any, *args: Any) -> Any:
            return func(*args)

        mock_to_thread.side_effect = side_effect

        await trail.log_event(AuditEventType.DATA_ACCESS, "test event")
        await trail.drain()

        # Verify to_thread was called
        assert mock_to_thread.called, "asyncio.to_thread should be called for file I/O"
        assert mock_to_thread.call_count == 1, "to_thread should be called exactly once"

        # Verify it was called with _write_to_file method and correct arguments
        call_args = mock_to_thread.call_args
        assert call_args[0][0].__name__ == "_write_to_file", (
            "First arg to to_thread should be _write_to_file method"
        )

    await trail.stop()


@pytest.mark.asyncio
async def test_concurrent_audit_does_not_block_event_loop(tmp_path: Path) -> None:
    """Verify concurrent audit logging doesn't block other async operations."""
    trail = AuditTrail(policy=CompliancePolicy(), storage_path=tmp_path)
    await trail.start()

    other_work_completed = False

    async def other_work() -> bool:
        nonlocal other_work_completed
        await asyncio.sleep(0.001)
        other_work_completed = True
        return True

    async def audit_burst() -> None:
        for i in range(50):
            await trail.log_event(AuditEventType.DATA_ACCESS, f"event {i}")

    # Both should complete without one blocking the other
    results = await asyncio.gather(audit_burst(), other_work())

    assert other_work_completed, "other_work should complete during audit burst"
    assert results[1] is True, "other_work should return True"

    await trail.stop()


@pytest.mark.asyncio
async def test_chain_integrity_preserved_with_async_writes(tmp_path: Path) -> None:
    """Verify hash chain integrity works correctly with async file I/O."""
    trail = AuditTrail(policy=CompliancePolicy(), storage_path=tmp_path)
    await trail.start()

    # Log multiple events to build a chain
    for i in range(10):
        await trail.log_event(AuditEventType.DATA_ACCESS, f"event {i}")

    await trail.drain()
    await trail.stop()

    # Verify chain integrity from storage
    result = await trail.verify_chain_from_storage()
    assert result.valid is True, f"Chain should be valid: {result.error_message}"
    assert result.events_checked == 10, (
        f"Expected 10 events, got {result.events_checked}"
    )


@pytest.mark.asyncio
async def test_write_error_contained_with_invalid_path(tmp_path: Path) -> None:
    """Verify file write errors are contained and don't crash the audit system."""
    # Use a path that will fail on write (directory that doesn't exist)
    invalid_path = tmp_path / "nonexistent" / "deeply" / "nested" / "path"

    trail = AuditTrail(policy=CompliancePolicy(), storage_path=invalid_path)
    await trail.start()

    # This should not raise, error should be contained
    await trail.log_event(AuditEventType.DATA_ACCESS, "test event")
    await trail.drain()

    # Verify the trail is still operational (can accept more events)
    await trail.log_event(AuditEventType.DATA_ACCESS, "another event")
    await trail.drain()

    # Verify statistics still work (trail didn't crash)
    stats = await trail.get_statistics()
    assert stats["total_events"] == 2, "Trail should have counted both events"

    await trail.stop()
