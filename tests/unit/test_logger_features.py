"""
Logger Feature Tests for Core Logger

Scope:
- Enricher enable/disable operations
- Redactor stage application
- Serialize-in-flush fast path
- Self-test functionality
- Log level sampling behavior
- Metrics integration (counters and histograms)
- Context binding precedence
- No-copy enqueue (object identity preservation)

Does NOT cover:
- Threading and worker lifecycle (see test_logger_threading.py)
- Error containment (see test_logger_errors.py)
- Pipeline stages and sampling (see test_logger_pipeline.py)
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade
from fapilog.metrics.metrics import MetricsCollector


class _SimpleEnricher:
    """Test enricher that adds x=1 to events."""

    name = "x_enricher"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        event["x"] = 1
        return event


class _SimpleRedactor:
    """Test redactor that removes x and adds redacted=True."""

    name = "mask_x"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
        e = dict(event)
        e.pop("x", None)
        e["redacted"] = True
        return e


class TestEnricherOperations:
    """Test enricher enable/disable operations."""

    @pytest.mark.asyncio
    async def test_enable_enricher_adds_fields_to_output(self) -> None:
        """Enabled enricher adds its fields to log events."""
        collected: list[dict[str, Any]] = []

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="enricher-enable-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
        )
        logger.start()
        logger.enable_enricher(_SimpleEnricher())

        logger.info("test-message")
        await logger.stop_and_drain()

        # Verify enricher added its field
        assert len(collected) == 1
        event = collected[0]
        assert event.get("x") == 1
        assert event.get("message") == "test-message"

    @pytest.mark.asyncio
    async def test_disable_enricher_removes_by_name(self) -> None:
        """Disabling enricher by name removes it from pipeline."""
        collected: list[dict[str, Any]] = []

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="enricher-disable-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
        )
        logger.start()

        # Enable then disable
        logger.enable_enricher(_SimpleEnricher())
        logger.disable_enricher("x_enricher")

        logger.info("test-message")
        await logger.stop_and_drain()

        # Verify enricher field is NOT present
        assert len(collected) == 1
        event = collected[0]
        assert "x" not in event
        assert event.get("message") == "test-message"

    @pytest.mark.asyncio
    async def test_enable_disable_enricher_affects_output(self) -> None:
        """Enable/disable cycle correctly toggles enricher effect."""
        collected: list[dict[str, Any]] = []

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        # First logger with enricher enabled
        logger1 = SyncLoggerFacade(
            name="enricher-test-1",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
        )
        logger1.start()
        logger1.enable_enricher(_SimpleEnricher())
        logger1.info("with-enricher")
        await logger1.stop_and_drain()

        # Verify enricher added its field
        assert len(collected) == 1
        assert collected[0].get("x") == 1

        # Second logger with enricher disabled
        collected.clear()
        logger2 = SyncLoggerFacade(
            name="enricher-test-2",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
        )
        logger2.start()
        logger2.enable_enricher(_SimpleEnricher())
        logger2.disable_enricher("x_enricher")
        logger2.info("without-enricher")
        await logger2.stop_and_drain()

        # Verify enricher field is NOT present
        assert len(collected) == 1
        assert "x" not in collected[0]


class TestRedactorStage:
    """Test redactor stage application."""

    @pytest.mark.asyncio
    async def test_redactor_stage_applies_when_configured(self) -> None:
        """Configured redactor removes specified fields and adds marker."""
        collected: list[dict[str, Any]] = []

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="redactor-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
        )

        # Inject redactor and enricher
        logger._redactors = [_SimpleRedactor()]  # type: ignore[attr-defined]
        logger.start()
        logger.enable_enricher(_SimpleEnricher())

        logger.info("test-message")
        await logger.stop_and_drain()

        # Verify: enricher added x, then redactor removed it and added marker
        assert len(collected) == 1
        event = collected[0]
        assert "x" not in event  # Redactor removed it
        assert event.get("redacted") is True  # Redactor added marker
        assert event.get("message") == "test-message"


class TestSerializeInFlush:
    """Test serialize_in_flush fast path."""

    @pytest.mark.asyncio
    async def test_serialize_in_flush_calls_write_serialized(self) -> None:
        """When serialize_in_flush=True, write_serialized is called with bytes."""
        serialized_calls: list[bytes] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            pass  # Should not be called

        async def sink_write_serialized(view: Any) -> None:
            serialized_calls.append(bytes(view.data))

        logger = SyncLoggerFacade(
            name="serialize-flush-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink_write,
            sink_write_serialized=sink_write_serialized,
            serialize_in_flush=True,
        )
        logger.start()
        logger.info("test-message", key="value")

        await asyncio.sleep(0.1)
        await logger.stop_and_drain()

        # Verify write_serialized was called with actual bytes
        assert len(serialized_calls) == 1
        serialized_bytes = serialized_calls[0]
        assert isinstance(serialized_bytes, bytes)
        # Should contain JSON data
        assert b"test-message" in serialized_bytes


class TestSelfTest:
    """Test self-test functionality."""

    @pytest.mark.asyncio
    async def test_self_test_returns_ok_and_writes_event(self) -> None:
        """Self-test returns ok=True and writes a test event."""
        collected: list[dict[str, Any]] = []

        async def sink(entry: dict[str, Any]) -> None:
            collected.append(entry)

        logger = SyncLoggerFacade(
            name="self-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink,
        )

        result = await logger.self_test()

        # Verify self-test returned success
        assert result.get("ok") is True

        # Verify test event was written
        assert len(collected) == 1
        assert collected[0]["message"] == "self_test"


class TestLogLevelSampling:
    """Test log level sampling behavior."""

    @pytest.mark.asyncio
    async def test_warning_bypasses_sampling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WARNING level messages bypass low sampling rate."""
        # Set very low sampling rate
        monkeypatch.setenv("FAPILOG_OBSERVABILITY__LOGGING__SAMPLING_RATE", "0.01")

        collected: list[dict[str, Any]] = []

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="sampling-test",
            queue_capacity=4096,
            batch_max_size=1024,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=sink,
        )
        logger.start()

        # WARNING should bypass sampling
        logger.warning("warning-message")
        await logger.stop_and_drain()

        # Verify warning message arrived despite low sampling rate
        messages = [e.get("message") for e in collected]
        assert "warning-message" in messages


