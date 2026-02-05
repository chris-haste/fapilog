"""Tests for enqueue_with_backpressure metrics resilience.

Verifies that metrics failures do not affect enqueue success.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.worker import enqueue_with_backpressure


class FailingMetrics:
    """Mock metrics collector that raises exceptions on all calls."""

    async def set_queue_high_watermark(self, value: int) -> None:
        raise RuntimeError("metrics failure")

    async def record_backpressure_wait(self, count: int = 1) -> None:
        raise RuntimeError("metrics failure")

    async def record_events_dropped(self, count: int = 1) -> None:
        raise RuntimeError("metrics failure")


class FailingQueue:
    """Mock queue that fails on await_enqueue."""

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def try_enqueue(self, payload: dict[str, Any]) -> bool:
        """Always return False to trigger slow/blocking path."""
        return False

    async def await_enqueue(
        self, payload: dict[str, Any], *, timeout: float | None
    ) -> None:
        """Always raise to test exception handling."""
        raise RuntimeError("queue failure")

    def qsize(self) -> int:
        return len(self._items)


class TestEnqueueMetricsResilience:
    """Tests that enqueue_with_backpressure tolerates metrics failures."""

    @pytest.fixture
    def queue(self) -> NonBlockingRingQueue[dict[str, Any]]:
        """Create a test queue with small capacity."""
        return NonBlockingRingQueue(capacity=2)

    @pytest.fixture
    def failing_metrics(self) -> FailingMetrics:
        """Create metrics that fail on every call."""
        return FailingMetrics()

    @pytest.fixture
    def payload(self) -> dict[str, Any]:
        """Create a test payload."""
        return {"level": "INFO", "message": "test"}

    @pytest.mark.asyncio
    async def test_fast_path_succeeds_despite_metrics_failure(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        failing_metrics: FailingMetrics,
        payload: dict[str, Any],
    ) -> None:
        """Fast path enqueue succeeds even when set_queue_high_watermark fails."""
        success, watermark = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=0.0,
            drop_on_full=True,
            metrics=failing_metrics,  # type: ignore[arg-type]
            current_high_watermark=0,
        )

        assert success is True
        assert watermark == 1
        assert queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_slow_path_backpressure_wait_metrics_failure(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        failing_metrics: FailingMetrics,
        payload: dict[str, Any],
    ) -> None:
        """Slow path succeeds even when record_backpressure_wait fails."""
        # Fill queue to trigger backpressure path
        queue.try_enqueue({"level": "INFO", "message": "fill1"})
        queue.try_enqueue({"level": "INFO", "message": "fill2"})

        # Drain one item asynchronously to allow enqueue
        async def drain_after_delay() -> None:
            import asyncio

            await asyncio.sleep(0.01)
            queue.try_dequeue()

        import asyncio

        asyncio.create_task(drain_after_delay())

        success, _ = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=1.0,
            drop_on_full=True,
            metrics=failing_metrics,  # type: ignore[arg-type]
            current_high_watermark=0,
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_slow_path_drop_metrics_failure(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        failing_metrics: FailingMetrics,
        payload: dict[str, Any],
    ) -> None:
        """Slow path returns False when timeout expires, even if metrics fails."""
        # Fill queue completely
        queue.try_enqueue({"level": "INFO", "message": "fill1"})
        queue.try_enqueue({"level": "INFO", "message": "fill2"})

        success, _ = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=0.01,  # Short timeout
            drop_on_full=True,
            metrics=failing_metrics,  # type: ignore[arg-type]
            current_high_watermark=0,
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_slow_path_watermark_metrics_failure_after_enqueue(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        failing_metrics: FailingMetrics,
        payload: dict[str, Any],
    ) -> None:
        """Slow path succeeds even when watermark metrics fails after enqueue."""
        # Fill queue to trigger slow path
        queue.try_enqueue({"level": "INFO", "message": "fill1"})
        queue.try_enqueue({"level": "INFO", "message": "fill2"})

        # Drain to allow enqueue
        async def drain_after_delay() -> None:
            import asyncio

            await asyncio.sleep(0.01)
            queue.try_dequeue()
            queue.try_dequeue()  # Drain both to trigger watermark update

        import asyncio

        asyncio.create_task(drain_after_delay())

        success, watermark = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=1.0,
            drop_on_full=True,
            metrics=failing_metrics,  # type: ignore[arg-type]
            current_high_watermark=0,
        )

        assert success is True
        assert watermark == 1

    @pytest.mark.asyncio
    async def test_blocking_path_backpressure_wait_metrics_failure(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        failing_metrics: FailingMetrics,
        payload: dict[str, Any],
    ) -> None:
        """Blocking path succeeds even when record_backpressure_wait fails."""
        # Fill queue
        queue.try_enqueue({"level": "INFO", "message": "fill1"})
        queue.try_enqueue({"level": "INFO", "message": "fill2"})

        # Drain one item asynchronously
        async def drain_after_delay() -> None:
            import asyncio

            await asyncio.sleep(0.01)
            queue.try_dequeue()

        import asyncio

        asyncio.create_task(drain_after_delay())

        success, _ = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=0.0,  # No timeout triggers blocking path
            drop_on_full=False,  # Don't drop = blocking
            metrics=failing_metrics,  # type: ignore[arg-type]
            current_high_watermark=0,
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_blocking_path_watermark_metrics_failure(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        failing_metrics: FailingMetrics,
        payload: dict[str, Any],
    ) -> None:
        """Blocking path succeeds even when watermark update fails."""
        # Fill queue
        queue.try_enqueue({"level": "INFO", "message": "fill1"})
        queue.try_enqueue({"level": "INFO", "message": "fill2"})

        # Drain both items asynchronously to trigger watermark check
        async def drain_after_delay() -> None:
            import asyncio

            await asyncio.sleep(0.01)
            queue.try_dequeue()
            queue.try_dequeue()

        import asyncio

        asyncio.create_task(drain_after_delay())

        success, watermark = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=0.0,
            drop_on_full=False,
            metrics=failing_metrics,  # type: ignore[arg-type]
            current_high_watermark=0,
        )

        assert success is True
        assert watermark == 1

    @pytest.mark.asyncio
    async def test_drop_on_full_metrics_failure(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        failing_metrics: FailingMetrics,
        payload: dict[str, Any],
    ) -> None:
        """Drop on full returns False even when record_events_dropped fails."""
        # Fill queue completely
        queue.try_enqueue({"level": "INFO", "message": "fill1"})
        queue.try_enqueue({"level": "INFO", "message": "fill2"})

        success, _ = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=0.0,  # No timeout
            drop_on_full=True,  # Drop immediately
            metrics=failing_metrics,  # type: ignore[arg-type]
            current_high_watermark=0,
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_blocking_path_await_enqueue_fails_with_metrics_failure(
        self,
        failing_metrics: FailingMetrics,
        payload: dict[str, Any],
    ) -> None:
        """Blocking path returns False when await_enqueue and record_events_dropped both fail."""
        failing_queue = FailingQueue()

        success, _ = await enqueue_with_backpressure(
            failing_queue,  # type: ignore[arg-type]
            payload,
            timeout=0.0,  # No timeout triggers blocking path
            drop_on_full=False,  # Blocking mode
            metrics=failing_metrics,  # type: ignore[arg-type]
            current_high_watermark=0,
        )

        assert success is False


class TestEnqueueMetricsCalledCorrectly:
    """Verify metrics are called when they don't fail."""

    @pytest.fixture
    def queue(self) -> NonBlockingRingQueue[dict[str, Any]]:
        """Create a test queue."""
        return NonBlockingRingQueue(capacity=10)

    @pytest.fixture
    def mock_metrics(self) -> AsyncMock:
        """Create mock metrics that track calls."""
        metrics = AsyncMock()
        metrics.set_queue_high_watermark = AsyncMock()
        metrics.record_backpressure_wait = AsyncMock()
        metrics.record_events_dropped = AsyncMock()
        return metrics

    @pytest.fixture
    def payload(self) -> dict[str, Any]:
        """Create a test payload."""
        return {"level": "INFO", "message": "test"}

    @pytest.mark.asyncio
    async def test_fast_path_calls_watermark_on_new_high(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        mock_metrics: AsyncMock,
        payload: dict[str, Any],
    ) -> None:
        """Fast path calls set_queue_high_watermark when queue size exceeds watermark."""
        success, watermark = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=0.0,
            drop_on_full=True,
            metrics=mock_metrics,
            current_high_watermark=0,
        )

        assert success is True
        assert watermark == 1
        mock_metrics.set_queue_high_watermark.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_fast_path_skips_watermark_when_not_exceeded(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        mock_metrics: AsyncMock,
        payload: dict[str, Any],
    ) -> None:
        """Fast path skips watermark update when queue size doesn't exceed watermark."""
        success, watermark = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=0.0,
            drop_on_full=True,
            metrics=mock_metrics,
            current_high_watermark=100,  # Already high
        )

        assert success is True
        assert watermark == 100  # Unchanged
        mock_metrics.set_queue_high_watermark.assert_not_called()

    @pytest.mark.asyncio
    async def test_drop_on_full_calls_events_dropped(
        self,
        queue: NonBlockingRingQueue[dict[str, Any]],
        mock_metrics: AsyncMock,
        payload: dict[str, Any],
    ) -> None:
        """Drop on full path calls record_events_dropped."""
        # Fill queue
        for i in range(10):
            queue.try_enqueue({"level": "INFO", "message": f"fill{i}"})

        success, _ = await enqueue_with_backpressure(
            queue,
            payload,
            timeout=0.0,
            drop_on_full=True,
            metrics=mock_metrics,
            current_high_watermark=0,
        )

        assert success is False
        mock_metrics.record_events_dropped.assert_called_once_with(1)
