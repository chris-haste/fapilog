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
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            logger = get_logger(preset="production")
            logger.info("test message")
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
            await logger.drain()
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "async message from fastapi preset" in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_fastapi_preset_sync_logger_works(self):
        """FastAPI preset also works with sync logger."""
        buf, orig = _swap_stdout_bytesio()
        try:
            logger = get_logger(preset="fastapi")
            logger.info("sync message from fastapi preset")
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
