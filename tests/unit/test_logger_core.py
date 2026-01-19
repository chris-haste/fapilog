"""
Test core SyncLoggerFacade behavior.

Scope:
- Logger instantiation and start
- In-loop vs thread mode detection
- Queue behavior and backpressure
- Correlation ID generation
- Batch and drain behavior
- Self-test functionality

Does NOT cover:
- AsyncLoggerFacade (see test_logger_async.py)
- Fast path serialization (see test_logger_fastpath.py)
- Threading lifecycle details (see test_logger_threading.py)
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from fapilog import get_logger
from fapilog.core import diagnostics as _diag_mod
from fapilog.core.context import request_id_var
from fapilog.core.diagnostics import _reset_for_tests, set_writer_for_tests
from fapilog.core.logger import SyncLoggerFacade


async def _collecting_sink(
    collected: list[dict[str, Any]], entry: dict[str, Any]
) -> None:
    collected.append(dict(entry))


class TestInLoopMode:
    """Tests for logger behavior when running inside an event loop."""

    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_in_loop_bind_and_flush(self) -> None:
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="t",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        # Start inside running loop: no thread should be used
        logger.start()
        assert logger._worker_thread is None  # type: ignore[attr-defined]
        assert logger._loop_thread_ident == threading.get_ident()  # type: ignore[attr-defined]

        for i in range(10):
            logger.info("m", i=i)

        # Allow time-based flush
        await asyncio.sleep(0.2)
        res = await logger.stop_and_drain()
        assert res.submitted == 10
        assert res.dropped == 0
        assert res.processed == 10
        assert len(collected) == 10

    @pytest.mark.asyncio
    async def test_in_loop_drop_when_full_nonblocking(self) -> None:
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="t",
            queue_capacity=1,
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=100,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()
        # Enqueue two items quickly; second should drop on the loop thread
        logger.info("a")
        logger.info("b")
        await asyncio.sleep(0.05)
        res = await logger.stop_and_drain()
        assert res.submitted == 2
        assert res.processed == 1
        assert res.dropped == res.submitted - res.processed


class TestThreadMode:
    """Tests for logger behavior when running outside an event loop."""

    @pytest.mark.critical
    def test_thread_mode_wait_then_drop(self) -> None:
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="t",
            queue_capacity=4,
            batch_max_size=4,
            batch_timeout_seconds=0.5,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        # Start outside of any running loop: spawns dedicated thread+loop
        logger.start()
        assert isinstance(logger._worker_thread, threading.Thread)  # type: ignore[attr-defined]

        # Saturate the queue; some submissions may drop under pressure
        for i in range(200):
            logger.info("x", i=i)

        # Drain synchronously via helper
        res = asyncio.run(logger.stop_and_drain())
        assert res.submitted == 200
        assert res.processed > 0
        assert res.processed + res.dropped == res.submitted

    def test_no_loop_creates_thread_and_in_loop_uses_tasks(self) -> None:
        collected: list[dict[str, Any]] = []
        # No running loop: thread-backed
        logger = SyncLoggerFacade(
            name="t",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()
        assert isinstance(logger._worker_thread, threading.Thread)  # type: ignore[attr-defined]
        res = asyncio.run(logger.stop_and_drain())
        assert isinstance(res.submitted, int)

        # In-loop: bind to current loop and create tasks
        async def _inner() -> None:
            collected2: list[dict[str, Any]] = []
            logger2 = SyncLoggerFacade(
                name="t2",
                queue_capacity=8,
                batch_max_size=4,
                batch_timeout_seconds=0.1,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=lambda e: _collecting_sink(collected2, e),
            )
            logger2.start()
            assert logger2._worker_thread is None  # type: ignore[attr-defined]
            # At least one worker task is created on this loop
            assert len(logger2._worker_tasks) > 0  # type: ignore[attr-defined]
            await logger2.stop_and_drain()

        asyncio.run(_inner())


class TestCorrelationId:
    """Tests for correlation ID generation."""

    @pytest.mark.asyncio
    async def test_logger_auto_generates_correlation_id(self) -> None:
        captured: list[dict[str, Any]] = []

        logger = get_logger(name="test")

        async def fake_write(entry: dict[str, Any]) -> None:
            captured.append(entry)

        # Replace sink_write on the logger (test-only replacement)
        logger._sink_write = fake_write  # type: ignore[attr-defined]

        logger.info("hello")
        await logger.stop_and_drain()

        assert captured, "Expected at least one emitted entry"
        event = captured[0]
        # v1.1 schema: correlation_id is in context
        assert "context" in event
        assert "correlation_id" in event["context"]
        assert isinstance(event["context"]["correlation_id"], str)
        assert len(event["context"]["correlation_id"]) > 0

    @pytest.mark.asyncio
    async def test_context_propagation_and_uuid_fallback(self) -> None:
        captured: list[dict[str, Any]] = []
        logger = get_logger(name="ctx-test")

        async def fake_write(entry: dict[str, Any]) -> None:
            captured.append(entry)

        logger._sink_write = fake_write  # type: ignore[attr-defined]

        # Explicit request id via context var
        token = request_id_var.set("req-123")
        try:
            logger.info("a")
        finally:
            request_id_var.reset(token)

        # No request id -> UUID fallback
        logger.info("b")

        await logger.stop_and_drain()

        assert len(captured) >= 2
        a, b = captured[0], captured[1]
        # v1.1 schema: correlation_id is in context
        assert a["context"]["correlation_id"] == "req-123"
        assert isinstance(b["context"]["correlation_id"], str)
        assert len(b["context"]["correlation_id"]) > 0


class TestBatchAndDrain:
    """Tests for batch timeout and drain behavior."""

    @pytest.mark.asyncio
    async def test_batch_and_drain_flushes_all_on_timeout_and_stop(self) -> None:
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="t",
            queue_capacity=1024,
            batch_max_size=64,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()
        for i in range(500):
            logger.info("m", i=i)
        # Allow a timeout-based flush or two to happen
        await asyncio.sleep(0.2)
        res = await logger.stop_and_drain()
        assert res.submitted == 500
        assert res.processed == 500
        assert res.dropped == 0
        assert len(collected) == 500


class TestBackpressure:
    """Tests for backpressure handling and diagnostics."""

    @pytest.mark.asyncio
    async def test_backpressure_drop_and_warn_is_emitted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        collected: list[dict[str, Any]] = []
        diag: list[dict[str, Any]] = []

        def _writer(payload: dict[str, Any]) -> None:
            diag.append(payload)

        set_writer_for_tests(_writer)
        # Force-enable internal diagnostics regardless of env
        monkeypatch.setattr(_diag_mod, "_is_enabled", lambda: True)

        logger = SyncLoggerFacade(
            name="t",
            queue_capacity=1,
            batch_max_size=1024,
            batch_timeout_seconds=0.5,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        # Overrun queue from the loop thread to trigger same-thread drop path
        for _ in range(100):
            logger.info("x")

        res = await logger.stop_and_drain()
        assert res.submitted == 100
        assert res.dropped > 0
        # Expect a throttled WARN diagnostic for backpressure component
        assert any(
            (d.get("level") == "WARN") and (d.get("component") == "backpressure")
            for d in diag
        )

    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_same_thread_drop_with_drop_on_full_false_notes_mismatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same-thread drop with drop_on_full=False emits diagnostic noting the mismatch."""
        # Reset rate limiter to avoid suppression from previous tests
        _reset_for_tests()

        collected: list[dict[str, Any]] = []
        diag: list[dict[str, Any]] = []

        def _writer(payload: dict[str, Any]) -> None:
            diag.append(payload)

        set_writer_for_tests(_writer)
        monkeypatch.setattr(_diag_mod, "_is_enabled", lambda: True)

        logger = SyncLoggerFacade(
            name="t",
            queue_capacity=1,
            batch_max_size=1024,
            batch_timeout_seconds=0.5,
            backpressure_wait_ms=1000,  # User expects to wait
            drop_on_full=False,  # User expects blocking behavior
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        # Overrun queue from the loop thread to trigger same-thread drop path
        for _ in range(100):
            logger.info("x")

        res = await logger.stop_and_drain()
        assert res.dropped > 0

        # Expect diagnostic noting that drop_on_full=False cannot be honored
        bp_diags = [
            d
            for d in diag
            if d.get("component") == "backpressure" and d.get("level") == "WARN"
        ]
        assert len(bp_diags) >= 1  # noqa: WA002 - rate limiting makes exact count unpredictable
        # Verify message includes the mismatch note
        assert any("drop_on_full=False" in d.get("message", "") for d in bp_diags)


class TestSelfTest:
    """Tests for logger self-test functionality."""

    @pytest.mark.asyncio
    async def test_logger_self_test_success(self) -> None:
        async def _sink_write(entry: dict) -> None:  # type: ignore[no-redef]
            # accept dict and do nothing
            return None

        logger = SyncLoggerFacade(
            name="selftest",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_sink_write,
        )
        res = await logger.self_test()
        assert res.get("ok") is True
        assert res.get("sink") == "default"