class TestMetricsIntegration:
    """Test metrics integration."""

    @pytest.mark.asyncio
    async def test_metrics_collector_receives_events(self) -> None:
        """MetricsCollector receives event counts."""
        metrics = MetricsCollector(enabled=True)
        collected: list[dict[str, Any]] = []

        async def sink(entry: dict[str, Any]) -> None:
            collected.append(entry)

        logger = SyncLoggerFacade(
            name="metrics-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink,
            metrics=metrics,
        )

        logger.info("test-message")
        result = await logger.stop_and_drain()

        # Verify metrics tracked submission
        assert result.submitted == 1
        assert result.processed == 1
        assert result.dropped == 0
        assert len(collected) == 1


class TestContextBinding:
    """Test context binding and unbinding behavior."""

    @pytest.mark.asyncio
    async def test_context_binding_precedence_and_unbind_clear(self) -> None:
        """Per-call context overrides bound context; unbind and clear work correctly."""
        collected: list[dict[str, Any]] = []

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="ctx-binding-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=sink,
        )
        logger.start()

        # Bind context with two fields
        logger.bind(user="A", trace="t1")
        logger.info("m1", user="B")  # per-call overrides bound
        await asyncio.sleep(0.02)

        logger.unbind("trace")
        logger.info("m2")
        await asyncio.sleep(0.02)

        logger.clear_context()
        logger.info("m3", user="C")
        await asyncio.sleep(0.02)

        await logger.stop_and_drain()

        # Verify exactly 3 messages processed
        assert len(collected) == 3, f"Expected 3 messages, got {len(collected)}"

        m1, m2, m3 = collected[0], collected[1], collected[2]
        # m1: per-call user="B" overrides bound user="A"
        assert m1["data"].get("user") == "B"
        # m2: trace was unbound, so shouldn't be present
        assert "trace" not in m2["data"]
        # m3: context cleared, only per-call user="C"
        assert m3["data"].get("user") == "C"


