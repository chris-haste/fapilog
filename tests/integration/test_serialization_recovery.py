"""
Serialization Failure Recovery Integration Tests

Tests for verifying that the logging pipeline handles serialization failures
gracefully:
- Events before a failure in a batch still reach the sink
- Events after a failure in a batch are processed normally
- Subsequent batches process normally after a failure
- Metrics accurately reflect partial successes
- Error context is captured for debugging

Story 7.2: These tests verify behavioral correctness of serialization
failure handling, not just line coverage.

Implementation Note (Updated Story 1.28):
After v1.1 schema alignment (Stories 1.26/1.27/1.28), the pipeline produces
log events that serialize successfully through serialize_envelope(). The only
failures are truly exceptional - non-JSON-serializable objects (custom classes,
lambdas, etc.) embedded in the event data.

Serialization paths:
1. serialize_envelope() - succeeds for all valid events from build_envelope()
2. serialize_mapping_to_json_bytes() - fallback for edge cases

When serialize_envelope fails (non-serializable data), handling depends on mode:
- strict mode: event is dropped
- best-effort mode: fallback attempted, or falls through to dict-path sink

These tests verify behavior with serialize_in_flush=True and a collecting
sink that tracks what events were successfully serialized.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest

from fapilog.core.logger import AsyncLoggerFacade
from fapilog.core.serialization import SerializedView

pytestmark = pytest.mark.integration


class NonSerializable:
    """Object that cannot be JSON serialized by orjson."""

    pass


def _create_collecting_sink(collected: list[dict[str, Any]]):
    """Create an async sink that collects events."""

    async def sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    return sink


def _create_serialized_collecting_sink(
    collected: list[dict[str, Any]],
):
    """Create an async sink that collects serialized events as parsed dicts.

    This sink receives SerializedView (bytes) and parses them back to dicts
    for easier assertion. Only successfully serialized events reach this sink.
    """

    async def sink(view: SerializedView) -> None:
        # Parse the JSON bytes back to dict for easier testing
        data = json.loads(view.data)
        collected.append(data)

    return sink


@pytest.mark.asyncio
async def test_serialization_failure_mid_batch_preserves_prior_events() -> None:
    """Events before a serialization failure should still reach the sink.

    This verifies that serialization failures are handled per-event, not
    per-batch, so valid events are not lost due to one bad event.

    We use sink_write_serialized to track successfully serialized events,
    and sink_write to track events that fell back to dict path (failed serialization).
    """
    serialized_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []

    logger = AsyncLoggerFacade(
        name="test-mid-batch",
        queue_capacity=100,
        batch_max_size=10,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=_create_collecting_sink(fallback_events),
        sink_write_serialized=_create_serialized_collecting_sink(serialized_events),
        serialize_in_flush=True,
    )
    logger.start()

    # First 3 events are valid
    await logger.info("event-1")
    await logger.info("event-2")
    await logger.info("event-3")

    # This event contains non-serializable data
    await logger.info("bad-event", payload=NonSerializable())

    # These events are valid
    await logger.info("event-5")
    await logger.info("event-6")

    result = await logger.stop_and_drain()

    # Extract messages from serialized events (successfully serialized)
    # v1.1 schema wraps in {"schema_version": "1.1", "log": {...}}
    serialized_messages = [e.get("log", e).get("message") for e in serialized_events]

    # Verify: valid events should have been serialized successfully
    assert "event-1" in serialized_messages, "event-1 should serialize"
    assert "event-2" in serialized_messages, "event-2 should serialize"
    assert "event-3" in serialized_messages, "event-3 should serialize"
    assert "event-5" in serialized_messages, "event-5 should serialize"
    assert "event-6" in serialized_messages, "event-6 should serialize"

    # Verify: the bad event should NOT be in serialized events
    assert "bad-event" not in serialized_messages, "bad event should fail serialization"

    # Verify: the bad event fell back to dict path
    fallback_messages = [e.get("message") for e in fallback_events]
    assert "bad-event" in fallback_messages, "bad event should fall back to dict sink"

    # Verify: counts - all 6 were submitted and processed (fallback counts as processed)
    assert result.submitted == 6, "All 6 events were submitted"
    assert result.processed == 6, "All 6 events were processed (including fallback)"
    assert len(serialized_events) == 5, "5 events were serialized successfully"
    assert len(fallback_events) == 1, "1 event fell back to dict path"


@pytest.mark.asyncio
async def test_pipeline_continues_after_serialization_failure() -> None:
    """Pipeline should remain healthy after a serialization failure.

    Verifies that subsequent batches process normally even after a batch
    contained a serialization failure. The bad event falls back to dict path,
    but doesn't affect processing of other events.
    """
    serialized_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []

    logger = AsyncLoggerFacade(
        name="test-continuity",
        queue_capacity=100,
        batch_max_size=5,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=_create_collecting_sink(fallback_events),
        sink_write_serialized=_create_serialized_collecting_sink(serialized_events),
        serialize_in_flush=True,
    )
    logger.start()

    # Batch 1: Contains a bad event
    await logger.info("batch1-event1")
    await logger.info("batch1-bad", payload=NonSerializable())
    await logger.info("batch1-event3")

    # Wait for batch to flush
    await asyncio.sleep(0.1)

    # Batch 2: All valid events (should process normally)
    await logger.info("batch2-event1")
    await logger.info("batch2-event2")
    await logger.info("batch2-event3")

    result = await logger.stop_and_drain()

    # v1.1 schema wraps in {"schema_version": "1.1", "log": {...}}
    serialized_messages = [e.get("log", e).get("message") for e in serialized_events]

    # Batch 1 valid events should be serialized
    assert "batch1-event1" in serialized_messages, "batch1-event1 should serialize"
    assert "batch1-event3" in serialized_messages, "batch1-event3 should serialize"
    assert "batch1-bad" not in serialized_messages, "bad event should not serialize"

    # Batch 2 events should all be serialized (pipeline recovered)
    assert "batch2-event1" in serialized_messages, "batch2-event1 should serialize"
    assert "batch2-event2" in serialized_messages, "batch2-event2 should serialize"
    assert "batch2-event3" in serialized_messages, "batch2-event3 should serialize"

    # Verify: bad event fell back to dict path
    fallback_messages = [e.get("message") for e in fallback_events]
    assert "batch1-bad" in fallback_messages, "bad event should fall back"

    # Verify counts
    assert result.submitted == 6
    assert result.processed == 6  # All processed (fallback counts)
    assert len(serialized_events) == 5  # 5 serialized successfully
    assert len(fallback_events) == 1  # 1 fell back


@pytest.mark.asyncio
async def test_metrics_reflect_serialization_failures() -> None:
    """Metrics should accurately count successes and failures.

    Verifies that DrainResult counters match actual processing outcomes
    when some events fail serialization. Both serialized and fallback
    events count as "processed".
    """
    serialized_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []

    logger = AsyncLoggerFacade(
        name="test-metrics",
        queue_capacity=100,
        batch_max_size=20,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=_create_collecting_sink(fallback_events),
        sink_write_serialized=_create_serialized_collecting_sink(serialized_events),
        serialize_in_flush=True,
    )
    logger.start()

    # Submit 5 valid events
    for i in range(5):
        await logger.info(f"valid-{i}")

    # Submit 1 invalid event
    await logger.info("invalid", payload=NonSerializable())

    # Submit 4 more valid events
    for i in range(4):
        await logger.info(f"valid-post-{i}")

    result = await logger.stop_and_drain()

    # Submitted should be 10
    assert result.submitted == 10, "10 events submitted"

    # All events processed (serialization failure falls back to dict path)
    assert result.processed == 10, "10 events processed (including fallback)"

    # 9 events serialized successfully
    assert len(serialized_events) == 9, "9 events serialized"

    # 1 event fell back to dict path
    assert len(fallback_events) == 1, "1 event fell back"

    # Verify the invalid event is in fallback
    fallback_messages = [e.get("message") for e in fallback_events]
    assert "invalid" in fallback_messages, "invalid event should fall back"


@pytest.mark.asyncio
async def test_serialization_error_emits_diagnostic() -> None:
    """Serialization failures should emit diagnostics with context.

    Verifies that when serialization fails, a diagnostic warning is emitted
    that can help with debugging.
    """
    diagnostics_emitted: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        diagnostics_emitted.append(
            {"component": component, "message": message, **fields}
        )

    serialized_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []

    with patch("fapilog.core.worker.warn", side_effect=capture_warn):
        logger = AsyncLoggerFacade(
            name="test-diagnostic",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_create_collecting_sink(fallback_events),
            sink_write_serialized=_create_serialized_collecting_sink(serialized_events),
            serialize_in_flush=True,
        )
        logger.start()

        await logger.info("bad-event", user_id="u-123", payload=NonSerializable())

        await logger.stop_and_drain()

    # Find the serialization error diagnostic
    serialization_errors = [
        d
        for d in diagnostics_emitted
        if "serializ" in d.get("message", "").lower() or d.get("component") == "sink"
    ]

    assert len(serialization_errors) >= 1, (  # noqa: WA002
        "Should emit diagnostic on serialization error"
    )

    # Verify the diagnostic contains useful context
    error = serialization_errors[0]
    assert error.get("mode") in ("strict", "best-effort"), "Should indicate mode"
    assert "reason" in error or "error_type" in error, "Should include error type"


@pytest.mark.asyncio
async def test_deeply_nested_non_serializable_handled() -> None:
    """Deeply nested non-serializable objects should be caught and handled.

    Verifies that even when the non-serializable object is buried deep in
    nested structures, it's caught and the event falls back to dict path.
    """
    serialized_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []

    logger = AsyncLoggerFacade(
        name="test-nested",
        queue_capacity=100,
        batch_max_size=10,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=_create_collecting_sink(fallback_events),
        sink_write_serialized=_create_serialized_collecting_sink(serialized_events),
        serialize_in_flush=True,
    )
    logger.start()

    # Valid event
    await logger.info("valid-before")

    # Deeply nested bad object
    await logger.info(
        "nested-bad",
        data={
            "level1": {
                "level2": {
                    "level3": NonSerializable(),
                },
            },
        },
    )

    # Valid event
    await logger.info("valid-after")

    result = await logger.stop_and_drain()

    # v1.1 schema wraps in {"schema_version": "1.1", "log": {...}}
    serialized_messages = [e.get("log", e).get("message") for e in serialized_events]
    assert "valid-before" in serialized_messages, "valid-before should serialize"
    assert "valid-after" in serialized_messages, "valid-after should serialize"
    assert "nested-bad" not in serialized_messages, "nested-bad should not serialize"

    # Verify nested-bad fell back to dict path
    fallback_messages = [e.get("message") for e in fallback_events]
    assert "nested-bad" in fallback_messages, "nested-bad should fall back to dict path"

    # Verify exact counts
    assert len(serialized_events) == 2, "2 events serialized successfully"
    assert len(fallback_events) == 1, "1 event fell back"
    assert result.processed == 3, "3 events processed (including fallback)"
    assert result.submitted == 3, "3 events submitted"
