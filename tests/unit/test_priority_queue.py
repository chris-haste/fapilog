"""Unit tests for priority-aware queue dropping (Story 1.37)."""

from __future__ import annotations

import time

import pytest

from fapilog.core.concurrency import PriorityAwareQueue
from fapilog.core.settings import Settings
from fapilog.metrics.metrics import MetricsCollector


class TestProtectedLevelsSetting:
    """Test protected_levels configuration in CoreSettings."""

    def test_default_protected_levels(self) -> None:
        """Default protects ERROR, CRITICAL, FATAL."""
        settings = Settings()
        assert "ERROR" in settings.core.protected_levels
        assert "CRITICAL" in settings.core.protected_levels
        assert "FATAL" in settings.core.protected_levels

    def test_custom_protected_levels(self) -> None:
        """Users can configure custom protected levels."""
        settings = Settings(core={"protected_levels": ["ERROR", "CRITICAL", "AUDIT"]})
        assert settings.core.protected_levels == ["ERROR", "CRITICAL", "AUDIT"]

    def test_empty_protected_levels_disables_priority(self) -> None:
        """Empty list disables priority dropping (rollback behavior)."""
        settings = Settings(core={"protected_levels": []})
        assert settings.core.protected_levels == []

    def test_protected_levels_normalized_to_uppercase(self) -> None:
        """Level names are normalized to uppercase."""
        settings = Settings(core={"protected_levels": ["error", "Critical"]})
        assert "ERROR" in settings.core.protected_levels
        assert "CRITICAL" in settings.core.protected_levels


