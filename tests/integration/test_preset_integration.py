"""Integration tests for configuration presets."""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from fapilog import get_async_logger, get_logger


def _swap_stdout_bytesio() -> tuple[io.BytesIO, Any]:
    """Swap stdout with a BytesIO buffer for capturing output."""
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
    return buf, orig


class TestProductionPresetIntegration:
    """Test production preset end-to-end behavior."""

    def test_production_preset_creates_log_directory(self, tmp_path: Path):
        """Production preset creates ./logs directory when writing."""
        import time

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            logger = get_logger(preset="production")
            logger.info("test message")
            # Allow workers to pick up the message before draining
            # (with worker_count=2, work distribution is async)
            time.sleep(0.3)
            # Drain to ensure file sink writes
            asyncio.run(logger.stop_and_drain())
            # The logs directory should exist after draining
            assert (tmp_path / "logs").exists(), "Logs directory should be created"
        finally:
            os.chdir(original_cwd)

    def test_production_preset_redacts_password_field(self, tmp_path: Path):
        """Production preset redacts password fields."""
        original_cwd = os.getcwd()
        buf, orig = _swap_stdout_bytesio()
        try:
            os.chdir(tmp_path)
            logger = get_logger(preset="production")
            logger.info("user login", password="secret123")
            asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            # The password should be redacted (not appear as-is)
            assert "secret123" not in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]
            os.chdir(original_cwd)

    def test_production_preset_redacts_api_key_field(self, tmp_path: Path):
        """Production preset redacts api_key fields."""
        original_cwd = os.getcwd()
        buf, orig = _swap_stdout_bytesio()
        try:
            os.chdir(tmp_path)
            logger = get_logger(preset="production")
            logger.info("api call", api_key="my-secret-key")
            asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "my-secret-key" not in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]
            os.chdir(original_cwd)


class TestDevPresetIntegration:
    """Test dev preset end-to-end behavior."""

    def test_dev_preset_immediate_flush(self):
        """Dev preset flushes immediately (batch_size=1)."""
        buf, orig = _swap_stdout_bytesio()
        try:
            logger = get_logger(preset="dev")
            logger.debug("immediate message")
            asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "immediate message" in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_dev_preset_logs_at_debug_level(self):
        """Dev preset allows DEBUG level messages."""
        buf, orig = _swap_stdout_bytesio()
        try:
            logger = get_logger(preset="dev")
            logger.debug("debug level message")
            asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            # Should see DEBUG level in output
            assert "DEBUG" in output or "debug level message" in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]


class TestFastAPIPresetIntegration:
    """Test fastapi preset end-to-end behavior."""

    @pytest.mark.asyncio
    async def test_fastapi_preset_async_logger_works(self):
        """FastAPI preset works with async logger."""
        buf, orig = _swap_stdout_bytesio()
        try:
            logger = await get_async_logger(preset="fastapi")
            await logger.info("async message from fastapi preset")
            # Allow workers to pick up the message (worker_count=2)
            await asyncio.sleep(0.3)
            await logger.drain()
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "async message from fastapi preset" in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_fastapi_preset_sync_logger_works(self):
        """FastAPI preset also works with sync logger."""
        import time

        buf, orig = _swap_stdout_bytesio()
        try:
            logger = get_logger(preset="fastapi")
            logger.info("sync message from fastapi preset")
            # Allow workers to pick up the message (worker_count=2)
            time.sleep(0.3)
            asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "sync message from fastapi preset" in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]


class TestMinimalPresetIntegration:
    """Test minimal preset matches default behavior."""

    def test_minimal_preset_matches_no_preset(self):
        """Minimal preset behaves same as no preset."""
        buf, orig = _swap_stdout_bytesio()
        try:
            # Log with minimal preset (use unique name to avoid cache conflicts)
            logger1 = get_logger(name="minimal-test", preset="minimal")
            logger1.info("minimal preset message")
            asyncio.run(logger1.stop_and_drain())
            sys.stdout.flush()
            output1 = buf.getvalue().decode("utf-8")

            # Reset buffer
            buf.truncate(0)
            buf.seek(0)

            # Log with no preset (use different unique name)
            logger2 = get_logger(name="no-preset-test")
            logger2.info("no preset message")
            asyncio.run(logger2.stop_and_drain())
            sys.stdout.flush()
            output2 = buf.getvalue().decode("utf-8")

            # Both should produce JSON output with INFO level
            assert "minimal preset message" in output1
            assert "no preset message" in output2

            # Both should be valid JSON
            for line in output1.strip().split("\n"):
                if line:
                    json.loads(line)
            for line in output2.strip().split("\n"):
                if line:
                    json.loads(line)
        finally:
            sys.stdout = orig  # type: ignore[assignment]


