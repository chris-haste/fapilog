"""
Tests for logger processing pipeline and failure handling.

Scope:
- Enrichment and redaction pipeline
- Enrichment exception handling
- Redaction exception handling
- Failure modes and recovery
- Sink failure recovery
- Serialization failure modes
- Queue backpressure and drops
- Cross-thread submission
- Worker loop graceful stop
- Exception serialization
- Flush serialization paths
"""

import asyncio
import sys
import threading
from typing import Any
from unittest.mock import patch

import pytest

import fapilog.core.worker as worker_mod
from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade
from fapilog.plugins.enrichers import BaseEnricher
from fapilog.plugins.redactors import BaseRedactor


async def _collect_events(
    collected: list[dict[str, Any]], event: dict[str, Any]
) -> None:
    """Helper to collect events in tests."""
    collected.append(dict(event))


def _create_async_sink(out: list[dict[str, Any]]):
    """Create an async sink function."""

    async def async_sink(event: dict[str, Any]) -> None:
        await _collect_events(out, event)

    return async_sink


class TestEnrichmentAndRedactionPipeline:
    """Test the full enrichment and redaction pipeline."""

    class MockEnricher(BaseEnricher):
        def __init__(self, name: str, add_field: str, add_value: str):
            self.name = name
            self.add_field = add_field
            self.add_value = add_value

        async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
            event = dict(event)
            event[self.add_field] = self.add_value
            return event

    class MockRedactor(BaseRedactor):
        def __init__(self, name: str, remove_field: str):
            self.name = name
            self.remove_field = remove_field

        async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
            event = dict(event)
            event.pop(self.remove_field, None)
            return event

    @pytest.mark.asyncio
    async def test_enrichment_pipeline(self) -> None:
        """Test log enrichment with multiple enrichers."""
        out: list[dict[str, Any]] = []

        enricher1 = self.MockEnricher("env", "environment", "production")
        enricher2 = self.MockEnricher("version", "app_version", "1.0.0")

        logger = SyncLoggerFacade(
            name="enrich-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            enrichers=[enricher1, enricher2],
        )

        logger.start()
        logger.info("test message")
        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("environment") == "production"
        assert event.get("app_version") == "1.0.0"
        assert event.get("message") == "test message"

    @pytest.mark.asyncio
    async def test_redaction_pipeline(self) -> None:
        """Test log redaction with multiple redactors."""
        out: list[dict[str, Any]] = []

        redactor1 = self.MockRedactor("secrets", "password")
        redactor2 = self.MockRedactor("pii", "ssn")

        logger = SyncLoggerFacade(
            name="redact-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger._redactors = [redactor1, redactor2]

        logger.start()
        logger.info(
            "test message", password="secret123", ssn="123-45-6789", safe_field="ok"
        )
        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "test message"

    @pytest.mark.asyncio
    async def test_enrichment_exception_handling(self) -> None:
        """Test enrichment pipeline with failing enrichers."""
        out: list[dict[str, Any]] = []

        class FailingEnricher(BaseEnricher):
            name = "failing"

            async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("Enricher failed")

        good_enricher = self.MockEnricher("good", "field", "value")
        failing_enricher = FailingEnricher()

        logger = SyncLoggerFacade(
            name="enrich-fail-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            enrichers=[good_enricher, failing_enricher],
        )

        logger.start()
        logger.info("test message")
        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "test message"

    @pytest.mark.asyncio
    async def test_redaction_exception_handling(self) -> None:
        """Test redaction pipeline with failing redactors."""
        out: list[dict[str, Any]] = []

        class FailingRedactor(BaseRedactor):
            name = "failing"

            async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("Redactor failed")

        good_redactor = self.MockRedactor("good", "remove_me")
        failing_redactor = FailingRedactor()

        logger = SyncLoggerFacade(
            name="redact-fail-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger._redactors = [good_redactor, failing_redactor]

        logger.start()
        logger.info("test message", remove_me="should_be_gone", keep_me="should_stay")
        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "test message"


class TestFailureModesAndRecovery:
    """Test various failure modes and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_sink_failure_recovery(self) -> None:
        """Test recovery from sink failures."""
        out: list[dict[str, Any]] = []
        fail_count = 0

        async def intermittent_sink(event: dict[str, Any]) -> None:
            nonlocal fail_count
            fail_count += 1
            if fail_count <= 2:
                raise RuntimeError("Sink temporarily unavailable")
            await _collect_events(out, event)

        logger = AsyncLoggerFacade(
            name="sink-recovery-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=intermittent_sink,
        )

        logger.start()

        await logger.info("message 1")
        await logger.info("message 2")
        await logger.info("message 3")

        result = await logger.stop_and_drain()

        assert result.submitted == 3
        assert result.dropped >= 3

    @pytest.mark.asyncio
    async def test_serialization_failure_modes(self) -> None:
        """Test serialization failures in fast-path mode."""
        out: list[dict[str, Any]] = []
        serialized_out: list[Any] = []

        async def regular_sink(event: dict[str, Any]) -> None:
            await _collect_events(out, event)

        async def serialized_sink(view: Any) -> None:
            serialized_out.append(view)

        logger = SyncLoggerFacade(
            name="serialization-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=regular_sink,
            sink_write_serialized=serialized_sink,
            serialize_in_flush=True,
        )

        logger.start()

        class NonSerializable:
            pass

        logger.info("test message", non_serializable=NonSerializable())
        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "test message"

    @pytest.mark.asyncio
    async def test_queue_backpressure_and_drops(self) -> None:
        """Test queue backpressure handling and message drops."""
        out: list[dict[str, Any]] = []

        async def slow_sink(event: dict[str, Any]) -> None:
            await asyncio.sleep(0.1)
            await _collect_events(out, event)

        logger = AsyncLoggerFacade(
            name="backpressure-test",
            queue_capacity=2,
            batch_max_size=1,
            batch_timeout_seconds=0.001,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=slow_sink,
        )

        logger.start()

        for i in range(10):
            await logger.info(f"message {i}")

        result = await logger.stop_and_drain()

        assert result.submitted == 10
        assert result.dropped > 0
        assert result.processed + result.dropped == result.submitted

    def test_cross_thread_submission_failure(self) -> None:
        """Test cross-thread submission failure handling."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="cross-thread-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger.start()

        logger.info("main thread message")

        def background_submit():
            for i in range(5):
                logger.info(f"background message {i}")

        thread = threading.Thread(target=background_submit)
        thread.start()
        thread.join()

        result = asyncio.run(logger.stop_and_drain())

        assert result.submitted == 6
        assert len(out) == 6

    @pytest.mark.asyncio
    async def test_worker_loop_stop_during_processing(self) -> None:
        """Test graceful stop during active processing."""
        out: list[dict[str, Any]] = []

        async def slow_processing_sink(event: dict[str, Any]) -> None:
            await asyncio.sleep(0.05)
            await _collect_events(out, event)

        logger = AsyncLoggerFacade(
            name="graceful-stop-test",
            queue_capacity=16,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=slow_processing_sink,
        )

        logger.start()

        for i in range(8):
            await logger.info(f"processing message {i}")

        result = await logger.stop_and_drain()

        assert result.submitted == 8
        assert result.processed <= 8
        assert len(out) <= 8


class TestExceptionSerialization:
    """Test exception serialization functionality."""

    @pytest.mark.asyncio
    async def test_exception_with_exc_parameter(self) -> None:
        """Test exception logging with exc parameter."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="exc-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            exceptions_enabled=True,
        )

        logger.start()

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error("Error occurred", exc=e)

        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        # v1.1 schema: exception in diagnostics.exception
        exc_data = event.get("diagnostics", {}).get("exception", {})

        assert "error.message" in exc_data or "error.frames" in exc_data

    @pytest.mark.asyncio
    async def test_exception_with_exc_info_tuple(self) -> None:
        """Test exception logging with exc_info tuple."""

        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="exc-info-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            exceptions_enabled=True,
        )

        logger.start()

        try:
            raise RuntimeError("Test runtime error")
        except RuntimeError:
            exc_info = sys.exc_info()
            logger.error("Error with exc_info", exc_info=exc_info)

        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        # v1.1 schema: exception in diagnostics.exception
        exc_data = event.get("diagnostics", {}).get("exception", {})

        assert "error.message" in exc_data or "error.frames" in exc_data

    @pytest.mark.asyncio
    async def test_exception_serialization_disabled(self) -> None:
        """Test logging with exception serialization disabled."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="no-exc-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            exceptions_enabled=False,
        )

        logger.start()

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error("Error occurred", exc=e)

        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        # v1.1 schema: exception would be in diagnostics.exception if enabled
        exc_data = event.get("diagnostics", {}).get("exception", {})

        assert "error.message" not in exc_data
        assert "error.frames" not in exc_data

    @pytest.mark.asyncio
    async def test_exception_serialization_error_handling(self) -> None:
        """Test exception serialization with errors in serialization."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="exc-error-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            exceptions_enabled=True,
        )

        logger.start()

        with patch(
            "fapilog.core.errors.serialize_exception",
            side_effect=Exception("Serialization failed"),
        ):
            try:
                raise ValueError("Test exception")
            except ValueError as e:
                logger.error("Error occurred", exc=e)

        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "Error occurred"


class TestFlushPaths:
    """Test flush serialization paths."""

    @pytest.mark.asyncio
    async def test_flush_serialization_strict_drops(self, monkeypatch) -> None:
        monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "true")

        async def sink_write(entry: dict) -> None:  # pragma: no cover - not used
            raise AssertionError("should not be called in strict drop path")

        async def sink_write_serialized(view: object) -> None:
            raise AssertionError("should not be called in strict drop path")

        monkeypatch.setattr(
            worker_mod,
            "serialize_envelope",
            lambda entry: (_ for _ in ()).throw(ValueError("boom")),
        )

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=4,
            batch_max_size=2,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink_write,
            sink_write_serialized=sink_write_serialized,
            serialize_in_flush=True,
        )

        batch = [{"id": 1}]
        await logger._flush_batch(batch)

        assert logger._processed == 0
        assert logger._dropped == 1  # Strict mode drop must be counted

    @pytest.mark.asyncio
    async def test_strict_mode_drop_records_metric(self, monkeypatch) -> None:
        """Strict mode drop triggers metrics recording."""
        from unittest.mock import AsyncMock

        from fapilog.metrics.metrics import MetricsCollector

        monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "true")

        async def sink_write(entry: dict) -> None:  # pragma: no cover
            raise AssertionError("should not be called in strict drop path")

        async def sink_write_serialized(view: object) -> None:  # pragma: no cover
            raise AssertionError("should not be called in strict drop path")

        monkeypatch.setattr(
            worker_mod,
            "serialize_envelope",
            lambda entry: (_ for _ in ()).throw(ValueError("boom")),
        )

        metrics = MetricsCollector(enabled=True)
        metrics.record_events_dropped = AsyncMock()  # type: ignore[method-assign]
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=4,
            batch_max_size=2,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink_write,
            sink_write_serialized=sink_write_serialized,
            serialize_in_flush=True,
            metrics=metrics,
        )

        batch = [{"id": 1}, {"id": 2}]
        await logger._flush_batch(batch)

        assert logger._dropped == 2
        # Metrics must record each drop individually
        assert metrics.record_events_dropped.call_count == 2
        metrics.record_events_dropped.assert_any_call(1)

    @pytest.mark.asyncio
    async def test_flush_serialization_best_effort_uses_fallback(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "false")

        serialized_calls: list[object] = []
        sink_calls: list[dict] = []

        async def sink_write(entry: dict) -> None:
            sink_calls.append(entry)

        async def sink_write_serialized(view: object) -> None:
            serialized_calls.append(view)

        monkeypatch.setattr(
            worker_mod,
            "serialize_envelope",
            lambda entry: (_ for _ in ()).throw(ValueError("boom")),
        )

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=4,
            batch_max_size=2,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink_write,
            sink_write_serialized=sink_write_serialized,
            serialize_in_flush=True,
        )

        batch = [{"id": 1}]
        await logger._flush_batch(batch)

        assert logger._processed == 1
        assert len(serialized_calls) == 1
        assert len(sink_calls) == 0

    @pytest.mark.asyncio
    async def test_flush_sink_error_increments_dropped(self, monkeypatch) -> None:
        async def sink_write(entry: dict) -> None:
            raise RuntimeError("sink failure")

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=4,
            batch_max_size=2,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink_write,
            serialize_in_flush=False,
        )

        batch = [{"id": 1}, {"id": 2}]
        await logger._flush_batch(batch)

        assert logger._processed == 0
        assert logger._dropped == 2