class TestPriorityAwareQueue:
    """Test PriorityAwareQueue with tombstone-based eviction."""

    def test_basic_enqueue_dequeue(self) -> None:
        """Basic operations work like NonBlockingRingQueue."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=10, protected_levels={"ERROR"}
        )
        payload = {"level": "INFO", "msg": "test"}
        assert queue.try_enqueue(payload) is True
        ok, item = queue.try_dequeue()
        assert ok is True
        assert item == payload

    def test_protected_event_evicts_unprotected_on_full(self) -> None:
        """When queue is full and protected event arrives, unprotected event is evicted."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )
        # Fill with DEBUG events
        queue.try_enqueue({"level": "DEBUG", "msg": "1"})
        queue.try_enqueue({"level": "DEBUG", "msg": "2"})
        queue.try_enqueue({"level": "DEBUG", "msg": "3"})
        assert queue.is_full()

        # Protected ERROR event should evict one DEBUG
        result = queue.try_enqueue({"level": "ERROR", "msg": "important"})
        assert result is True

        # Dequeue should skip evicted tombstone and return remaining items
        dequeued: list[dict[str, str]] = []
        while True:
            ok, item = queue.try_dequeue()
            if not ok:
                break
            assert item is not None  # noqa: WA003 - type guard for mypy
            dequeued.append(item)

        # Should have 3 items: 2 DEBUG (one evicted) + 1 ERROR
        assert len(dequeued) == 3
        levels = [d["level"] for d in dequeued]
        assert levels.count("ERROR") == 1
        assert levels.count("DEBUG") == 2

    def test_unprotected_event_drops_when_queue_full(self) -> None:
        """Non-protected events follow existing drop behavior when queue is full."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )
        # Fill with ERROR events
        queue.try_enqueue({"level": "ERROR", "msg": "1"})
        queue.try_enqueue({"level": "ERROR", "msg": "2"})
        queue.try_enqueue({"level": "ERROR", "msg": "3"})

        # DEBUG cannot evict protected events, should be dropped
        result = queue.try_enqueue({"level": "DEBUG", "msg": "low priority"})
        assert result is False

    def test_protected_event_drops_when_no_eviction_candidates(self) -> None:
        """Protected events drop when queue is full with only protected events."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR", "CRITICAL"}
        )
        # Fill with protected events
        queue.try_enqueue({"level": "ERROR", "msg": "1"})
        queue.try_enqueue({"level": "ERROR", "msg": "2"})
        queue.try_enqueue({"level": "CRITICAL", "msg": "3"})

        # No unprotected events to evict
        result = queue.try_enqueue({"level": "ERROR", "msg": "4"})
        assert result is False

    def test_custom_protected_levels(self) -> None:
        """Custom protected levels (like AUDIT) are respected."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=2, protected_levels={"AUDIT", "SECURITY"}
        )
        queue.try_enqueue({"level": "INFO", "msg": "1"})
        queue.try_enqueue({"level": "INFO", "msg": "2"})

        # AUDIT should evict INFO
        result = queue.try_enqueue({"level": "AUDIT", "msg": "audit event"})
        assert result is True

    def test_tombstoned_events_skipped_on_dequeue(self) -> None:
        """Dequeue skips tombstoned (evicted) entries."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )
        queue.try_enqueue({"level": "DEBUG", "msg": "1"})
        queue.try_enqueue({"level": "DEBUG", "msg": "2"})
        queue.try_enqueue({"level": "DEBUG", "msg": "3"})

        # Evict first DEBUG
        queue.try_enqueue({"level": "ERROR", "msg": "err1"})
        # Evict second DEBUG
        queue.try_enqueue({"level": "ERROR", "msg": "err2"})

        # Dequeue all - should get 1 DEBUG and 2 ERRORs (2 evicted)
        items: list[dict[str, str]] = []
        while True:
            ok, item = queue.try_dequeue()
            if not ok:
                break
            assert item is not None  # noqa: WA003 - type guard for mypy
            items.append(item)

        assert len(items) == 3
        assert sum(1 for i in items if i["level"] == "ERROR") == 2
        assert sum(1 for i in items if i["level"] == "DEBUG") == 1

    def test_eviction_latency_constant_across_queue_sizes(self) -> None:
        """Eviction is O(1) - latency doesn't scale with queue size."""
        # This test verifies AC5: O(1) performance
        timings = []

        for queue_size in [100, 1000, 5000]:
            queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
                capacity=queue_size, protected_levels={"ERROR"}
            )
            # Fill with DEBUG events
            for i in range(queue_size):
                queue.try_enqueue({"level": "DEBUG", "msg": str(i)})

            # Measure eviction latency
            start = time.perf_counter_ns()
            queue.try_enqueue({"level": "ERROR", "msg": "important"})
            elapsed = time.perf_counter_ns() - start
            timings.append(elapsed)

        # Latency should be roughly constant (within 10x of smallest)
        # Allow generous margin for test stability
        assert timings[-1] < timings[0] * 20, (
            f"Eviction latency scaled with queue size: {timings}"
        )

    def test_empty_protected_levels_disables_eviction(self) -> None:
        """With empty protected_levels, no eviction occurs (rollback behavior)."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=2, protected_levels=set()
        )
        queue.try_enqueue({"level": "DEBUG", "msg": "1"})
        queue.try_enqueue({"level": "DEBUG", "msg": "2"})

        # ERROR should be dropped since nothing is protected
        result = queue.try_enqueue({"level": "ERROR", "msg": "err"})
        assert result is False

    def test_qsize_reflects_live_items_only(self) -> None:
        """qsize() returns count of live (non-tombstoned) items."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )
        queue.try_enqueue({"level": "DEBUG", "msg": "1"})
        queue.try_enqueue({"level": "DEBUG", "msg": "2"})
        queue.try_enqueue({"level": "DEBUG", "msg": "3"})
        assert queue.qsize() == 3

        # Evict one
        queue.try_enqueue({"level": "ERROR", "msg": "err"})
        # Live count should still be 3 (1 evicted + 1 added)
        assert queue.qsize() == 3

    def test_evicted_marker_stripped_on_dequeue(self) -> None:
        """Events dequeued don't have internal _evicted marker."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=2, protected_levels={"ERROR"}
        )
        queue.try_enqueue({"level": "DEBUG", "msg": "1"})
        queue.try_enqueue({"level": "DEBUG", "msg": "2"})
        queue.try_enqueue({"level": "ERROR", "msg": "err"})

        # Dequeue all items
        while True:
            ok, item = queue.try_dequeue()
            if not ok:
                break
            assert item is not None  # noqa: WA003 - type guard for mypy
            # No _evicted marker should be visible
            assert "_evicted" not in item


class TestPriorityIntegration:
    """Integration tests for priority queue with full logger pipeline."""

    @pytest.mark.asyncio
    async def test_logger_uses_protected_levels_from_settings(self) -> None:
        """Logger creates PriorityAwareQueue with configured protected_levels."""
        from fapilog import get_async_logger

        # Create logger with custom protected levels
        settings = Settings(core={"protected_levels": ["ERROR", "AUDIT"]})
        logger = await get_async_logger(
            name="test_priority", settings=settings, reuse=False
        )

        try:
            # Verify the queue has the protected levels
            assert hasattr(logger, "_protected_levels")
            assert "ERROR" in logger._protected_levels
            assert "AUDIT" in logger._protected_levels
            assert "DEBUG" not in logger._protected_levels
        finally:
            await logger.stop_and_drain()


class TestProtectedLevelsBuilder:
    """Test builder method for protected_levels (AC1, AC6)."""

    def test_with_protected_levels_sets_custom_levels(self) -> None:
        """Builder can configure custom protected levels."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_protected_levels(["ERROR", "CRITICAL", "AUDIT"])

        # Verify config is set correctly
        assert builder._config["core"]["protected_levels"] == [
            "ERROR",
            "CRITICAL",
            "AUDIT",
        ]

    def test_with_protected_levels_empty_disables(self) -> None:
        """Empty list disables priority dropping."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_protected_levels([])

        assert builder._config["core"]["protected_levels"] == []

    def test_with_protected_levels_returns_self(self) -> None:
        """Method returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_protected_levels(["ERROR"])

        assert result is builder


