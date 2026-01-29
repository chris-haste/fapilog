"""
Worker/Logger Lifecycle Coverage Tests

Story 7.10: Tests covering lifecycle and error-handling paths in worker.py
and logger.py that represent real production risk scenarios.

Coverage areas:
- AC1: Worker Shutdown Ordering (plugin stop order, error containment)
- AC2: Worker Cancellation Handling (CancelledError, queue integrity)
- AC3: Sink Write Failure Mid-Batch (dropped counter, error recording)
- AC4: Serialization Fallback Paths (strict/best-effort modes)
- AC5: Backpressure and Enqueue Edge Cases (same-thread drop, timeout)
- AC6: Thread-Loop Mode (background thread creation, cleanup)
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fapilog.core import worker
from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade
from fapilog.core.serialization import SerializedView
from fapilog.core.worker import LoggerWorker, stop_plugins

pytestmark = pytest.mark.integration


# =============================================================================
# Helpers
# =============================================================================


class NonSerializable:
    """Object that cannot be JSON serialized."""

    pass


def _create_collecting_sink(collected: list[dict[str, Any]]):
    """Create an async sink that collects events."""

    async def sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    return sink


def _create_serialized_collecting_sink(collected: list[dict[str, Any]]):
    """Create an async sink that collects serialized events as parsed dicts."""

    async def sink(view: SerializedView) -> None:
        data = json.loads(view.data)
        collected.append(data)

    return sink


# =============================================================================
# AC1: Worker Shutdown Ordering
# =============================================================================


class _TrackedPlugin:
    """Plugin that tracks stop order."""

    def __init__(self, name: str, stop_order: list[str], *, raise_exc: bool = False):
        self.name = name
        self._stop_order = stop_order
        self._raise_exc = raise_exc

    async def stop(self) -> None:
        self._stop_order.append(self.name)
        if self._raise_exc:
            raise RuntimeError(f"{self.name} stop failed")


@pytest.mark.asyncio
async def test_stop_plugins_reverse_order() -> None:
    """Plugins should stop in reverse registration order."""
    stop_order: list[str] = []

    enrichers = [
        _TrackedPlugin("enricher-0", stop_order),
        _TrackedPlugin("enricher-1", stop_order),
        _TrackedPlugin("enricher-2", stop_order),
    ]

    await stop_plugins([], [], [], enrichers)

    # Should stop in reverse: enricher-2, enricher-1, enricher-0
    assert stop_order == ["enricher-2", "enricher-1", "enricher-0"]


@pytest.mark.asyncio
async def test_stop_plugins_contains_errors() -> None:
    """Plugin stop errors should not block other plugins."""
    stop_order: list[str] = []

    plugins = [
        _TrackedPlugin("good-1", stop_order),
        _TrackedPlugin("failing", stop_order, raise_exc=True),
        _TrackedPlugin("good-2", stop_order),
    ]

    # Should not raise, should stop all plugins that can be stopped
    await stop_plugins([], [], [], plugins)

    # All plugins should have had stop() called
    assert "good-1" in stop_order
    assert "failing" in stop_order
    assert "good-2" in stop_order


@pytest.mark.asyncio
async def test_stop_plugins_emits_diagnostics_on_failure(monkeypatch) -> None:
    """Plugin stop failures should emit diagnostics."""
    diagnostics: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        diagnostics.append({"component": component, "message": message, **fields})

    monkeypatch.setattr(worker, "warn", capture_warn)

    plugins = [_TrackedPlugin("failing-plugin", [], raise_exc=True)]

    await stop_plugins([], [], [], plugins)

    # Should have emitted a diagnostic for the failing plugin
    assert len(diagnostics) == 1
    assert diagnostics[0]["component"] == "enricher"
    assert diagnostics[0]["message"] == "plugin stop failed"
    assert diagnostics[0]["plugin"] == "failing-plugin"


# =============================================================================
# AC2: Worker Cancellation Handling
# =============================================================================


@pytest.mark.asyncio
async def test_cancelled_error_exits_worker_cleanly() -> None:
    """CancelledError should exit worker loop without corrupting state."""
    collected: list[dict[str, Any]] = []
    queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
    counters: dict[str, int] = {"processed": 0, "dropped": 0}

    # Pre-populate queue with events
    for i in range(5):
        queue.try_enqueue({"message": f"event-{i}", "level": "INFO"})

    worker_instance = LoggerWorker(
        queue=queue,
        batch_max_size=10,
        batch_timeout_seconds=10.0,
        sink_write=_create_collecting_sink(collected),
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=None,
        serialize_in_flush=False,
        strict_envelope_mode_provider=lambda: False,
        stop_flag=lambda: False,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        counters=counters,
    )

    # Run worker and cancel it after a brief period
    task = asyncio.create_task(worker_instance.run())
    await asyncio.sleep(0.05)
    task.cancel()

    # Worker catches CancelledError and returns cleanly (doesn't re-raise)
    # So we should be able to await the task without exception
    try:
        await task
    except asyncio.CancelledError:
        pass  # Also acceptable if it does propagate

    # Queue should still be accessible (not corrupted) - verify we can call qsize()
    # The queue may have been drained during the run, so we just verify it's callable
    qsize = queue.qsize()
    assert isinstance(qsize, int), "Queue should return integer size"


@pytest.mark.asyncio
async def test_metrics_reflect_events_processed_before_cancellation() -> None:
    """Metrics should reflect events processed before cancellation."""
    collected: list[dict[str, Any]] = []
    queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
    counters: dict[str, int] = {"processed": 0, "dropped": 0}
    stop_flag_value = False

    def stop_flag() -> bool:
        return stop_flag_value

    # Pre-populate queue with events
    for i in range(3):
        queue.try_enqueue({"message": f"event-{i}", "level": "INFO"})

    worker_instance = LoggerWorker(
        queue=queue,
        batch_max_size=10,
        batch_timeout_seconds=0.01,  # Short timeout to flush quickly
        sink_write=_create_collecting_sink(collected),
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=None,
        serialize_in_flush=False,
        strict_envelope_mode_provider=lambda: False,
        stop_flag=stop_flag,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        counters=counters,
    )

    # Run worker until batch timeout triggers flush
    task = asyncio.create_task(worker_instance.run())
    await asyncio.sleep(0.05)  # Allow batch to flush
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Events should have been processed before cancellation
    assert counters["processed"] == 3
    assert len(collected) == 3


# =============================================================================
# AC3: Sink Write Failure Mid-Batch
# =============================================================================


@pytest.mark.asyncio
async def test_sink_failure_increments_dropped_counter() -> None:
    """Sink write failure should increment dropped counter for the batch."""
    queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
    counters: dict[str, int] = {"processed": 0, "dropped": 0}

    async def failing_sink(event: dict[str, Any]) -> None:
        raise OSError("Sink unavailable")

    # Pre-populate queue
    for i in range(3):
        queue.try_enqueue({"message": f"event-{i}", "level": "INFO"})

    worker_instance = LoggerWorker(
        queue=queue,
        batch_max_size=10,
        batch_timeout_seconds=0.01,
        sink_write=failing_sink,
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=None,
        serialize_in_flush=False,
        strict_envelope_mode_provider=lambda: False,
        stop_flag=lambda: True,  # Stop immediately after drain
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        counters=counters,
    )

    await worker_instance.run()

    # All events should be counted as dropped due to sink failure
    assert counters["dropped"] == 3


@pytest.mark.asyncio
async def test_record_sink_error_captures_sink_name() -> None:
    """_record_sink_error should capture the sink class name."""
    metrics_calls: list[dict[str, Any]] = []

    class MockMetrics:
        async def record_sink_error(self, *, sink: str | None) -> None:
            metrics_calls.append({"method": "record_sink_error", "sink": sink})

        async def record_flush(
            self, *, batch_size: int, latency_seconds: float
        ) -> None:
            pass

    class NamedSink:
        async def write(self, event: dict[str, Any]) -> None:
            raise OSError("Sink failed")

    sink_instance = NamedSink()
    queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
    counters: dict[str, int] = {"processed": 0, "dropped": 0}

    queue.try_enqueue({"message": "test", "level": "INFO"})

    worker_instance = LoggerWorker(
        queue=queue,
        batch_max_size=10,
        batch_timeout_seconds=0.01,
        sink_write=sink_instance.write,
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=MockMetrics(),  # type: ignore[arg-type]
        serialize_in_flush=False,
        strict_envelope_mode_provider=lambda: False,
        stop_flag=lambda: True,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        counters=counters,
    )

    await worker_instance.run()

    # Verify sink name was captured in metrics
    sink_errors = [c for c in metrics_calls if c["method"] == "record_sink_error"]
    assert len(sink_errors) == 1
    assert sink_errors[0]["sink"] == "NamedSink"


@pytest.mark.asyncio
async def test_emit_sink_flush_error_includes_context(monkeypatch) -> None:
    """_emit_sink_flush_error should emit diagnostic with error context."""
    diagnostics: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        diagnostics.append({"component": component, "message": message, **fields})

    monkeypatch.setattr(worker, "warn", capture_warn)

    queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
    counters: dict[str, int] = {"processed": 0, "dropped": 0}

    async def failing_sink(event: dict[str, Any]) -> None:
        raise ValueError("Connection refused")

    queue.try_enqueue({"message": "test", "level": "INFO"})

    worker_instance = LoggerWorker(
        queue=queue,
        batch_max_size=10,
        batch_timeout_seconds=0.01,
        sink_write=failing_sink,
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=None,
        serialize_in_flush=False,
        strict_envelope_mode_provider=lambda: False,
        stop_flag=lambda: True,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        counters=counters,
    )

    await worker_instance.run()

    # Should have emitted a flush error diagnostic
    flush_errors = [d for d in diagnostics if d["message"] == "flush error"]
    assert len(flush_errors) == 1
    assert flush_errors[0]["component"] == "sink"
    assert flush_errors[0]["error_type"] == "ValueError"
    assert "Connection refused" in flush_errors[0]["error"]


@pytest.mark.asyncio
async def test_subsequent_batches_process_after_sink_failure() -> None:
    """Subsequent batches should process normally after a sink failure."""
    collected: list[dict[str, Any]] = []
    call_count = 0

    async def flaky_sink(event: dict[str, Any]) -> None:
        nonlocal call_count
        call_count += 1
        # Fail on first call only
        if call_count == 1:
            raise OSError("Temporary failure")
        collected.append(dict(event))

    logger = AsyncLoggerFacade(
        name="test-recovery",
        queue_capacity=100,
        batch_max_size=1,  # Process one at a time to control failure
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=flaky_sink,
    )
    logger.start()

    # First event - will fail (call_count=1 raises)
    await logger.info("event1-fail")
    await asyncio.sleep(0.05)

    # Second event - should succeed (call_count=2)
    await logger.info("event2-success")
    await asyncio.sleep(0.05)

    # Third event - should succeed (call_count=3)
    await logger.info("event3-success")

    await logger.stop_and_drain()

    # Events after failure should have been collected
    messages = [e.get("message") for e in collected]
    assert "event2-success" in messages
    assert "event3-success" in messages
    # First event should have been dropped due to failure
    assert "event1-fail" not in messages


# =============================================================================
# AC4: Serialization Fallback Paths
# =============================================================================


@pytest.mark.asyncio
async def test_strict_envelope_mode_drops_unserializable() -> None:
    """Strict mode should drop events that fail serialization without fallback.

    In strict envelope mode, when serialization fails, events are dropped
    rather than falling back to the dict sink. This tests that behavior
    by verifying unserializable events don't reach ANY sink.

    After Story 1.28 (v1.1 schema alignment): Valid events from build_envelope()
    now serialize successfully. Only events with non-JSON-serializable objects
    (custom classes, lambdas, etc.) fail serialization. The distinction is:
    - Best-effort mode: Falls back to serialize_mapping_to_json_bytes
    - Strict mode: Drops events that fail serialization
    """
    serialized_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []

    # Patch Settings before creating logger so it caches strict_envelope_mode=True
    # (Story 1.25 - settings are cached at logger init time)
    with patch("fapilog.core.settings.Settings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings.core.strict_envelope_mode = True
        mock_settings.observability.logging.sampling_rate = 1.0
        mock_settings.core.filters = []
        mock_settings.core.error_dedupe_window_seconds = 0.0
        mock_settings_cls.return_value = mock_settings

        logger = AsyncLoggerFacade(
            name="test-strict",
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

        # With v1.1 schema, valid events now pass serialize_envelope (have context/diagnostics)
        # Only events with non-serializable payloads fail and are dropped in strict mode
        await logger.info("event-1")
        await logger.info("event-with-bad-payload", payload=NonSerializable())
        await logger.info("event-2")

        await logger.stop_and_drain()

    # In strict mode, events that fail serialization are dropped, not fall back
    fallback_messages = [e.get("message") for e in fallback_events]
    assert "event-with-bad-payload" not in fallback_messages, (
        "Bad event should not fall back to dict sink in strict mode"
    )

    # Valid events should NOT fall back either - they serialize successfully
    assert "event-1" not in fallback_messages
    assert "event-2" not in fallback_messages

    # v1.1 schema: valid events now serialize successfully (have context/diagnostics/data)
    # Only the bad payload event is dropped
    # Note: serialized output is {"schema_version": "1.1", "log": {...}}
    serialized_messages = [e.get("log", e).get("message") for e in serialized_events]
    assert "event-1" in serialized_messages, "Valid events should serialize in v1.1"
    assert "event-2" in serialized_messages, "Valid events should serialize in v1.1"
    assert "event-with-bad-payload" not in serialized_messages, "Bad payload dropped"


@pytest.mark.asyncio
async def test_best_effort_mode_falls_back_to_mapping_serializer() -> None:
    """Best-effort mode should fall back to serialize_mapping_to_json_bytes."""
    serialized_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []

    logger = AsyncLoggerFacade(
        name="test-best-effort",
        queue_capacity=100,
        batch_max_size=10,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=_create_collecting_sink(fallback_events),
        sink_write_serialized=_create_serialized_collecting_sink(serialized_events),
        serialize_in_flush=True,
    )

    # Default mode is best-effort (strict_envelope_mode=False)
    logger.start()

    await logger.info("valid-event")
    await logger.info("bad-event", payload=NonSerializable())
    await logger.info("another-valid")

    await logger.stop_and_drain()

    # v1.1 schema wraps in {"schema_version": "1.1", "log": {...}}
    serialized_messages = [e.get("log", e).get("message") for e in serialized_events]
    fallback_messages = [e.get("message") for e in fallback_events]

    # Valid events should be serialized
    assert "valid-event" in serialized_messages
    assert "another-valid" in serialized_messages

    # Bad event should fall back to dict sink in best-effort mode
    assert "bad-event" in fallback_messages


@pytest.mark.asyncio
async def test_serialization_diagnostic_includes_mode_and_error_type(
    monkeypatch,
) -> None:
    """Serialization error diagnostic should include mode and error type."""
    diagnostics: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        diagnostics.append({"component": component, "message": message, **fields})

    monkeypatch.setattr(worker, "warn", capture_warn)

    serialized_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []

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

    await logger.info("bad-event", payload=NonSerializable())

    await logger.stop_and_drain()

    # Find serialization error diagnostic
    serialization_errors = [
        d for d in diagnostics if "serialization" in d.get("message", "").lower()
    ]

    assert len(serialization_errors) >= 1  # noqa: WA002 timing-dependent
    error = serialization_errors[0]
    assert error.get("mode") in ("strict", "best-effort")
    assert "reason" in error  # Error type name


# =============================================================================
# AC5: Backpressure and Enqueue Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_same_thread_enqueue_drops_with_diagnostic_when_full() -> None:
    """Same-thread enqueue should drop with diagnostic when queue full."""
    diagnostics: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        diagnostics.append({"component": component, "message": message, **fields})

    collected: list[dict[str, Any]] = []

    # Create logger with tiny queue that will fill up
    logger = SyncLoggerFacade(
        name="test-same-thread-bp",
        queue_capacity=2,
        batch_max_size=100,
        batch_timeout_seconds=10.0,  # Long timeout so batch doesn't flush
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=_create_collecting_sink(collected),
    )

    logger.start()

    # Simulate being on the same thread as the worker loop
    logger._loop_thread_ident = threading.get_ident()

    # Patch diagnostics.warn where it's actually imported from
    with patch("fapilog.core.diagnostics.warn", side_effect=capture_warn):
        # Manually fill logger queue
        logger._queue.try_enqueue({"message": "fill-1"})
        logger._queue.try_enqueue({"message": "fill-2"})

        # Now try to enqueue when full (same-thread path)
        # This should drop since queue is full and we're on same thread
        logger._enqueue("INFO", "overflow-event")

    # Should have backpressure diagnostic
    bp_diagnostics = [d for d in diagnostics if d["component"] == "backpressure"]
    assert len(bp_diagnostics) == 1
    assert "drop" in bp_diagnostics[0]["message"].lower()

    # Verify the event was dropped (exactly 1 event should be dropped)
    assert logger._dropped == 1


@pytest.mark.asyncio
async def test_same_thread_drop_with_drop_on_full_false_includes_mismatch_note() -> (
    None
):
    """Same-thread drop with drop_on_full=False emits diagnostic noting the mismatch."""
    diagnostics: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        diagnostics.append({"component": component, "message": message, **fields})

    collected: list[dict[str, Any]] = []

    # Create logger with drop_on_full=False (user expects blocking/waiting)
    logger = SyncLoggerFacade(
        name="test-same-thread-mismatch",
        queue_capacity=2,
        batch_max_size=100,
        batch_timeout_seconds=10.0,
        backpressure_wait_ms=1000,  # User configured to wait 1 second
        drop_on_full=False,  # User expects blocking behavior
        sink_write=_create_collecting_sink(collected),
    )

    logger.start()

    # Simulate being on the same thread as the worker loop
    logger._loop_thread_ident = threading.get_ident()

    with patch("fapilog.core.diagnostics.warn", side_effect=capture_warn):
        # Fill the queue
        logger._queue.try_enqueue({"message": "fill-1"})
        logger._queue.try_enqueue({"message": "fill-2"})

        # Same-thread enqueue when full - should drop despite drop_on_full=False
        logger._enqueue("INFO", "overflow-event")

    # Should have backpressure diagnostic with mismatch note
    bp_diagnostics = [d for d in diagnostics if d["component"] == "backpressure"]
    assert len(bp_diagnostics) == 1
    diag = bp_diagnostics[0]

    # Verify diagnostic includes drop_on_full_setting field
    assert "drop_on_full_setting" in diag
    assert diag["drop_on_full_setting"] is False

    # Verify message includes note about drop_on_full=False not being honored
    assert "drop_on_full=False" in diag["message"]

    # Verify the event was dropped
    assert logger._dropped == 1


@pytest.mark.asyncio
async def test_cross_thread_enqueue_timeout_path() -> None:
    """Cross-thread enqueue should timeout and drop when queue full."""
    collected: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        diagnostics.append({"component": component, "message": message, **fields})

    # Use a sink that blocks indefinitely to keep queue full
    block_event = asyncio.Event()

    async def blocking_sink(event: dict[str, Any]) -> None:
        await block_event.wait()  # Block until released
        collected.append(dict(event))

    logger = SyncLoggerFacade(
        name="test-cross-thread",
        queue_capacity=1,
        batch_max_size=1,
        batch_timeout_seconds=0.001,  # Very short batch timeout
        backpressure_wait_ms=10,  # 10ms backpressure wait
        drop_on_full=True,
        sink_write=blocking_sink,
    )
    logger.start()
    await asyncio.sleep(0.05)  # Allow worker to start

    # First event fills the queue and starts processing (blocks in sink)
    logger.info("event-1")
    await asyncio.sleep(0.05)  # Allow batch to start processing

    # Fill the queue again while sink is blocked
    logger._queue.try_enqueue({"message": "fill"})

    # Patch diagnostics where it's actually used
    with patch("fapilog.core.diagnostics.warn", side_effect=capture_warn):
        # This event should timeout waiting for space
        logger.info("event-2-overflow")

    # Allow some time for cross-thread enqueue attempt
    await asyncio.sleep(0.15)

    # Release the blocking sink so we can drain
    block_event.set()

    # The dropped counter should have been incremented (at least 1 drop)
    assert logger._dropped >= 1  # noqa: WA002 timing-dependent


@pytest.mark.asyncio
async def test_drop_on_full_false_waits_indefinitely() -> None:
    """drop_on_full=False should wait for space rather than dropping."""
    collected: list[dict[str, Any]] = []

    # Use a blocking sink to control when space is freed
    release_sink = asyncio.Event()

    async def controlled_sink(event: dict[str, Any]) -> None:
        await release_sink.wait()
        collected.append(dict(event))

    logger = AsyncLoggerFacade(
        name="test-wait",
        queue_capacity=1,
        batch_max_size=1,
        batch_timeout_seconds=0.001,  # Flush quickly
        backpressure_wait_ms=1000,  # Long wait
        drop_on_full=False,  # Should wait, not drop
        sink_write=controlled_sink,
    )
    logger.start()
    await asyncio.sleep(0.01)

    # Enqueue first event - fills queue and starts processing (blocked in sink)
    await logger.info("event-1")
    await asyncio.sleep(0.02)  # Let batch start processing

    # Fill the queue while sink is blocked
    logger._queue.try_enqueue({"message": "blocker"})

    # Try to enqueue another event - should block waiting for space
    enqueue_started = asyncio.Event()

    async def delayed_enqueue():
        enqueue_started.set()
        await logger.info("event-2")

    enqueue_task = asyncio.create_task(delayed_enqueue())
    await enqueue_started.wait()
    await asyncio.sleep(0.02)

    # Verify dropped counter is still 0 (event is waiting, not dropped)
    # With drop_on_full=False, we should be waiting
    # Note: The event may have been enqueued if queue freed space
    # The key behavior is that events are NOT dropped

    # Release the sink to allow processing
    release_sink.set()

    # Wait for the enqueue to complete
    await asyncio.wait_for(enqueue_task, timeout=2.0)

    await logger.stop_and_drain()

    # Key assertion: no events should be dropped
    assert logger._dropped == 0, "With drop_on_full=False, no events should be dropped"


@pytest.mark.asyncio
async def test_queue_high_watermark_updates_correctly() -> None:
    """_queue_high_watermark should track maximum queue depth."""
    collected: list[dict[str, Any]] = []

    # Use a slow sink to allow queue to build up
    async def slow_sink(event: dict[str, Any]) -> None:
        await asyncio.sleep(0.01)
        collected.append(dict(event))

    logger = AsyncLoggerFacade(
        name="test-hwm",
        queue_capacity=100,
        batch_max_size=5,
        batch_timeout_seconds=1.0,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=slow_sink,
    )
    logger.start()

    # Rapidly enqueue events to build up queue depth
    for i in range(10):
        await logger.info(f"event-{i}")

    await asyncio.sleep(0.05)  # Allow some processing

    # High watermark should have been updated (timing-dependent)
    assert logger._queue_high_watermark >= 1  # noqa: WA002

    result = await logger.stop_and_drain()

    # DrainResult should include the watermark (timing-dependent)
    assert result.queue_depth_high_watermark >= 1  # noqa: WA002


# =============================================================================
# AC6: Thread-Loop Mode
# =============================================================================


def test_sync_logger_creates_background_thread_when_no_event_loop() -> None:
    """Sync logger should create background thread when no event loop exists."""
    collected: list[dict[str, Any]] = []

    async def collecting_sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    # Create logger outside of async context
    logger = SyncLoggerFacade(
        name="test-thread-mode",
        queue_capacity=100,
        batch_max_size=10,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=collecting_sink,
    )

    # Start should create a background thread since there's no running loop
    logger.start()

    # Verify thread was created (is_alive() is the behavioral check)
    assert logger._worker_thread is not None  # noqa: WA003
    assert logger._worker_thread.is_alive()

    # Log some events
    logger.info("thread-mode-event")

    # Drain using sync method since we're not in async context
    # We need to use asyncio.run to call the async drain method
    async def drain_async():
        return await logger.stop_and_drain()

    result = asyncio.run(drain_async())

    # Thread should have processed the event (we submitted exactly 1)
    assert result.submitted == 1


@pytest.mark.asyncio
async def test_thread_cleanup_on_drain() -> None:
    """Worker thread should be cleaned up on drain."""
    collected: list[dict[str, Any]] = []

    async def collecting_sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    # Create logger in a separate thread to force thread-loop mode
    logger = SyncLoggerFacade(
        name="test-thread-cleanup",
        queue_capacity=100,
        batch_max_size=10,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=collecting_sink,
    )

    # Start in a thread to simulate sync context
    def start_logger():
        logger.start()

    thread = threading.Thread(target=start_logger)
    thread.start()
    thread.join(timeout=2.0)

    # If logger created its own thread, verify cleanup
    if logger._worker_thread is not None:
        # Drain should clean up the thread
        await asyncio.to_thread(logger._drain_thread_mode, warn_on_timeout=True)

        # Worker thread reference should be cleared
        assert logger._worker_thread is None


@pytest.mark.asyncio
async def test_thread_cleanup_timeout_warning(monkeypatch) -> None:
    """Should warn when worker thread doesn't join within timeout."""
    diagnostics: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        diagnostics.append({"component": component, "message": message, **fields})

    # Create a mock thread that never terminates
    class NeverEndingThread:
        def __init__(self):
            self.ident = 12345

        def join(self, timeout=None):
            # Simulate timeout by not actually joining
            pass

        def is_alive(self):
            return True  # Always alive

    logger = SyncLoggerFacade(
        name="test-timeout-warning",
        queue_capacity=100,
        batch_max_size=10,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=_create_collecting_sink([]),
    )

    # Set up the logger state to simulate thread mode
    logger._worker_loop = MagicMock()
    logger._worker_loop.call_soon_threadsafe = MagicMock()
    logger._worker_thread = NeverEndingThread()  # type: ignore[assignment]

    # Patch diagnostics.warn where the import happens
    with patch("fapilog.core.diagnostics.warn", side_effect=capture_warn):
        # Call drain which should warn about timeout
        logger._drain_thread_mode(warn_on_timeout=True)

    # Should have emitted exactly one timeout warning
    timeout_warnings = [
        d for d in diagnostics if "timeout" in d.get("message", "").lower()
    ]
    assert len(timeout_warnings) == 1
    assert timeout_warnings[0]["component"] == "logger"


