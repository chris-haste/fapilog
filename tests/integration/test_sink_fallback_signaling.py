"""
Integration tests for sink failure signaling and fallback (Story 4.41, 4.48).

Tests that:
- Sinks raising SinkWriteError trigger fallback to stderr
- Sinks returning False trigger fallback to stderr
- Fallback works through the full get_logger pipeline
- Fallback redacts sensitive fields in lists (Story 4.48)
"""

import asyncio
import json
from unittest.mock import patch

import pytest

from fapilog import get_logger
from fapilog.core.errors import SinkWriteError


def _drain_logger(logger) -> None:
    """Helper to drain the logger."""
    asyncio.run(logger.stop_and_drain())


class FailingSink:
    """Test sink that raises SinkWriteError on write."""

    name = "failing_sink"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def write(self, entry: dict) -> None:
        raise SinkWriteError(
            f"Failed to write to {self.name}",
            sink_name=self.name,
        )


class FalseReturnSink:
    """Test sink that returns False on write."""

    name = "false_return_sink"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def write(self, entry: dict) -> bool:
        return False


class SuccessfulSink:
    """Test sink that succeeds."""

    name = "successful_sink"
    written: list[dict]

    def __init__(self) -> None:
        self.written = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def write(self, entry: dict) -> None:
        self.written.append(entry)


class TestSinkFallbackIntegration:
    """Integration tests for sink fallback on failure signals."""

    def test_sink_write_error_triggers_fallback_handler(self):
        """When a sink raises SinkWriteError, fallback handler should be called."""
        failing_sink = FailingSink()

        logger = get_logger(
            "test_logger",
            sinks=[failing_sink],
        )

        try:
            with patch(
                "fapilog.core.sink_writers.handle_sink_write_failure"
            ) as mock_fallback:
                mock_fallback.return_value = None
                logger.info("test message")
                _drain_logger(logger)

                # Fallback should have been called
                mock_fallback.assert_called()
        except Exception:
            _drain_logger(logger)
            raise

    def test_false_return_triggers_fallback_handler(self):
        """When a sink returns False, fallback handler should be called."""
        false_sink = FalseReturnSink()

        logger = get_logger(
            "test_logger",
            sinks=[false_sink],
        )

        try:
            with patch(
                "fapilog.core.sink_writers.handle_sink_write_failure"
            ) as mock_fallback:
                mock_fallback.return_value = None
                logger.info("test message from false")
                _drain_logger(logger)

                # Fallback should have been called
                mock_fallback.assert_called()
        except Exception:
            _drain_logger(logger)
            raise

    def test_successful_sink_no_fallback(self):
        """Successful sinks should not trigger fallback."""
        success_sink = SuccessfulSink()

        logger = get_logger(
            "test_logger",
            sinks=[success_sink],
        )

        try:
            with patch(
                "fapilog.core.sink_writers.handle_sink_write_failure"
            ) as mock_fallback:
                logger.info("success message")
                _drain_logger(logger)

                # Successful sink should have the message
                assert len(success_sink.written) == 1
                assert success_sink.written[0]["message"] == "success message"

                # No fallback should be triggered
                mock_fallback.assert_not_called()
        except Exception:
            _drain_logger(logger)
            raise

    def test_mixed_sinks_partial_fallback(self):
        """With mixed sinks, only failing ones trigger fallback."""
        success_sink = SuccessfulSink()
        failing_sink = FailingSink()

        logger = get_logger(
            "test_logger",
            sinks=[success_sink, failing_sink],
        )

        try:
            with patch(
                "fapilog.core.sink_writers.handle_sink_write_failure"
            ) as mock_fallback:
                mock_fallback.return_value = None
                logger.info("mixed test")
                _drain_logger(logger)

                # Success sink should have the message
                assert len(success_sink.written) == 1

                # Fallback should have been called for failing sink
                mock_fallback.assert_called()
        except Exception:
            _drain_logger(logger)
            raise

    def test_logger_continues_after_sink_failure(self):
        """Logger should continue working after sink failures."""
        failing_sink = FailingSink()
        success_sink = SuccessfulSink()

        logger = get_logger(
            "test_logger",
            sinks=[failing_sink, success_sink],
        )

        try:
            with patch(
                "fapilog.core.sink_writers.handle_sink_write_failure"
            ) as mock_fallback:
                mock_fallback.return_value = None

                # Log multiple messages
                logger.info("first message")
                logger.info("second message")
                logger.info("third message")
                _drain_logger(logger)

                # Success sink should have all messages
                assert len(success_sink.written) == 3

                # Logger didn't crash despite failing sink
                assert mock_fallback.call_count == 3
        except Exception:
            _drain_logger(logger)
            raise


class TestFallbackListRedaction:
    """Integration tests for fallback redaction of lists (Story 4.48)."""

    @pytest.mark.asyncio
    async def test_fallback_redacts_sensitive_fields_in_lists(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC6: Fallback redacts sensitive fields within list items."""
        from fapilog.plugins.sinks.fallback import handle_sink_write_failure

        class MockSink:
            name = "mock_sink"

        payload = {"users": [{"password": "secret", "name": "alice"}]}
        await handle_sink_write_failure(
            payload,
            sink=MockSink(),
            error=Exception("test"),
            serialized=False,
            redact_mode="minimal",
        )

        captured = capsys.readouterr()
        # Parse the JSON output to verify redaction
        output = json.loads(captured.err.strip())
        assert output["users"][0]["password"] == "***"
        assert output["users"][0]["name"] == "alice"
        assert "secret" not in captured.err