class TestPriorityMetrics:
    """Test metrics for priority-aware queue behavior (AC7)."""

    @pytest.mark.asyncio
    async def test_record_priority_eviction(self) -> None:
        """Priority evictions are tracked by counter."""
        metrics = MetricsCollector(enabled=True)
        await metrics.record_priority_eviction()
        # Verify counter exists and was incremented
        snapshot = await metrics.snapshot()
        assert snapshot.priority_evictions == 1

    @pytest.mark.asyncio
    async def test_record_events_dropped_with_protected_label(self) -> None:
        """Events dropped are labeled by protection status."""
        metrics = MetricsCollector(enabled=True)
        await metrics.record_events_dropped_protected(count=1)
        await metrics.record_events_dropped_unprotected(count=2)
        snapshot = await metrics.snapshot()
        assert snapshot.drops_protected == 1
        assert snapshot.drops_unprotected == 2

    @pytest.mark.asyncio
    async def test_record_events_evicted_by_level(self) -> None:
        """Evicted events are tracked by level."""
        metrics = MetricsCollector(enabled=True)
        await metrics.record_events_evicted(level="DEBUG", count=3)
        await metrics.record_events_evicted(level="INFO", count=2)
        snapshot = await metrics.snapshot()
        assert snapshot.evicted_by_level is not None  # noqa: WA003 - type guard
        assert snapshot.evicted_by_level["DEBUG"] == 3
        assert snapshot.evicted_by_level["INFO"] == 2

    @pytest.mark.asyncio
    async def test_metrics_disabled_no_error(self) -> None:
        """Methods are safe no-ops when metrics disabled."""
        metrics = MetricsCollector(enabled=False)
        # Should not raise
        await metrics.record_priority_eviction()
        await metrics.record_events_dropped_protected(count=1)
        await metrics.record_events_dropped_unprotected(count=1)
        await metrics.record_events_evicted(level="DEBUG", count=1)