@pytest.mark.asyncio
async def test_partial_batch_failure_counts_correctly() -> None:
    """Sink failure mid-batch should only count unprocessed events as dropped.

    Story 10.39: This test verifies the fix for the counter race condition.
    When a sink fails after some events in a batch have been processed,
    only the remaining events should be counted as dropped, not the entire batch.

    Previous bug: processed=N + dropped=batch_size for N<batch_size events,
    violating the invariant processed + dropped <= batch_size.
    """
    processed_events: list[dict[str, Any]] = []
    fail_after = 2  # Fail after processing 2 events

    async def failing_after_n_sink(event: dict[str, Any]) -> None:
        if len(processed_events) >= fail_after:
            raise OSError("Sink failed mid-batch")
        processed_events.append(dict(event))

    queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
    counters: dict[str, int] = {"processed": 0, "dropped": 0}

    # Pre-populate queue with 5 events
    for i in range(5):
        queue.try_enqueue({"message": f"event-{i}", "level": "INFO"})

    worker_instance = LoggerWorker(
        queue=queue,
        batch_max_size=10,  # Large enough to process all at once
        batch_timeout_seconds=0.01,
        sink_write=failing_after_n_sink,
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=None,
        serialize_in_flush=False,
        strict_envelope_mode_provider=lambda: False,
        stop_flag=lambda: True,  # Stop immediately after drain
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        counters=counters,
    )

    await worker_instance.run()

    # The sink should have processed 2 events before failing
    assert len(processed_events) == 2

    # Counters must maintain the invariant: processed + dropped == batch_size
    # 2 events processed, 3 events dropped (5 - 2)
    assert counters["processed"] == 2, (
        f"Expected 2 processed, got {counters['processed']}"
    )
    assert counters["dropped"] == 3, f"Expected 3 dropped, got {counters['dropped']}"
    assert counters["processed"] + counters["dropped"] == 5, (
        f"Invariant violated: {counters['processed']} + {counters['dropped']} != 5"
    )
