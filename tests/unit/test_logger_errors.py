"""
Test logger error handling and containment.

Scope:
- Sink exception containment
- Enricher exception containment
- Redactor exception containment
- Exception serialization
- Sink error metrics tracking

Does NOT cover:
- Exception serialization in pipeline (see test_logger_pipeline.py)
- Fast path fallback on errors (see test_logger_fastpath.py)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fapilog.core.logger import SyncLoggerFacade
from fapilog.plugins.enrichers import BaseEnricher
from fapilog.plugins.redactors import BaseRedactor


def _create_collecting_sink(collected: list[dict[str, Any]]):
    """Create a sink that collects events for verification."""

    async def sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    return sink


class TestSinkExceptionContainment:
    """Test that sink exceptions don't crash the logger."""

    def test_sink_exception_is_contained(self) -> None:
        """Sink throwing exception doesn't crash logger."""
        collected: list[dict[str, Any]] = []
        exception_count = 0

        async def exploding_sink(event: dict[str, Any]) -> None:
            nonlocal exception_count
            if "explode" in event.get("message", ""):
                exception_count += 1
                raise RuntimeError("Sink explosion!")
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="sink-explosion-test",
            queue_capacity=16,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=exploding_sink,
        )

        logger.start()

        # Submit normal, exploding, and more normal messages
        logger.info("before-1")
        logger.info("before-2")
        logger.info("explode")
        logger.info("after-1")
        logger.info("after-2")

        time.sleep(0.1)
        result = asyncio.run(logger.stop_and_drain())

        # All messages were submitted
        assert result.submitted == 5
        # Sink exception was triggered
        assert exception_count == 1
        # Logger continued after exception - messages before/after collected
        messages = [e.get("message") for e in collected]
        assert "before-1" in messages
        assert "before-2" in messages
        # Messages after exception were still processed
        assert "after-1" in messages or "after-2" in messages

    def test_intermittent_sink_failures_are_contained(self) -> None:
        """Intermittent sink failures don't stop message processing."""
        collected: list[dict[str, Any]] = []
        call_count = 0

        async def flaky_sink(event: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise RuntimeError(f"Flaky failure {call_count}")
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="flaky-sink-test",
            queue_capacity=32,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=flaky_sink,
        )

        logger.start()

        # Submit many messages
        for i in range(20):
            logger.info(f"message-{i}")

        time.sleep(0.15)
        result = asyncio.run(logger.stop_and_drain())

        # All messages submitted
        assert result.submitted == 20
        # Some messages were collected despite failures (not all failed)
        assert len(collected) > 0
        # Logger continued processing after failures
        assert result.processed > 0


