from __future__ import annotations

import datetime as dt
import io
import sys
from datetime import timezone
from unittest.mock import patch

import pytest

from fapilog.plugins.sinks.stdout_pretty import StdoutPrettySink


class TestTimestampFormatting:
    def test_formats_datetime(self) -> None:
        sink = StdoutPrettySink(colors=False)
        stamp = dt.datetime(2025, 1, 11, 14, 30, 22)
        assert sink._format_timestamp(stamp) == "2025-01-11 14:30:22"

    def test_formats_float_timestamp(self) -> None:
        sink = StdoutPrettySink(colors=False)
        value = 1736605822.0
        expected = (
            dt.datetime.fromtimestamp(value).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        )
        assert sink._format_timestamp(value) == expected

    def test_formats_invalid_string_timestamp(self) -> None:
        sink = StdoutPrettySink(colors=False)
        value = "not-a-date"
        assert sink._format_timestamp(value) == value

    def test_formats_timezone_aware_timestamp(self) -> None:
        sink = StdoutPrettySink(colors=False)
        stamp = dt.datetime(2025, 1, 11, 14, 30, 22, tzinfo=timezone.utc)
        expected = stamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        assert sink._format_timestamp(stamp) == expected

    def test_reuses_cached_timestamp(self) -> None:
        sink = StdoutPrettySink(colors=False)
        value = 1736605822.0
        first = sink._format_timestamp(value)
        second = sink._format_timestamp(value)
        assert first == second


class TestLevelFormatting:
    def test_level_padded_without_colors(self) -> None:
        sink = StdoutPrettySink(colors=False)
        result = sink._format_level("INFO")
        assert result == "INFO".ljust(8)

    def test_level_colored_when_tty(self) -> None:
        with patch.object(sys.stdout, "isatty", return_value=True):
            sink = StdoutPrettySink(colors=True)
        result = sink._format_level("ERROR")
        assert "\033[" in result
        assert "ERROR" in result
        assert result.endswith("\033[0m")

    def test_level_cache_short_circuits_formatting(self) -> None:
        sink = StdoutPrettySink(colors=False)
        sink._level_cache["INFO"] = "CACHED"
        assert sink._format_level("INFO") == "CACHED"


