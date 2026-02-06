"""Tests for unsafe_debug escape hatch (Story 4.70).

Covers:
- AC1: unsafe_debug emits at DEBUG level
- AC2: Event tagged with _fapilog_unsafe marker
- AC3: Redaction pipeline skipped for unsafe_debug events
- AC4: Regular debug() still redacts
- AC5: Async facade support
- AC6: User-supplied _fapilog_unsafe kwarg does not bypass redaction
- Exception forwarding via exc/exc_info
"""

from __future__ import annotations

from typing import Any

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade


class _FieldRedactor:
    """Test redactor that replaces 'password' values with '***'."""

    name = "field_mask"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
        e = dict(event)
        data = e.get("data")
        if isinstance(data, dict) and "password" in data:
            data = dict(data)
            data["password"] = "***"
            e["data"] = data
        return e


def _make_sync_logger(
    collected: list[dict[str, Any]],
    *,
    with_redactor: bool = False,
) -> SyncLoggerFacade:
    """Create a SyncLoggerFacade that collects events into a list."""

    async def sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    logger = SyncLoggerFacade(
        name="unsafe-debug-test",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=sink,
    )
    if with_redactor:
        logger._redactors = [_FieldRedactor()]  # type: ignore[attr-defined]
        logger._invalidate_redactors_cache()  # type: ignore[attr-defined]
    return logger


def _make_async_logger(
    collected: list[dict[str, Any]],
    *,
    with_redactor: bool = False,
) -> AsyncLoggerFacade:
    """Create an AsyncLoggerFacade that collects events into a list."""

    async def sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    logger = AsyncLoggerFacade(
        name="unsafe-debug-async-test",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=sink,
    )
    if with_redactor:
        logger._redactors = [_FieldRedactor()]  # type: ignore[attr-defined]
        logger._invalidate_redactors_cache()  # type: ignore[attr-defined]
    return logger


class TestUnsafeDebug:
    """Tests for SyncLoggerFacade.unsafe_debug()."""

    @pytest.mark.asyncio
    async def test_unsafe_debug_emits_debug_level(self) -> None:
        """AC1: unsafe_debug() always produces a DEBUG-level event."""
        collected: list[dict[str, Any]] = []
        logger = _make_sync_logger(collected)
        logger.start()

        logger.unsafe_debug("raw data", payload="sensitive")
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["level"] == "DEBUG"

    @pytest.mark.asyncio
    async def test_unsafe_debug_tags_fapilog_unsafe_marker(self) -> None:
        """AC2: Event has data._fapilog_unsafe = True."""
        collected: list[dict[str, Any]] = []
        logger = _make_sync_logger(collected)
        logger.start()

        logger.unsafe_debug("raw data", payload="x")
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["data"]["_fapilog_unsafe"] is True

    @pytest.mark.asyncio
    async def test_unsafe_debug_skips_redaction(self) -> None:
        """AC3: Events from unsafe_debug bypass the redaction pipeline."""
        collected: list[dict[str, Any]] = []
        logger = _make_sync_logger(collected, with_redactor=True)
        logger.start()

        logger.unsafe_debug("debug", password="secret123", api_key="sk-abc")
        await logger.stop_and_drain()

        assert len(collected) == 1
        data = collected[0]["data"]
        assert data["password"] == "secret123"
        assert data["api_key"] == "sk-abc"

    @pytest.mark.asyncio
    async def test_regular_debug_still_redacts(self) -> None:
        """AC4: Regular debug() continues to apply redaction."""
        collected: list[dict[str, Any]] = []
        logger = _make_sync_logger(collected, with_redactor=True)
        logger.start()

        logger.debug("debug", password="secret123")
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["data"]["password"] == "***"

    @pytest.mark.asyncio
    async def test_user_kwarg_fapilog_unsafe_does_not_bypass_redaction(self) -> None:
        """AC6: User-supplied _fapilog_unsafe=True via normal log methods is stripped."""
        collected: list[dict[str, Any]] = []
        logger = _make_sync_logger(collected, with_redactor=True)
        logger.start()

        logger.info("sneaky", password="secret123", _fapilog_unsafe=True)
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["data"]["password"] == "***"

    @pytest.mark.asyncio
    async def test_unsafe_debug_with_exception(self) -> None:
        """unsafe_debug forwards exc/exc_info to the envelope."""
        collected: list[dict[str, Any]] = []
        logger = _make_sync_logger(collected)
        logger.start()

        err = ValueError("test error")
        logger.unsafe_debug("error dump", exc=err, detail="raw")
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["level"] == "DEBUG"
        assert collected[0]["data"]["detail"] == "raw"
        # Exception info should be captured in diagnostics.exception
        exc_info = collected[0].get("diagnostics", {}).get("exception", {})
        assert exc_info.get("error.type") == "ValueError"
        assert exc_info.get("error.message") == "test error"


class TestAsyncUnsafeDebug:
    """Tests for AsyncLoggerFacade.unsafe_debug() (AC5)."""

    @pytest.mark.asyncio
    async def test_async_unsafe_debug_emits_debug_level(self) -> None:
        """AC5: Async facade unsafe_debug produces DEBUG-level event."""
        collected: list[dict[str, Any]] = []
        logger = _make_async_logger(collected)
        logger.start()

        await logger.unsafe_debug("raw data", payload="sensitive")
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["level"] == "DEBUG"

    @pytest.mark.asyncio
    async def test_async_unsafe_debug_skips_redaction(self) -> None:
        """AC5+AC3: Async unsafe_debug also bypasses redaction."""
        collected: list[dict[str, Any]] = []
        logger = _make_async_logger(collected, with_redactor=True)
        logger.start()

        await logger.unsafe_debug("debug", password="secret123")
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["data"]["password"] == "secret123"

    @pytest.mark.asyncio
    async def test_async_user_kwarg_fapilog_unsafe_stripped(self) -> None:
        """AC6: Async facade also strips _fapilog_unsafe from user kwargs."""
        collected: list[dict[str, Any]] = []
        logger = _make_async_logger(collected, with_redactor=True)
        logger.start()

        await logger.info("sneaky", password="secret123", _fapilog_unsafe=True)
        await logger.stop_and_drain()

        assert len(collected) == 1
        assert collected[0]["data"]["password"] == "***"
