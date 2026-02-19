"""Contract test: shedding survives full pipeline (Story 1.59, AC9).

Verifies that protected events dequeued during shed mode are normal envelopes
that pass through redaction and sink write without errors.
"""

from __future__ import annotations

from typing import Any

import pytest

from fapilog.core.concurrency import DualQueue
from fapilog.core.envelope import build_envelope
from fapilog.plugins.redactors import redact_in_order


@pytest.mark.asyncio
async def test_shed_mode_events_flow_through_pipeline() -> None:
    """Protected events enqueued during shed mode are valid envelopes."""
    dq: DualQueue[dict[str, Any]] = DualQueue(
        main_capacity=100,
        protected_capacity=10,
        protected_levels=frozenset({"ERROR"}),
    )

    # Build a real envelope and enqueue it
    envelope = build_envelope(level="ERROR", message="critical event")
    dq.try_enqueue(dict(envelope))

    # Activate shedding
    dq.activate_shedding()

    # Dequeue — should only get the protected event
    ok, item = dq.try_dequeue()
    assert ok is True
    assert item is not None and item["level"] == "ERROR"

    # Pass through redaction with no redactors (empty pipeline)
    redacted = await redact_in_order(item, [])
    assert redacted["level"] == "ERROR"
    assert redacted["message"] == "critical event"

    # Simulate sink write (just verify the dict is JSON-serializable)
    import json

    serialized = json.dumps(redacted)
    assert "critical event" in serialized