class TestPresetWorkerCountIntegration:
    """Test worker_count settings propagate to logger.

    Story 10.44: Production presets default to worker_count=2 for 30x
    throughput improvement. These tests verify the configuration flows
    through to the actual logger instance.
    """

    def test_production_preset_spawns_two_workers(self, tmp_path: Path):
        """Logger built with production preset has 2 workers.

        Story 10.44 AC1: Verify logger built with production preset spawns 2 workers.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            logger = get_logger(preset="production")
            assert logger._num_workers == 2  # noqa: SLF001
            asyncio.run(logger.stop_and_drain())
        finally:
            os.chdir(original_cwd)

    def test_fastapi_preset_spawns_two_workers(self):
        """Logger built with fastapi preset has 2 workers."""
        buf, orig = _swap_stdout_bytesio()
        try:
            logger = get_logger(preset="fastapi")
            assert logger._num_workers == 2  # noqa: SLF001
            asyncio.run(logger.stop_and_drain())
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_serverless_preset_spawns_two_workers(self):
        """Logger built with serverless preset has 2 workers."""
        buf, orig = _swap_stdout_bytesio()
        try:
            logger = get_logger(preset="serverless")
            assert logger._num_workers == 2  # noqa: SLF001
            asyncio.run(logger.stop_and_drain())
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_hardened_preset_spawns_two_workers(self, tmp_path: Path):
        """Logger built with hardened preset has 2 workers."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            logger = get_logger(preset="hardened")
            assert logger._num_workers == 2  # noqa: SLF001
            asyncio.run(logger.stop_and_drain())
        finally:
            os.chdir(original_cwd)

    def test_dev_preset_spawns_one_worker(self):
        """Logger built with dev preset has 1 worker for simpler debugging."""
        buf, orig = _swap_stdout_bytesio()
        try:
            logger = get_logger(preset="dev")
            assert logger._num_workers == 1  # noqa: SLF001
            asyncio.run(logger.stop_and_drain())
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_explicit_with_workers_overrides_preset(self, tmp_path: Path):
        """Explicit .with_workers() call overrides preset default.

        Story 10.44 AC3: Users who explicitly set worker_count are unaffected.
        """
        from fapilog import LoggerBuilder

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            logger = (
                LoggerBuilder()
                .with_preset("production")
                .with_workers(4)  # Override the preset's default of 2
                .build()
            )
            assert logger._num_workers == 4  # noqa: SLF001
            asyncio.run(logger.stop_and_drain())
        finally:
            os.chdir(original_cwd)


class TestPresetPerformance:
    """Test preset application performance."""

    def test_preset_application_is_fast(self):
        """Preset application should add minimal overhead."""
        import time

        # Warm up
        _ = get_logger(preset="dev")

        # Measure
        start = time.perf_counter()
        for _ in range(10):
            _ = get_logger(preset="production")
        elapsed = time.perf_counter() - start

        # Average should be < 100ms per logger (generous bound)
        avg_ms = (elapsed / 10) * 1000
        assert avg_ms < 100, f"Preset application too slow: {avg_ms:.1f}ms per logger"


class TestPresetWithBuilderSinkIntegration:
    """Test preset + builder add_file() integration.

    Regression test for bug where with_preset('production') combined
    with add_file() caused messages to be submitted but never processed.
    """

    @pytest.mark.asyncio
    async def test_production_preset_with_add_file_processes_messages(
        self, tmp_path: Path
    ):
        """with_preset('production').add_file() processes messages.

        Bug reproduction: messages were submitted but processed=0.
        Fix: merge sinks instead of replacing them.
        """
        from fapilog import AsyncLoggerBuilder

        logger = await (
            AsyncLoggerBuilder()
            .with_preset("production")
            .add_file(directory=str(tmp_path))
            .reuse(False)
            .build_async()
        )

        await logger.info("Test message", data={"key": "value"})
        # Allow workers to process (production preset has worker_count=2)
        await asyncio.sleep(0.3)
        result = await logger.drain()

        assert result.submitted == 1, "Message should be submitted"
        assert result.processed == 1, "Message should be processed (was 0 before fix)"

        # Verify file was created
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1, "Log file should be created"

    @pytest.mark.asyncio
    async def test_dev_preset_with_add_file_processes_messages(self, tmp_path: Path):
        """with_preset('dev').add_file() processes messages."""
        from fapilog import AsyncLoggerBuilder

        logger = await (
            AsyncLoggerBuilder()
            .with_preset("dev")
            .add_file(directory=str(tmp_path))
            .reuse(False)
            .build_async()
        )

        await logger.debug("Debug test message")
        result = await logger.drain()

        assert result.submitted == 1
        assert result.processed == 1

        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1

    def test_production_preset_with_add_file_sync(self, tmp_path: Path):
        """Sync version: with_preset('production').add_file() works."""
        import time

        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .with_preset("production")
            .add_file(directory=str(tmp_path))
            .reuse(False)
            .build()
        )

        logger.info("Sync test message")
        # Allow workers to process
        time.sleep(0.3)
        result = asyncio.run(logger.stop_and_drain())

        assert result.submitted == 1
        assert result.processed == 1

        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1