class TestContextFormatting:
    def test_context_flattens_metadata_and_top_level(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {
            "level": "INFO",
            "message": "test",
            "metadata": {"user": {"id": 123}, "request_id": "abc-123"},
            "correlation_id": "corr-1",
        }
        result = sink._format_context(entry)
        assert "user.id=123" in result
        assert "request_id=abc-123" in result
        assert "correlation_id=corr-1" in result

    def test_context_quotes_strings_with_spaces(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {"metadata": {"error": "connection timeout"}}
        result = sink._format_context(entry)
        assert "error='connection timeout'" in result

    def test_context_skips_reserved_fields(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {"timestamp": 1, "level": "INFO", "message": "x"}
        result = sink._format_context(entry)
        assert "timestamp=" not in result
        assert "level=" not in result
        assert "message=" not in result

    def test_context_includes_base_context(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {"context": {"region": "us-east-1"}, "metadata": {"key": "value"}}
        result = sink._format_context(entry)
        assert "region=us-east-1" in result
        assert "key=value" in result

    def test_context_skips_error_fields(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {"metadata": {"error.stack": "Traceback", "ok": "yes"}}
        result = sink._format_context(entry)
        assert "error.stack" not in result
        assert "ok=yes" in result


class TestExceptionFormatting:
    def test_exception_uses_error_stack_and_context(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {
            "level": "ERROR",
            "message": "boom",
            "metadata": {
                "error.stack": "Traceback (most recent call last):\nValueError: bad",
                "user_id": 123,
            },
        }
        result = sink._format_exception(entry)
        assert "Traceback (most recent call last)" in result
        assert "ValueError: bad" in result
        assert "Context: user_id=123" in result
        assert "error.stack" not in result

    def test_exception_uses_frames_list(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {
            "level": "ERROR",
            "message": "boom",
            "metadata": {
                "error.type": "ValueError",
                "error.message": "bad",
                "error.frames": [
                    {
                        "file": "app.py",
                        "line": 42,
                        "function": "run",
                        "code": "raise ValueError()",
                    }
                ],
                "user_id": 7,
            },
        }
        result = sink._format_exception(entry)
        assert "Traceback (most recent call last):" in result
        assert 'File "app.py", line 42, in run' in result
        assert "raise ValueError()" in result
        assert "ValueError: bad" in result
        assert "Context: user_id=7" in result

    def test_exception_frames_without_message(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {
            "level": "ERROR",
            "metadata": {
                "error.type": "RuntimeError",
                "error.frames": [{"file": "app.py", "line": 1, "function": "main"}],
            },
        }
        result = sink._format_exception(entry)
        assert "RuntimeError" in result
        assert "Context:" not in result

    def test_exception_frames_skips_non_mapping(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {
            "level": "ERROR",
            "metadata": {
                "error.type": "RuntimeError",
                "error.frames": ["bad-frame", {"file": "app.py", "line": 2}],
            },
        }
        result = sink._format_exception(entry)
        assert "Traceback (most recent call last):" in result

    def test_exception_uses_exception_mapping(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {"exception": {"traceback": "Traceback (most recent call last):\nboom"}}
        result = sink._format_exception(entry)
        assert "Traceback (most recent call last):" in result


class TestPrettyFormatting:
    def test_format_pretty_includes_context(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {
            "timestamp": dt.datetime(2025, 1, 11, 14, 30, 22),
            "level": "INFO",
            "message": "hello",
            "metadata": {"user_id": 123},
        }
        result = sink._format_pretty(entry)
        assert "2025-01-11 14:30:22" in result
        assert "INFO" in result
        assert "hello" in result
        assert "user_id=123" in result

    def test_format_pretty_includes_exception_block(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {
            "timestamp": dt.datetime(2025, 1, 11, 14, 30, 22),
            "level": "ERROR",
            "message": "failed",
            "metadata": {"error.stack": "Traceback (most recent call last):\nboom"},
        }
        result = sink._format_pretty(entry)
        assert "failed" in result
        assert "Traceback (most recent call last)" in result


class TestSinkWrite:
    @pytest.mark.asyncio
    async def test_start_stop_are_noops(self) -> None:
        sink = StdoutPrettySink(colors=False)
        await sink.start()
        await sink.stop()

    @pytest.mark.asyncio
    async def test_write_outputs_newline(self) -> None:
        sink = StdoutPrettySink(colors=False)
        entry = {"level": "INFO", "message": "test"}
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            await sink.write(entry)
        output = buf.getvalue()
        assert "test" in output
        assert output.endswith("\n")

    @pytest.mark.asyncio
    async def test_write_raises_sink_write_error_on_failure(self) -> None:
        from fapilog.core.errors import SinkWriteError

        sink = StdoutPrettySink(colors=False)
        entry = {"level": "INFO", "message": "test"}
        with patch.object(sink, "_format_pretty", side_effect=RuntimeError("boom")):
            with pytest.raises(SinkWriteError) as exc_info:
                await sink.write(entry)
        assert exc_info.value.context.plugin_name == "stdout_pretty"
        assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestTtyDetection:
    def test_is_tty_handles_exception(self) -> None:
        class BrokenStdout:
            def isatty(self) -> bool:
                raise RuntimeError("boom")

        sink = StdoutPrettySink(colors=False)
        with patch("sys.stdout", BrokenStdout()):
            assert sink._is_tty() is False


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_false_on_error(self) -> None:
        class BrokenStdout:
            @property
            def write(self) -> bool:  # pragma: no cover - behavior check
                raise RuntimeError("boom")

        sink = StdoutPrettySink(colors=False)
        with patch("sys.stdout", BrokenStdout()):
            assert await sink.health_check() is False
