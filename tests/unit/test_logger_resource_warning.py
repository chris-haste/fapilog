"""Tests for ResourceWarning on undrained loggers (Story 10.29 AC3).

Verifies that:
- Undrained loggers emit ResourceWarning on garbage collection
- Properly drained loggers do not emit warnings
- Cached loggers do not emit warnings (they persist)
"""

from __future__ import annotations

import asyncio
import gc
import warnings


class TestAsyncLoggerResourceWarning:
    """Tests for AsyncLoggerFacade ResourceWarning behavior."""

    async def test_undrained_async_logger_warns(self) -> None:
        """Undrained async logger emits ResourceWarning on GC."""
        from fapilog import get_async_logger

        async def create_and_abandon_logger() -> None:
            """Create a logger and abandon it without draining."""
            logger = await get_async_logger("ephemeral", reuse=False)

            # Break the reference cycle: cancel tasks so GC can collect
            logger._stop_flag = True
            if logger._worker_loop is not None:
                for task in logger._worker_tasks:
                    task.cancel()
                await asyncio.sleep(0.05)
            logger._worker_tasks.clear()
            logger._worker_loop = None
            # Logger goes out of scope here without drain()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", ResourceWarning)

            await create_and_abandon_logger()

            # Force GC (multiple passes for cycle collection)
            gc.collect()
            gc.collect()
            gc.collect()

            # Should have emitted ResourceWarning
            resource_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, ResourceWarning)
            ]
            # >= 1 since exact count depends on GC behavior
            assert len(resource_warnings) >= 1  # noqa: WA002
            assert any(
                "drain()" in str(warning.message) for warning in resource_warnings
            )

    async def test_drained_async_logger_no_warning(self) -> None:
        """Properly drained async logger does not emit warning."""
        from fapilog import get_async_logger

        async def create_and_drain_logger() -> None:
            """Create a logger and properly drain it."""
            logger = await get_async_logger("ephemeral", reuse=False)
            await logger.drain()
            # Logger goes out of scope properly drained

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", ResourceWarning)

            await create_and_drain_logger()

            gc.collect()
            gc.collect()
            gc.collect()

            # Should NOT have fapilog-related ResourceWarnings
            fapilog_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, ResourceWarning)
                and "drain()" in str(warning.message)
            ]
            assert len(fapilog_warnings) == 0

    async def test_cached_logger_no_warning_on_scope_exit(self) -> None:
        """Cached loggers don't warn when reference goes out of scope."""
        from fapilog import get_async_logger

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", ResourceWarning)

            # Create cached logger
            logger = await get_async_logger("cached-service")
            # Let reference go out of scope but don't clear cache
            del logger

            gc.collect()

            # Cached loggers persist, so no warning
            fapilog_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, ResourceWarning)
                and "drain()" in str(warning.message)
            ]
            assert len(fapilog_warnings) == 0


class TestSyncLoggerResourceWarning:
    """Tests for SyncLoggerFacade ResourceWarning behavior."""

    def test_undrained_sync_logger_warns(self) -> None:
        """Undrained sync logger emits ResourceWarning on GC."""
        from fapilog import get_logger

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", ResourceWarning)

            # Create logger without caching and don't drain
            logger = get_logger("ephemeral", reuse=False)

            # Break reference cycle: stop workers without draining
            logger._stop_flag = True
            if logger._worker_thread is not None:
                logger._worker_thread.join(timeout=0.1)
            logger._worker_tasks.clear()
            logger._worker_loop = None
            logger._worker_thread = None

            del logger

            gc.collect()
            gc.collect()
            gc.collect()

            # Should have emitted ResourceWarning
            resource_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, ResourceWarning)
            ]
            # >= 1 since exact count depends on GC behavior
            assert len(resource_warnings) >= 1  # noqa: WA002
            assert any(
                "drain()" in str(warning.message) for warning in resource_warnings
            )
