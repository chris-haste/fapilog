from __future__ import annotations

import asyncio
import io
import sys
from typing import Any
from unittest.mock import patch

import pytest

from fapilog import get_async_logger, get_logger


def _swap_stdout_bytesio() -> tuple[io.BytesIO, Any]:
    """Swap stdout with a BytesIO buffer for capturing output."""
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
    return buf, orig


class TestFormatParameterIntegration:
    def test_format_pretty_uses_pretty_output(self) -> None:
        buf, orig = _swap_stdout_bytesio()
        try:
            with patch.object(sys.stdout, "isatty", return_value=False):
                logger = get_logger(format="pretty")
                logger.info("Test message", key="value")
                asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "Test message" in output
            assert "key=value" in output
            assert " | " in output
            assert "{" not in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_format_json_uses_json_output(self) -> None:
        buf, orig = _swap_stdout_bytesio()
        try:
            logger = get_logger(format="json")
            logger.info("Test message", key="value")
            asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "{" in output
            assert "Test message" in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_format_auto_uses_pretty_in_tty(self) -> None:
        buf, orig = _swap_stdout_bytesio()
        try:
            with patch.object(sys.stdout, "isatty", return_value=True):
                logger = get_logger(format="auto")
                logger.info("Auto pretty")
                asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "Auto pretty" in output
            assert " | " in output
            assert "{" not in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_format_auto_uses_json_when_piped(self) -> None:
        buf, orig = _swap_stdout_bytesio()
        try:
            with patch.object(sys.stdout, "isatty", return_value=False):
                logger = get_logger(format="auto")
                logger.info("Auto json")
                asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "{" in output
            assert "Auto json" in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]

    def test_format_overrides_preset(self) -> None:
        import time

        buf, orig = _swap_stdout_bytesio()
        try:
            with patch.object(sys.stdout, "isatty", return_value=False):
                logger = get_logger(preset="production", format="pretty")
                logger.info("Preset override")
                # Allow workers to process (production preset has worker_count=2)
                time.sleep(0.3)
                asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "Preset override" in output
            assert " | " in output
            assert "{" not in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]


class TestDevPresetPrettyOutput:
    def test_dev_preset_outputs_pretty(self) -> None:
        buf, orig = _swap_stdout_bytesio()
        try:
            with patch.object(sys.stdout, "isatty", return_value=True):
                logger = get_logger(preset="dev")
                logger.debug("Dev preset pretty")
                asyncio.run(logger.stop_and_drain())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "Dev preset pretty" in output
            assert " | " in output
            assert "{" not in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]


class TestAsyncPrettyOutput:
    @pytest.mark.asyncio
    async def test_async_logger_format_pretty(self) -> None:
        buf, orig = _swap_stdout_bytesio()
        try:
            with patch.object(sys.stdout, "isatty", return_value=False):
                logger = await get_async_logger(format="pretty")
                await logger.info("Async pretty")
                await logger.drain()
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "Async pretty" in output
            assert " | " in output
            assert "{" not in output
        finally:
            sys.stdout = orig  # type: ignore[assignment]