class TestPriorityAwareQueueEdgeCases:
    """Tests for edge cases and error handling in PriorityAwareQueue."""

    def test_capacity_must_be_positive(self) -> None:
        """Queue raises ValueError for capacity <= 0."""
        with pytest.raises(ValueError, match="capacity must be > 0"):
            PriorityAwareQueue(capacity=0, protected_levels={"ERROR"})

        with pytest.raises(ValueError, match="capacity must be > 0"):
            PriorityAwareQueue(capacity=-1, protected_levels={"ERROR"})

    def test_non_dict_items_not_protected(self) -> None:
        """Non-dict items are never considered protected."""
        queue: PriorityAwareQueue[str] = PriorityAwareQueue(
            capacity=2, protected_levels={"ERROR"}
        )
        # Fill with strings (not dicts)
        queue.try_enqueue("item1")
        queue.try_enqueue("item2")
        assert queue.is_full()

        # Another string cannot evict (strings are unprotected, but can't evict)
        result = queue.try_enqueue("item3")
        assert result is False

    def test_compact_when_queue_empty(self) -> None:
        """Compaction is a no-op on empty queue."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )
        # Manually trigger compact on empty queue - should not raise
        queue._compact_if_needed()
        assert queue.is_empty()

    def test_dequeue_skips_none_slots(self) -> None:
        """Dequeue skips None slots from manual compaction or corruption."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=5, protected_levels={"ERROR"}
        )
        # Add some items
        queue.try_enqueue({"level": "INFO", "msg": "1"})
        queue.try_enqueue({"level": "INFO", "msg": "2"})

        # Manually insert None to simulate a compacted slot
        queue._dq.appendleft(None)

        # Dequeue should skip the None
        ok, item = queue.try_dequeue()
        assert ok is True
        assert item == {"level": "INFO", "msg": "1"}

    def test_compaction_skips_none_slots(self) -> None:
        """Compaction loop skips None entries in the deque."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=10, protected_levels={"ERROR"}
        )
        # Fill partially
        for i in range(5):
            queue.try_enqueue({"level": "DEBUG", "msg": str(i)})

        # Manually insert None to simulate edge case
        queue._dq.append(None)

        # Force high tombstone ratio to trigger compaction
        queue._tombstone_count = 4  # >25% of 6 items

        queue._compact_if_needed()
        # None should be removed, only live items remain
        assert None not in queue._dq


class TestPriorityAwareQueueAsync:
    """Tests for async await_enqueue and await_dequeue methods."""

    @pytest.mark.asyncio
    async def test_await_enqueue_immediate_success(self) -> None:
        """await_enqueue returns immediately when space available."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )
        await queue.await_enqueue({"level": "INFO", "msg": "test"})
        assert queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_await_dequeue_immediate_success(self) -> None:
        """await_dequeue returns immediately when data available."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )
        queue.try_enqueue({"level": "INFO", "msg": "test"})

        item = await queue.await_dequeue()
        assert item == {"level": "INFO", "msg": "test"}

    @pytest.mark.asyncio
    async def test_await_enqueue_timeout_expired(self) -> None:
        """await_enqueue raises TimeoutError when timeout expires."""
        from fapilog.core.errors import TimeoutError

        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=1,
            protected_levels=set(),  # No eviction possible
        )
        queue.try_enqueue({"level": "INFO", "msg": "fill"})
        assert queue.is_full()

        with pytest.raises(TimeoutError, match="Timed out waiting to enqueue"):
            await queue.await_enqueue({"level": "INFO", "msg": "blocked"}, timeout=0.01)

    @pytest.mark.asyncio
    async def test_await_dequeue_timeout_expired(self) -> None:
        """await_dequeue raises TimeoutError when timeout expires."""
        from fapilog.core.errors import TimeoutError

        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )
        assert queue.is_empty()

        with pytest.raises(TimeoutError, match="Timed out waiting to dequeue"):
            await queue.await_dequeue(timeout=0.01)

    @pytest.mark.asyncio
    async def test_await_enqueue_waits_for_space(self) -> None:
        """await_enqueue waits until space becomes available."""
        import asyncio

        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=1, protected_levels=set()
        )
        queue.try_enqueue({"level": "INFO", "msg": "fill"})

        async def consumer() -> None:
            await asyncio.sleep(0.01)
            queue.try_dequeue()

        async def producer() -> None:
            await queue.await_enqueue({"level": "INFO", "msg": "new"}, timeout=1.0)

        # Run both concurrently - consumer frees space, producer enqueues
        await asyncio.gather(consumer(), producer())
        assert queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_await_dequeue_waits_for_data(self) -> None:
        """await_dequeue waits until data becomes available."""
        import asyncio

        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )

        async def producer() -> None:
            await asyncio.sleep(0.01)
            queue.try_enqueue({"level": "INFO", "msg": "data"})

        async def consumer() -> dict[str, str]:
            return await queue.await_dequeue(timeout=1.0)

        # Run both concurrently
        _, item = await asyncio.gather(producer(), consumer())
        assert item == {"level": "INFO", "msg": "data"}

    @pytest.mark.asyncio
    async def test_await_enqueue_timeout_zero_remaining(self) -> None:
        """await_enqueue raises when remaining time is zero or negative."""
        from fapilog.core.errors import TimeoutError

        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=1, protected_levels=set()
        )
        queue.try_enqueue({"level": "INFO", "msg": "fill"})

        # Very short timeout to trigger the remaining <= 0 check
        with pytest.raises(TimeoutError, match="Timed out waiting to enqueue"):
            await queue.await_enqueue(
                {"level": "INFO", "msg": "blocked"}, timeout=0.0001
            )

    @pytest.mark.asyncio
    async def test_await_dequeue_timeout_zero_remaining(self) -> None:
        """await_dequeue raises when remaining time is zero or negative."""
        from fapilog.core.errors import TimeoutError

        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )

        # Very short timeout to trigger the remaining <= 0 check
        with pytest.raises(TimeoutError, match="Timed out waiting to dequeue"):
            await queue.await_dequeue(timeout=0.0001)

    @pytest.mark.asyncio
    async def test_await_enqueue_retry_loop(self) -> None:
        """await_enqueue retries when try_enqueue fails after wait."""
        import asyncio

        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=1, protected_levels=set()
        )
        queue.try_enqueue({"level": "INFO", "msg": "fill"})

        async def delayed_free() -> None:
            # First wake-up won't free space, second will
            await asyncio.sleep(0.01)
            queue._space_available.set()  # Wake up waiter but don't dequeue
            await asyncio.sleep(0.01)
            queue.try_dequeue()  # Now actually free space

        async def producer() -> None:
            await queue.await_enqueue({"level": "INFO", "msg": "new"}, timeout=1.0)

        await asyncio.gather(delayed_free(), producer())
        assert queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_await_dequeue_retry_loop(self) -> None:
        """await_dequeue retries when try_dequeue fails after wait."""
        import asyncio

        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=3, protected_levels={"ERROR"}
        )

        async def delayed_enqueue() -> None:
            # First wake-up won't have data, second will
            await asyncio.sleep(0.01)
            queue._data_available.set()  # Wake up waiter but don't enqueue
            await asyncio.sleep(0.01)
            queue.try_enqueue({"level": "INFO", "msg": "data"})

        async def consumer() -> dict[str, str]:
            return await queue.await_dequeue(timeout=1.0)

        _, item = await asyncio.gather(delayed_enqueue(), consumer())
        assert item == {"level": "INFO", "msg": "data"}
