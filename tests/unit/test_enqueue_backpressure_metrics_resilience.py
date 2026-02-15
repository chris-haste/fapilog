"""Tests for _try_enqueue_with_metrics on the logger mixin.

Verifies that the direct try_enqueue path correctly updates
high watermark and returns success/failure.
"""

from __future__ import annotations

from typing import Any

from fapilog.core.logger import AsyncLoggerFacade


def _make_logger(queue_capacity: int = 2) -> AsyncLoggerFacade:
    """Create a minimal async logger for testing enqueue."""
    return AsyncLoggerFacade(
        name="test",
        queue_capacity=queue_capacity,
        batch_max_size=10,
        batch_timeout_seconds=1.0,
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=lambda e: None,  # type: ignore[arg-type, return-value]
    )


class TestTryEnqueueWithMetrics:
    """Tests for _try_enqueue_with_metrics on the logger."""

    def test_enqueue_succeeds_and_updates_watermark(self) -> None:
        """Successful enqueue updates the high watermark."""
        logger = _make_logger(queue_capacity=10)
        payload: dict[str, Any] = {"level": "INFO", "message": "test"}

        ok = logger._try_enqueue_with_metrics(payload)

        assert ok is True
        assert logger._queue_high_watermark == 1
        assert logger._queue.qsize() == 1

    def test_enqueue_fails_when_queue_full(self) -> None:
        """Enqueue returns False when queue is at capacity."""
        logger = _make_logger(queue_capacity=2)

        # Fill via the method under test so watermark is also tracked
        logger._try_enqueue_with_metrics({"level": "INFO", "message": "fill1"})
        logger._try_enqueue_with_metrics({"level": "INFO", "message": "fill2"})
        assert logger._queue_high_watermark == 2

        ok = logger._try_enqueue_with_metrics({"level": "INFO", "message": "overflow"})

        assert ok is False
        assert logger._queue.qsize() == 2

    def test_watermark_only_increases(self) -> None:
        """High watermark only increases, never decreases."""
        logger = _make_logger(queue_capacity=10)

        # Enqueue 3 items — watermark rises to 3
        for i in range(3):
            logger._try_enqueue_with_metrics({"level": "INFO", "message": f"msg{i}"})
        assert logger._queue_high_watermark == 3

        # Dequeue 2 items
        logger._queue.try_dequeue()
        logger._queue.try_dequeue()

        # Enqueue 1 more — qsize=2, watermark stays at 3 (doesn't decrease)
        logger._try_enqueue_with_metrics({"level": "INFO", "message": "new"})
        assert logger._queue_high_watermark == 3

        # Enqueue 3 more — qsize=5, watermark rises past previous high
        for i in range(3):
            logger._try_enqueue_with_metrics({"level": "INFO", "message": f"extra{i}"})
        assert logger._queue_high_watermark == 5

    def test_protected_level_eviction_counted_as_success(self) -> None:
        """Protected-level events that evict unprotected ones count as success."""
        logger = _make_logger(queue_capacity=2)

        # Fill with unprotected events
        logger._try_enqueue_with_metrics({"level": "INFO", "message": "info1"})
        logger._try_enqueue_with_metrics({"level": "INFO", "message": "info2"})
        assert logger._queue.qsize() == 2

        # Protected event should evict and succeed
        ok = logger._try_enqueue_with_metrics({"level": "ERROR", "message": "error1"})
        assert ok is True
