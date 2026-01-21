"""Tests for logger instance caching (Story 10.29).

Verifies that:
- Same name returns same instance (AC1)
- reuse=False creates new instances (AC2)
- Cache management functions work (AC4)
- Concurrent access returns same instance (AC5)
"""

from __future__ import annotations

import asyncio


class TestAsyncLoggerCaching:
    """Tests for get_async_logger() caching behavior."""

    async def test_same_name_returns_same_instance(self) -> None:
        """Calling get_async_logger() with same name returns cached instance."""
        from fapilog import get_async_logger

        logger1 = await get_async_logger("my-service")
        logger2 = await get_async_logger("my-service")

        assert logger1 is logger2

    async def test_default_logger_is_cached(self) -> None:
        """Default logger (no name) is also cached."""
        from fapilog import get_async_logger

        logger1 = await get_async_logger()
        logger2 = await get_async_logger()

        assert logger1 is logger2

    async def test_different_names_different_instances(self) -> None:
        """Different names create different logger instances."""
        from fapilog import get_async_logger

        logger1 = await get_async_logger("service-a")
        logger2 = await get_async_logger("service-b")

        assert logger1 is not logger2

    async def test_reuse_false_creates_new_instance(self) -> None:
        """Setting reuse=False creates a new independent instance."""
        from fapilog import get_async_logger

        logger1 = await get_async_logger("test-logger")
        logger2 = await get_async_logger("test-logger", reuse=False)

        assert logger1 is not logger2

        # Cleanup the non-cached instance
        await logger2.drain()

    async def test_reuse_false_instance_not_cached(self) -> None:
        """Instance created with reuse=False is not added to cache."""
        from fapilog import get_async_logger, get_cached_loggers

        # Create a cached logger first
        await get_async_logger("cached-one")

        # Create a non-cached logger
        logger2 = await get_async_logger("ephemeral", reuse=False)

        cached = get_cached_loggers()
        assert "cached-one" in cached
        assert "ephemeral" not in cached

        await logger2.drain()


class TestSyncLoggerCaching:
    """Tests for get_logger() caching behavior."""

    def test_same_name_returns_same_instance(self) -> None:
        """Calling get_logger() with same name returns cached instance."""
        from fapilog import get_logger

        logger1 = get_logger("my-service")
        logger2 = get_logger("my-service")

        assert logger1 is logger2

    def test_default_logger_is_cached(self) -> None:
        """Default logger (no name) is also cached."""
        from fapilog import get_logger

        logger1 = get_logger()
        logger2 = get_logger()

        assert logger1 is logger2

    def test_reuse_false_creates_new_instance(self) -> None:
        """Setting reuse=False creates a new independent instance."""
        from fapilog import get_logger

        logger1 = get_logger("test-logger")
        logger2 = get_logger("test-logger", reuse=False)

        assert logger1 is not logger2


class TestCacheManagement:
    """Tests for cache management functions (AC4)."""

    async def test_get_cached_loggers_returns_all(self) -> None:
        """get_cached_loggers() returns all cached logger names."""
        from fapilog import get_async_logger, get_cached_loggers, get_logger

        await get_async_logger("service-a")
        await get_async_logger("service-b")
        get_logger("service-c")

        cached = get_cached_loggers()

        assert "service-a" in cached
        assert "service-b" in cached
        assert "service-c" in cached
        assert cached["service-a"] == "async"
        assert cached["service-b"] == "async"
        assert cached["service-c"] == "sync"

    async def test_clear_logger_cache_drains_all(self) -> None:
        """clear_logger_cache() drains and removes all cached loggers."""
        from fapilog import clear_logger_cache, get_async_logger, get_cached_loggers

        logger1 = await get_async_logger("service-a")
        logger2 = await get_async_logger("service-b")

        # Verify they're cached
        cached_before = get_cached_loggers()
        assert len(cached_before) == 2

        # Clear cache
        await clear_logger_cache()

        # Verify cache is empty
        cached_after = get_cached_loggers()
        assert len(cached_after) == 0

        # Verify loggers were drained (workers stopped)
        assert logger1._worker_loop is None or logger1._stop_flag
        assert logger2._worker_loop is None or logger2._stop_flag


class TestConcurrentAccess:
    """Tests for thread-safe cache access (AC5)."""

    async def test_concurrent_access_returns_same_instance(self) -> None:
        """Concurrent calls to get_async_logger return same instance."""
        from fapilog import get_async_logger

        results: list[int] = []

        async def get_logger_task() -> None:
            logger = await get_async_logger("shared")
            results.append(id(logger))

        # Run 50 concurrent tasks
        await asyncio.gather(*[get_logger_task() for _ in range(50)])

        # All should return the same instance
        assert len(set(results)) == 1


class TestRuntimeAsyncCacheInteraction:
    """Tests for runtime_async() cache interaction (AC7)."""

    async def test_runtime_async_does_not_pollute_cache(self) -> None:
        """runtime_async() should not leave a drained logger in cache."""
        from fapilog import get_cached_loggers, runtime_async

        # Use runtime_async - it drains on exit
        async with runtime_async() as logger1:
            await logger1.info("test")

        # Cache should be empty after context manager exits
        # (runtime_async uses reuse=False)
        cached = get_cached_loggers()
        # The default key should NOT be in cache
        assert "__fapilog_default__" not in cached

    async def test_runtime_async_independent_from_cached(self) -> None:
        """runtime_async logger is independent from get_async_logger."""
        from fapilog import get_async_logger, runtime_async

        # Create a cached default logger first
        cached_logger = await get_async_logger()

        # runtime_async should use a different instance
        async with runtime_async() as context_logger:
            assert context_logger is not cached_logger
            await context_logger.info("test")

        # Cached logger should still be usable
        await cached_logger.info("still works")
        assert cached_logger._worker_tasks  # Has active workers
