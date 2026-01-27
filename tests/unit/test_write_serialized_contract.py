"""
Contract tests for write_serialized error handling (Story 4.53).

All sinks implementing write_serialized must:
1. Raise SinkWriteError on deserialization failure (AC1, AC3)
2. Emit diagnostics on failure (AC2)
3. Never silently replace data with placeholders (AC1)

This module tests all affected sinks parametrically.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fapilog.core.errors import SinkWriteError
from fapilog.core.serialization import SerializedView

# Test data: invalid JSON that should trigger deserialization errors
INVALID_JSON_BYTES = b"not valid json {{{"
INVALID_UTF8_BYTES = b"\xff\xfe invalid utf-8"


class TestHttpSinkWriteSerializedContract:
    """HttpSink write_serialized must raise SinkWriteError on invalid data."""

    @pytest.fixture
    def http_sink(self) -> Any:
        """Create HttpSink with mocked pool."""
        from fapilog.plugins.sinks.http_client import HttpSink, HttpSinkConfig

        config = HttpSinkConfig(endpoint="http://example.com/logs")
        sink = HttpSink(config)
        # Mock the pool and sender to avoid network calls
        sink._pool = MagicMock()
        sink._sender = MagicMock()
        return sink

    @pytest.mark.asyncio
    async def test_raises_sink_write_error_on_invalid_json(
        self, http_sink: Any
    ) -> None:
        """write_serialized must raise SinkWriteError on invalid JSON."""
        invalid_view = SerializedView(memoryview(INVALID_JSON_BYTES))

        with pytest.raises(SinkWriteError) as exc_info:
            await http_sink.write_serialized(invalid_view)

        assert exc_info.value.context.plugin_name == "http"
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

    @pytest.mark.asyncio
    async def test_emits_diagnostics_on_failure(self, http_sink: Any) -> None:
        """write_serialized must emit diagnostics when deserialization fails."""
        invalid_view = SerializedView(memoryview(INVALID_JSON_BYTES))

        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            with pytest.raises(SinkWriteError):
                await http_sink.write_serialized(invalid_view)

            mock_warn.assert_called_once()
            call_args = mock_warn.call_args
            assert "http" in call_args[0][0].lower()
            assert (
                "deserialize" in call_args[0][1].lower()
                or "deserialize" in str(call_args.kwargs).lower()
            )


class TestWebhookSinkWriteSerializedContract:
    """WebhookSink write_serialized must raise SinkWriteError on invalid data."""

    @pytest.fixture
    def webhook_sink(self) -> Any:
        """Create WebhookSink with mocked pool."""
        from fapilog.plugins.sinks.webhook import WebhookSink, WebhookSinkConfig

        config = WebhookSinkConfig(endpoint="http://example.com/webhook")
        sink = WebhookSink(config)
        sink._pool = MagicMock()
        return sink

    @pytest.mark.asyncio
    async def test_raises_sink_write_error_on_invalid_json(
        self, webhook_sink: Any
    ) -> None:
        """write_serialized must raise SinkWriteError on invalid JSON."""
        invalid_view = SerializedView(memoryview(INVALID_JSON_BYTES))

        with pytest.raises(SinkWriteError) as exc_info:
            await webhook_sink.write_serialized(invalid_view)

        assert exc_info.value.context.plugin_name == "webhook"
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

    @pytest.mark.asyncio
    async def test_emits_diagnostics_on_failure(self, webhook_sink: Any) -> None:
        """write_serialized must emit diagnostics when deserialization fails."""
        invalid_view = SerializedView(memoryview(INVALID_JSON_BYTES))

        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            with pytest.raises(SinkWriteError):
                await webhook_sink.write_serialized(invalid_view)

            mock_warn.assert_called_once()
            call_args = mock_warn.call_args
            assert "webhook" in call_args[0][0].lower()


class TestLokiSinkWriteSerializedContract:
    """LokiSink write_serialized must raise SinkWriteError on invalid data."""

    @pytest.fixture
    def loki_sink(self) -> Any:
        """Create LokiSink with mocked client."""
        from fapilog.plugins.sinks.contrib.loki import LokiSink, LokiSinkConfig

        config = LokiSinkConfig(url="http://localhost:3100")
        sink = LokiSink(config)
        sink._client = MagicMock()
        return sink

    @pytest.mark.asyncio
    async def test_raises_sink_write_error_on_invalid_utf8(
        self, loki_sink: Any
    ) -> None:
        """write_serialized must raise SinkWriteError on invalid UTF-8."""
        invalid_view = SerializedView(memoryview(INVALID_UTF8_BYTES))

        with pytest.raises(SinkWriteError) as exc_info:
            await loki_sink.write_serialized(invalid_view)

        assert exc_info.value.context.plugin_name == "loki"
        assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)

    @pytest.mark.asyncio
    async def test_emits_diagnostics_on_failure(self, loki_sink: Any) -> None:
        """write_serialized must emit diagnostics when deserialization fails."""
        invalid_view = SerializedView(memoryview(INVALID_UTF8_BYTES))

        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            with pytest.raises(SinkWriteError):
                await loki_sink.write_serialized(invalid_view)

            mock_warn.assert_called_once()
            call_args = mock_warn.call_args
            assert "loki" in call_args[0][0].lower()


class TestCloudWatchSinkWriteSerializedContract:
    """CloudWatchSink write_serialized must raise SinkWriteError on invalid data."""

    @pytest.fixture
    def cloudwatch_sink(self) -> Any:
        """Create CloudWatchSink with mocked client."""
        from fapilog.plugins.sinks.contrib.cloudwatch import (
            CloudWatchSink,
            CloudWatchSinkConfig,
        )

        config = CloudWatchSinkConfig(log_group_name="/test/logs")
        sink = CloudWatchSink(config)
        sink._client = MagicMock()
        return sink

    @pytest.mark.asyncio
    async def test_raises_sink_write_error_on_invalid_utf8(
        self, cloudwatch_sink: Any
    ) -> None:
        """write_serialized must raise SinkWriteError on invalid UTF-8."""
        invalid_view = SerializedView(memoryview(INVALID_UTF8_BYTES))

        with pytest.raises(SinkWriteError) as exc_info:
            await cloudwatch_sink.write_serialized(invalid_view)

        assert exc_info.value.context.plugin_name == "cloudwatch"
        assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)

    @pytest.mark.asyncio
    async def test_emits_diagnostics_on_failure(self, cloudwatch_sink: Any) -> None:
        """write_serialized must emit diagnostics when deserialization fails."""
        invalid_view = SerializedView(memoryview(INVALID_UTF8_BYTES))

        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            with pytest.raises(SinkWriteError):
                await cloudwatch_sink.write_serialized(invalid_view)

            mock_warn.assert_called_once()
            call_args = mock_warn.call_args
            assert "cloudwatch" in call_args[0][0].lower()


class TestPostgresSinkWriteSerializedContract:
    """PostgresSink write_serialized must raise SinkWriteError on invalid data."""

    @pytest.fixture
    def postgres_sink(self) -> Any:
        """Create PostgresSink with mocked pool."""
        from fapilog.plugins.sinks.contrib.postgres import (
            PostgresSink,
            PostgresSinkConfig,
        )

        config = PostgresSinkConfig(dsn="postgresql://localhost/test")
        sink = PostgresSink(config)
        sink._pool = MagicMock()
        return sink

    @pytest.mark.asyncio
    async def test_raises_sink_write_error_on_invalid_json(
        self, postgres_sink: Any
    ) -> None:
        """write_serialized must raise SinkWriteError on invalid JSON."""
        invalid_view = SerializedView(memoryview(INVALID_JSON_BYTES))

        with pytest.raises(SinkWriteError) as exc_info:
            await postgres_sink.write_serialized(invalid_view)

        assert exc_info.value.context.plugin_name == "postgres"
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

    @pytest.mark.asyncio
    async def test_raises_sink_write_error_on_non_dict_json(
        self, postgres_sink: Any
    ) -> None:
        """write_serialized must raise SinkWriteError when JSON is not a dict."""
        # Valid JSON but not a dict - should also signal failure
        array_json = b'["item1", "item2"]'
        invalid_view = SerializedView(memoryview(array_json))

        with pytest.raises(SinkWriteError) as exc_info:
            await postgres_sink.write_serialized(invalid_view)

        assert "postgres" in exc_info.value.context.plugin_name.lower()

    @pytest.mark.asyncio
    async def test_emits_diagnostics_on_failure(self, postgres_sink: Any) -> None:
        """write_serialized must emit diagnostics when deserialization fails."""
        invalid_view = SerializedView(memoryview(INVALID_JSON_BYTES))

        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            with pytest.raises(SinkWriteError):
                await postgres_sink.write_serialized(invalid_view)

            mock_warn.assert_called_once()
            call_args = mock_warn.call_args
            assert "postgres" in call_args[0][0].lower()


class TestWriteSerializedSuccessPath:
    """Verify write_serialized succeeds with valid data."""

    @pytest.mark.asyncio
    async def test_http_sink_succeeds_with_valid_json(self) -> None:
        """HttpSink write_serialized should succeed with valid JSON."""
        from fapilog.plugins.sinks.http_client import HttpSink, HttpSinkConfig

        config = HttpSinkConfig(endpoint="http://example.com/logs")
        sink = HttpSink(config)
        sink._pool = MagicMock()
        sink._batch_queue = AsyncMock()
        sink._batch_queue.put = AsyncMock()

        valid_json = b'{"message": "test", "level": "INFO"}'
        valid_view = SerializedView(memoryview(valid_json))

        # Should not raise
        await sink.write_serialized(valid_view)

    @pytest.mark.asyncio
    async def test_webhook_sink_succeeds_with_valid_json(self) -> None:
        """WebhookSink write_serialized should succeed with valid JSON."""
        from fapilog.plugins.sinks.webhook import WebhookSink, WebhookSinkConfig

        config = WebhookSinkConfig(endpoint="http://example.com/webhook")
        sink = WebhookSink(config)
        sink._pool = MagicMock()
        sink._batch_queue = AsyncMock()
        sink._batch_queue.put = AsyncMock()

        valid_json = b'{"message": "test", "level": "INFO"}'
        valid_view = SerializedView(memoryview(valid_json))

        # Should not raise
        await sink.write_serialized(valid_view)

    @pytest.mark.asyncio
    async def test_loki_sink_succeeds_with_valid_utf8(self) -> None:
        """LokiSink write_serialized should succeed with valid UTF-8."""
        from fapilog.plugins.sinks.contrib.loki import LokiSink, LokiSinkConfig

        config = LokiSinkConfig(url="http://localhost:3100")
        sink = LokiSink(config)
        sink._client = MagicMock()
        sink._batch_queue = AsyncMock()
        sink._batch_queue.put = AsyncMock()

        valid_json = b'{"message": "test", "level": "INFO"}'
        valid_view = SerializedView(memoryview(valid_json))

        # Should not raise
        await sink.write_serialized(valid_view)

    @pytest.mark.asyncio
    async def test_cloudwatch_sink_succeeds_with_valid_utf8(self) -> None:
        """CloudWatchSink write_serialized should succeed with valid UTF-8."""
        from fapilog.plugins.sinks.contrib.cloudwatch import (
            CloudWatchSink,
            CloudWatchSinkConfig,
        )

        config = CloudWatchSinkConfig(log_group_name="/test/logs")
        sink = CloudWatchSink(config)
        sink._client = MagicMock()
        sink._batch_queue = AsyncMock()
        sink._batch_queue.put = AsyncMock()

        valid_json = b'{"message": "test", "level": "INFO"}'
        valid_view = SerializedView(memoryview(valid_json))

        # Should not raise
        await sink.write_serialized(valid_view)

    @pytest.mark.asyncio
    async def test_postgres_sink_succeeds_with_valid_json_dict(self) -> None:
        """PostgresSink write_serialized should succeed with valid JSON dict."""
        from fapilog.plugins.sinks.contrib.postgres import (
            PostgresSink,
            PostgresSinkConfig,
        )

        config = PostgresSinkConfig(dsn="postgresql://localhost/test")
        sink = PostgresSink(config)
        sink._pool = MagicMock()
        sink._batch_queue = AsyncMock()
        sink._batch_queue.put = AsyncMock()

        valid_json = b'{"message": "test", "level": "INFO"}'
        valid_view = SerializedView(memoryview(valid_json))

        # Should not raise
        await sink.write_serialized(valid_view)
