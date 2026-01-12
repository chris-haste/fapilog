from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from fapilog import Settings, get_logger
from fapilog.plugins.sinks.fallback import FallbackSink


class TestFallbackSink:
    @pytest.mark.asyncio
    async def test_primary_sink_success(self) -> None:
        primary = AsyncMock()
        fallback = FallbackSink(primary)
        entry = {"message": "test"}

        with patch("sys.stderr.write") as stderr_write:
            await fallback.write(entry)

        primary.write.assert_awaited_once_with(entry)
        stderr_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_primary_failure_falls_back_to_stderr(self) -> None:
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)
        entry = {"message": "test"}

        with patch("sys.stderr.write") as stderr_write:
            await fallback.write(entry)

        stderr_write.assert_called_once()
        written = stderr_write.call_args[0][0]
        assert json.loads(written.strip()) == entry

    @pytest.mark.asyncio
    async def test_fallback_emits_warning(self) -> None:
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        primary.name = "primary"
        fallback = FallbackSink(primary)

        with patch("fapilog.plugins.sinks.fallback.diagnostics.warn") as warn_mock:
            with patch("sys.stderr.write"):
                await fallback.write({"message": "test"})

        warn_mock.assert_called_once()
        args, kwargs = warn_mock.call_args
        assert args[0] == "sink"
        assert "fallback" in args[1].lower()
        assert kwargs["sink"] == "primary"
        assert kwargs["error"] == "Exception"
        assert kwargs["fallback"] == "stderr"

    @pytest.mark.asyncio
    async def test_stderr_failure_emits_warning_only(self) -> None:
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)

        with patch("sys.stderr.write", side_effect=Exception("stderr failed")):
            with patch("fapilog.plugins.sinks.fallback.diagnostics.warn") as warn_mock:
                await fallback.write({"message": "test"})

        assert warn_mock.called


class TestSinkFallbackIntegration:
    def test_fanout_path_falls_back(self) -> None:
        class FailingSink:
            name = "failing"

            async def write(self, entry: dict) -> None:
                raise RuntimeError("boom")

        warn_calls = []
        writes = []

        def _capture_warn(*_args, **kwargs):
            warn_calls.append(kwargs)

        def _capture_write(value: str) -> int:
            writes.append(value)
            return len(value)

        with patch("fapilog.plugins.sinks.fallback.diagnostics.warn", _capture_warn):
            with patch("sys.stderr.write", _capture_write):
                logger = get_logger(sinks=[FailingSink()])
                try:
                    logger.info("fanout failure")
                finally:
                    asyncio.run(logger.stop_and_drain())

        assert writes
        assert warn_calls
        assert warn_calls[0]["sink"] == "failing"

    def test_routing_path_falls_back(self) -> None:
        class FailingSink:
            name = "failing"

            async def write(self, entry: dict) -> None:
                raise RuntimeError("boom")

        warn_calls = []
        writes = []

        def _capture_warn(*_args, **kwargs):
            warn_calls.append(kwargs)

        def _capture_write(value: str) -> int:
            writes.append(value)
            return len(value)

        settings = Settings(
            sink_routing={
                "enabled": True,
                "rules": [{"levels": ["INFO"], "sinks": ["failing"]}],
            },
        )

        with patch("fapilog.plugins.sinks.fallback.diagnostics.warn", _capture_warn):
            with patch("sys.stderr.write", _capture_write):
                logger = get_logger(settings=settings, sinks=[FailingSink()])
                try:
                    logger.info("routing failure")
                finally:
                    asyncio.run(logger.stop_and_drain())

        assert writes
        assert warn_calls
        assert warn_calls[0]["sink"] == "failing"
