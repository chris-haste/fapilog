"""
Test critical() log level method for both SyncLoggerFacade and AsyncLoggerFacade.

Scope:
- critical() method exists on both facades
- critical() logs with level="CRITICAL" in envelope
- Signature matches error() method
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade


async def _collecting_sink(
    collected: list[dict[str, Any]], entry: dict[str, Any]
) -> None:
    collected.append(dict(entry))


class TestSyncLoggerCritical:
    """Tests for SyncLoggerFacade.critical() method."""

    @pytest.mark.asyncio
    async def test_sync_logger_has_critical_method(self) -> None:
        """AC1: SyncLoggerFacade exposes a critical() method."""
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        # Should not raise AttributeError
        logger.critical("System failure imminent")

        await asyncio.sleep(0.1)
        res = await logger.stop_and_drain()
        assert res.submitted == 1
        assert res.processed == 1

    @pytest.mark.asyncio
    async def test_sync_critical_logs_include_correct_level(self) -> None:
        """AC3: CRITICAL logs include level='CRITICAL' in envelope."""
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        logger.critical("Test critical message")

        await asyncio.sleep(0.1)
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["level"] == "CRITICAL"
        assert collected[0]["message"] == "Test critical message"

    @pytest.mark.asyncio
    async def test_sync_critical_accepts_metadata(self) -> None:
        """critical() accepts arbitrary metadata like error()."""
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        logger.critical("System down", service="api", code=500)

        await asyncio.sleep(0.1)
        await logger.stop_and_drain()

        assert len(collected) == 1
        # Metadata goes into data field (v1.1 envelope schema)
        data = collected[0].get("data", {})
        assert data.get("service") == "api"
        assert data.get("code") == 500

    @pytest.mark.asyncio
    async def test_sync_critical_accepts_exc_info(self) -> None:
        """critical() accepts exc_info parameter like error()."""
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        try:
            raise ValueError("boom")
        except ValueError:
            logger.critical("Fatal error", exc_info=True)

        await asyncio.sleep(0.1)
        await logger.stop_and_drain()

        assert len(collected) == 1
        # Exception info goes in diagnostics.exception (v1.1 envelope schema)
        diagnostics = collected[0].get("diagnostics", {})
        exception = diagnostics.get("exception", {})
        assert exception.get("error.type") == "ValueError"
        assert exception.get("error.message") == "boom"


class TestAsyncLoggerCritical:
    """Tests for AsyncLoggerFacade.critical() method."""

    @pytest.mark.asyncio
    async def test_async_logger_has_critical_method(self) -> None:
        """AC2: AsyncLoggerFacade exposes an async critical() method."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        await logger.start_async()

        # Should not raise AttributeError and should be awaitable
        await logger.critical("System failure imminent")

        await asyncio.sleep(0.1)
        res = await logger.drain()
        assert res.submitted == 1
        assert res.processed == 1

    @pytest.mark.asyncio
    async def test_async_critical_logs_include_correct_level(self) -> None:
        """AC3: CRITICAL logs include level='CRITICAL' in envelope."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        await logger.start_async()

        await logger.critical("Test critical message")

        await asyncio.sleep(0.1)
        await logger.drain()

        assert len(collected) == 1
        assert collected[0]["level"] == "CRITICAL"
        assert collected[0]["message"] == "Test critical message"

    @pytest.mark.asyncio
    async def test_async_critical_accepts_metadata(self) -> None:
        """critical() accepts arbitrary metadata like error()."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        await logger.start_async()

        await logger.critical("System down", service="api", code=500)

        await asyncio.sleep(0.1)
        await logger.drain()

        assert len(collected) == 1
        # Metadata goes into data field (v1.1 envelope schema)
        data = collected[0].get("data", {})
        assert data.get("service") == "api"
        assert data.get("code") == 500

    @pytest.mark.asyncio
    async def test_async_critical_accepts_exc_info(self) -> None:
        """critical() accepts exc_info parameter like error()."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        await logger.start_async()

        try:
            raise ValueError("boom")
        except ValueError:
            await logger.critical("Fatal error", exc_info=True)

        await asyncio.sleep(0.1)
        await logger.drain()

        assert len(collected) == 1
        # Exception info goes in diagnostics.exception (v1.1 envelope schema)
        diagnostics = collected[0].get("diagnostics", {})
        exception = diagnostics.get("exception", {})
        assert exception.get("error.type") == "ValueError"
        assert exception.get("error.message") == "boom"