class TestEnricherEdgeCases:
    """Test enricher edge cases."""

    @pytest.mark.asyncio
    async def test_enricher_without_name_attribute_is_ignored(self) -> None:
        """Enricher without name attribute is silently ignored (no-op)."""
        collected: list[dict[str, Any]] = []

        class NamelessEnricher:
            # No name attribute
            async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
                event["enriched"] = True
                return event

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="nameless-enricher-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=sink,
        )
        logger.start()

        # This should be a no-op since enricher has no name
        logger.enable_enricher(NamelessEnricher())  # type: ignore[arg-type]
        logger.info("test")
        await asyncio.sleep(0.02)
        result = await logger.stop_and_drain()

        # Message should be processed
        assert result.submitted == 1
        assert result.processed == 1
        # Enricher should not have been added since it has no name
        assert len(logger._enrichers) == 0  # type: ignore[attr-defined]
        # Event should NOT have "enriched" field (enricher wasn't applied)
        assert len(collected) == 1
        assert "enriched" not in collected[0]

    @pytest.mark.asyncio
    async def test_disable_nonexistent_enricher_is_noop(self) -> None:
        """Disabling non-existent enricher is a silent no-op."""
        collected: list[dict[str, Any]] = []

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="disable-nonexistent-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=sink,
        )
        logger.start()

        # Try to disable non-existent enricher (should be no-op, no error)
        logger.disable_enricher("nonexistent")
        logger.info("test")
        await asyncio.sleep(0.02)

        result = await logger.stop_and_drain()

        # Message should still be processed normally
        assert result.submitted == 1
        assert result.processed == 1
        assert len(logger._enrichers) == 0  # type: ignore[attr-defined]
        assert len(collected) == 1
        assert collected[0]["message"] == "test"


def _sum_samples(registry: Any, name: str, sample_suffix: str) -> float:
    """Sum samples from prometheus registry for a given metric name."""
    total = 0.0
    for metric in registry.collect():
        if metric.name == name:
            for s in metric.samples:
                if s.name.endswith(sample_suffix):
                    total += float(s.value)
    return total


class TestMetricsPrometheus:
    """Test prometheus metrics recording."""

    @pytest.mark.asyncio
    async def test_sink_error_counter_and_flush_histogram_recorded(self) -> None:
        """Sink errors increment counter and flush histogram records timing."""
        metrics = MetricsCollector(enabled=True)

        async def raising_sink(_entry: dict[str, Any]) -> None:
            raise RuntimeError("fail")

        logger = SyncLoggerFacade(
            name="metrics-prometheus-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=raising_sink,
            metrics=metrics,
        )
        logger.start()
        logger.info("x")
        await asyncio.sleep(0.05)
        await logger.stop_and_drain()

        reg = metrics.registry
        # Flush histogram should have exactly one count (one flush occurred)
        flush_count = _sum_samples(reg, "fapilog_flush_seconds", "_count")
        assert flush_count == 1.0


def _cross_thread_submit(logger: SyncLoggerFacade, sentinel: object) -> None:
    """Submit from a different thread to exercise cross-thread path."""
    logger.info("x", marker=sentinel)


class TestNoCopyEnqueue:
    """Test that enqueue preserves object identity (no-copy behavior)."""

    @pytest.mark.asyncio
    async def test_same_thread_enqueue_preserves_identity(self) -> None:
        """Same-thread enqueue preserves object identity in metadata."""
        seen: list[dict[str, Any]] = []

        async def capture(entry: dict[str, Any]) -> None:
            seen.append(entry)

        logger = SyncLoggerFacade(
            name="no-copy-same-thread",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=capture,
        )
        logger.start()

        sentinel = object()
        logger.info("m", sentinel=sentinel)
        await asyncio.sleep(0.05)
        await logger.stop_and_drain()

        assert seen, "expected at least one entry"
        # v1.1 schema: custom fields in data
        data = seen[0].get("data", {})
        # The sentinel is embedded under data.sentinel; ensure same identity
        assert data.get("sentinel") is sentinel

    @pytest.mark.asyncio
    async def test_cross_thread_enqueue_preserves_identity(self) -> None:
        """Cross-thread enqueue preserves object identity in metadata."""
        seen: list[dict[str, Any]] = []

        async def capture(entry: dict[str, Any]) -> None:
            seen.append(entry)

        logger = SyncLoggerFacade(
            name="no-copy-cross-thread",
            queue_capacity=8,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=capture,
        )
        logger.start()
        sentinel = object()
        # Submit from a thread
        await asyncio.to_thread(_cross_thread_submit, logger, sentinel)
        await asyncio.sleep(0.1)
        await logger.stop_and_drain()

        assert seen, "expected emitted entries"
        # v1.1 schema: custom fields in data
        data = seen[0].get("data", {})
        assert data.get("marker") is sentinel