class TestEnricherExceptionContainment:
    """Test that enricher exceptions don't crash the logger."""

    def test_enricher_exception_is_contained(self) -> None:
        """Enricher throwing exception doesn't crash logger."""
        collected: list[dict[str, Any]] = []

        class ExplodingEnricher(BaseEnricher):
            name = "exploder"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
                if "explode" in event.get("message", ""):
                    raise RuntimeError("Enricher explosion!")
                event["enriched"] = True
                return event

        logger = SyncLoggerFacade(
            name="enricher-explosion-test",
            queue_capacity=16,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()
        logger.enable_enricher(ExplodingEnricher())

        # Submit messages including one that triggers explosion
        logger.info("normal-1")
        logger.info("explode")
        logger.info("normal-2")

        time.sleep(0.1)
        result = asyncio.run(logger.stop_and_drain())

        # All messages submitted
        assert result.submitted == 3
        # Logger continued working - at least normal messages collected
        assert len(collected) >= 2

        # Normal messages were enriched
        normal_msgs = [e for e in collected if "normal" in e.get("message", "")]
        for msg in normal_msgs:
            assert msg.get("enriched") is True


class TestRedactorExceptionContainment:
    """Test that redactor exceptions don't crash the logger."""

    def test_redactor_exception_is_contained(self) -> None:
        """Redactor throwing exception doesn't crash logger."""
        collected: list[dict[str, Any]] = []

        class ExplodingRedactor(BaseRedactor):
            name = "redactor-exploder"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
                if "explode" in event.get("message", ""):
                    raise RuntimeError("Redactor explosion!")
                event["redacted"] = True
                return event

        logger = SyncLoggerFacade(
            name="redactor-explosion-test",
            queue_capacity=16,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()
        logger._redactors = [ExplodingRedactor()]  # type: ignore[attr-defined]

        # Submit messages
        logger.info("normal-1")
        logger.info("explode")
        logger.info("normal-2")

        time.sleep(0.1)
        result = asyncio.run(logger.stop_and_drain())

        # All messages submitted
        assert result.submitted == 3
        # Logger continued working
        assert len(collected) >= 2


class TestExceptionSerialization:
    """Test exception serialization during logging."""

    def test_exception_method_captures_traceback(self) -> None:
        """logger.exception() captures exception info with error.* fields."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="exception-test",
            queue_capacity=16,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()

        try:
            raise ValueError("test exception")
        except ValueError:
            logger.exception("caught error")

        time.sleep(0.1)
        asyncio.run(logger.stop_and_drain())

        # Exception logged
        assert len(collected) == 1
        event = collected[0]
        assert event.get("message") == "caught error"

        # v1.1 schema: exception info in diagnostics.exception
        diagnostics = event.get("diagnostics", {})
        exc_data = diagnostics.get("exception", {})
        assert exc_data.get("error.type") == "ValueError"
        assert exc_data.get("error.message") == "test exception"
        assert "error.stack" in exc_data
        # Stack should contain traceback info
        assert "ValueError" in exc_data.get("error.stack", "")

    def test_exception_with_explicit_exc_info(self) -> None:
        """Explicit exc_info tuple is captured in error.* fields."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="exc-info-test",
            queue_capacity=16,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()

        try:
            raise RuntimeError("explicit error")
        except RuntimeError:
            import sys

            logger.error("with exc_info", exc_info=sys.exc_info())

        time.sleep(0.1)
        asyncio.run(logger.stop_and_drain())

        assert len(collected) == 1
        event = collected[0]
        assert event.get("message") == "with exc_info"

        # v1.1 schema: exception info in diagnostics.exception
        diagnostics = event.get("diagnostics", {})
        exc_data = diagnostics.get("exception", {})
        assert exc_data.get("error.type") == "RuntimeError"
        assert exc_data.get("error.message") == "explicit error"
        assert "error.stack" in exc_data

    def test_exception_serialization_with_exc_param_and_exc_info_tuple(self) -> None:
        """Both exc= parameter and exc_info= tuple are captured correctly."""
        import sys

        collected: list[dict[str, Any]] = []

        async def sink(e: dict[str, Any]) -> None:
            collected.append(e)

        logger = SyncLoggerFacade(
            name="exc-both-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=sink,
            exceptions_enabled=True,
            exceptions_max_frames=5,
            exceptions_max_stack_chars=2000,
        )
        logger.start()

        # Test exc= parameter
        try:
            raise KeyError("boom")
        except KeyError as err:
            logger.error("with-exc", exc=err)

        # Test exc_info= tuple
        try:
            _ = 1 / 0
        except ZeroDivisionError:
            info = sys.exc_info()
            logger.error("with-tuple", exc_info=info)

        time.sleep(0.05)
        asyncio.run(logger.stop_and_drain())

        # Both messages should be captured
        assert len(collected) == 2

        # v1.1 schema: verify exception info was serialized in diagnostics.exception
        for e in collected:
            exc_data = e.get("diagnostics", {}).get("exception", {})
            assert "error.stack" in exc_data or "error.frames" in exc_data


class TestSinkErrorMetrics:
    """Test sink error counting and metrics tracking."""

    def test_sink_error_counts_drops_correctly(self) -> None:
        """Sink failures are counted as drops and tracked in metrics."""
        from fapilog.metrics.metrics import MetricsCollector

        calls = {"writes": 0}

        async def bad_sink(_e: dict[str, Any]) -> None:
            calls["writes"] += 1
            raise RuntimeError("sink-fail")

        metrics = MetricsCollector(enabled=True)
        logger = SyncLoggerFacade(
            name="sink-fail-metrics-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=bad_sink,
            metrics=metrics,
        )
        logger.start()

        # Submit 5 messages
        for i in range(5):
            logger.info("x", i=i)

        time.sleep(0.05)
        result = asyncio.run(logger.stop_and_drain())

        # All messages submitted
        assert result.submitted == 5
        # All should be dropped due to sink failure (may vary slightly due to timing)
        assert result.dropped >= 5, f"Expected at least 5 drops, got {result.dropped}"
        # Sink attempted each entry with batch_size=1 (may have retries)
        assert calls["writes"] >= 5, (
            f"Expected at least 5 writes, got {calls['writes']}"
        )
