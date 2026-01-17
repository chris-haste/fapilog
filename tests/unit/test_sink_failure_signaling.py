"""
Tests for sink failure signaling (Story 4.41).

Scope:
- SinkWriteError class and attributes
- Fanout writer handles SinkWriteError and False returns
- Routing writer handles SinkWriteError and False returns
- Circuit breaker integration with signaled failures
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fapilog.core.errors import (
    ErrorCategory,
    ErrorRecoveryStrategy,
    ErrorSeverity,
    PluginError,
    SinkWriteError,
)


class TestSinkWriteError:
    """Test SinkWriteError class."""

    def test_sink_write_error_is_plugin_error(self):
        """SinkWriteError should be a subclass of PluginError."""
        error = SinkWriteError("write failed", sink_name="test_sink")
        assert isinstance(error, PluginError)

    def test_sink_write_error_has_correct_category(self):
        """SinkWriteError should have IO category."""
        error = SinkWriteError("write failed")
        assert error.context.category == ErrorCategory.IO

    def test_sink_write_error_has_high_severity(self):
        """SinkWriteError should have HIGH severity."""
        error = SinkWriteError("write failed")
        assert error.context.severity == ErrorSeverity.HIGH

    def test_sink_write_error_has_fallback_recovery(self):
        """SinkWriteError should use FALLBACK recovery strategy."""
        error = SinkWriteError("write failed")
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.FALLBACK

    def test_sink_write_error_stores_sink_name(self):
        """SinkWriteError should store the sink name in context."""
        error = SinkWriteError("write failed", sink_name="my_sink")
        assert error.context.plugin_name == "my_sink"

    def test_sink_write_error_chains_cause(self):
        """SinkWriteError should chain the original exception."""
        original = OSError("disk full")
        error = SinkWriteError("write failed", cause=original)
        assert error.__cause__ is original

    def test_sink_write_error_message(self):
        """SinkWriteError should preserve the message."""
        error = SinkWriteError("Failed to write to stdout_json")
        assert error.message == "Failed to write to stdout_json"
        assert str(error) == "Failed to write to stdout_json"


class TestFanoutWriterFailureHandling:
    """Test _fanout_writer handles failure signals."""

    @pytest.mark.asyncio
    async def test_fanout_writer_handles_sink_write_error(self):
        """Fanout writer should catch SinkWriteError and trigger fallback."""
        from fapilog import _fanout_writer

        # Create a sink that raises SinkWriteError
        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"

        async def failing_write(entry):
            raise SinkWriteError("write failed", sink_name="failing_sink")

        mock_sink.write = failing_write
        mock_sink.write_serialized = AsyncMock()

        write_fn, _ = _fanout_writer([mock_sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            # Should not raise - error should be contained
            await write_fn({"message": "test"})
            # Fallback should have been called
            mock_fallback.assert_called_once()
            call_kwargs = mock_fallback.call_args.kwargs
            assert call_kwargs["sink"] is mock_sink
            assert isinstance(call_kwargs["error"], SinkWriteError)

    @pytest.mark.asyncio
    async def test_fanout_writer_handles_false_return(self):
        """Fanout writer should treat False return as failure."""
        from fapilog import _fanout_writer

        # Create a sink that returns False
        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"

        async def failing_write(entry):
            return False  # Signal failure

        mock_sink.write = failing_write
        mock_sink.write_serialized = AsyncMock()

        write_fn, _ = _fanout_writer([mock_sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            await write_fn({"message": "test"})
            # Fallback should have been called for False return
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_fanout_writer_false_increments_circuit_breaker(self):
        """Fanout writer should increment circuit breaker on False return."""
        from fapilog import _fanout_writer
        from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"

        async def failing_write(entry):
            return False

        mock_sink.write = failing_write
        mock_sink.write_serialized = AsyncMock()

        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=3)
        write_fn, _ = _fanout_writer([mock_sink], circuit_config=config)

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            # Write multiple times
            for _ in range(3):
                await write_fn({"message": "test"})

            # After 3 failures, circuit should be open
            # Next write should be skipped (no fallback call)
            mock_fallback.reset_mock()
            await write_fn({"message": "test"})
            # No fallback because circuit is open - write was skipped
            mock_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_fanout_writer_none_return_is_success(self):
        """Fanout writer should treat None return as success."""
        from fapilog import _fanout_writer

        mock_sink = MagicMock()
        mock_sink.name = "ok_sink"

        async def ok_write(entry):
            return None  # Success (default)

        mock_sink.write = ok_write
        mock_sink.write_serialized = AsyncMock()

        write_fn, _ = _fanout_writer([mock_sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            await write_fn({"message": "test"})
            # No fallback for success
            mock_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_fanout_writer_true_return_is_success(self):
        """Fanout writer should treat True return as success."""
        from fapilog import _fanout_writer

        mock_sink = MagicMock()
        mock_sink.name = "ok_sink"

        async def ok_write(entry):
            return True  # Explicit success

        mock_sink.write = ok_write
        mock_sink.write_serialized = AsyncMock()

        write_fn, _ = _fanout_writer([mock_sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            await write_fn({"message": "test"})
            mock_fallback.assert_not_called()


class TestRoutingWriterFailureHandling:
    """Test RoutingSinkWriter handles failure signals."""

    @pytest.mark.asyncio
    async def test_routing_writer_handles_sink_write_error(self):
        """Routing writer should catch SinkWriteError and trigger fallback."""
        from fapilog.core.routing import RoutingSinkWriter

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"

        async def failing_write(entry):
            raise SinkWriteError("write failed", sink_name="failing_sink")

        mock_sink.write = failing_write
        mock_sink.write_serialized = AsyncMock()

        writer = RoutingSinkWriter(
            sinks=[mock_sink],
            rules=[({"INFO"}, ["failing_sink"])],
            fallback_sink_names=[],
        )

        with patch(
            "fapilog.plugins.sinks.fallback.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            await writer.write({"level": "INFO", "message": "test"})
            mock_fallback.assert_called_once()
            call_kwargs = mock_fallback.call_args.kwargs
            assert isinstance(call_kwargs["error"], SinkWriteError)

    @pytest.mark.asyncio
    async def test_routing_writer_handles_false_return(self):
        """Routing writer should treat False return as failure."""
        from fapilog.core.routing import RoutingSinkWriter

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"

        async def failing_write(entry):
            return False

        mock_sink.write = failing_write
        mock_sink.write_serialized = AsyncMock()

        writer = RoutingSinkWriter(
            sinks=[mock_sink],
            rules=[({"INFO"}, ["failing_sink"])],
            fallback_sink_names=[],
        )

        with patch(
            "fapilog.plugins.sinks.fallback.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            await writer.write({"level": "INFO", "message": "test"})
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_routing_writer_false_increments_circuit_breaker(self):
        """Routing writer should increment circuit breaker on False return."""
        from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig
        from fapilog.core.routing import RoutingSinkWriter

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"

        async def failing_write(entry):
            return False

        mock_sink.write = failing_write
        mock_sink.write_serialized = AsyncMock()

        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=3)
        writer = RoutingSinkWriter(
            sinks=[mock_sink],
            rules=[({"INFO"}, ["failing_sink"])],
            fallback_sink_names=[],
            circuit_config=config,
        )

        with patch(
            "fapilog.plugins.sinks.fallback.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            for _ in range(3):
                await writer.write({"level": "INFO", "message": "test"})

            mock_fallback.reset_mock()
            await writer.write({"level": "INFO", "message": "test"})
            # Circuit open - write skipped, no fallback
            mock_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_routing_writer_none_return_is_success(self):
        """Routing writer should treat None return as success."""
        from fapilog.core.routing import RoutingSinkWriter

        mock_sink = MagicMock()
        mock_sink.name = "ok_sink"

        async def ok_write(entry):
            return None

        mock_sink.write = ok_write
        mock_sink.write_serialized = AsyncMock()

        writer = RoutingSinkWriter(
            sinks=[mock_sink],
            rules=[({"INFO"}, ["ok_sink"])],
            fallback_sink_names=[],
        )

        with patch(
            "fapilog.plugins.sinks.fallback.handle_sink_write_failure"
        ) as mock_fallback:
            await writer.write({"level": "INFO", "message": "test"})
            mock_fallback.assert_not_called()


class TestSinkErrorSignaling:
    """Test that built-in sinks signal errors via SinkWriteError."""

    @pytest.mark.asyncio
    async def test_stdout_json_raises_sink_write_error_on_failure(self):
        """StdoutJsonSink should raise SinkWriteError on write failure."""
        from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

        sink = StdoutJsonSink()

        with patch("sys.stdout.buffer.fileno", side_effect=OSError("broken pipe")):
            with patch("sys.stdout.buffer.writelines", side_effect=OSError("broken")):
                with pytest.raises(SinkWriteError) as exc_info:
                    await sink.write({"message": "test"})
                assert (
                    "stdout_json" in str(exc_info.value).lower()
                    or exc_info.value.context.plugin_name == "stdout_json"
                )

    @pytest.mark.asyncio
    async def test_rotating_file_raises_sink_write_error_on_failure(self, tmp_path):
        """RotatingFileSink should raise SinkWriteError on write failure."""
        from fapilog.plugins.sinks.rotating_file import (
            RotatingFileSink,
            RotatingFileSinkConfig,
        )

        config = RotatingFileSinkConfig(directory=tmp_path)
        sink = RotatingFileSink(config)
        await sink.start()

        # Force a write failure by closing the file
        if sink._active_file:
            sink._active_file.close()
            sink._active_file = None
            sink._active_path = None

        # Mock _open_new_file to raise an error
        async def failing_open():
            raise OSError("cannot open file")

        sink._open_new_file = failing_open

        with pytest.raises(SinkWriteError) as exc_info:
            await sink.write({"message": "test"})
        assert exc_info.value.context.plugin_name == "rotating_file"


class TestFanoutWriterSerializedPath:
    """Test _fanout_writer write_serialized handles failure signals."""

    @pytest.mark.asyncio
    async def test_fanout_writer_serialized_false_return_triggers_fallback(self):
        """Fanout writer write_serialized should treat False as failure."""
        from fapilog import _fanout_writer

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"
        mock_sink.write = AsyncMock(return_value=None)

        async def failing_write_serialized(view):
            return False

        mock_sink.write_serialized = failing_write_serialized

        _, write_serialized_fn = _fanout_writer([mock_sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            await write_serialized_fn(b'{"message": "test"}')
            mock_fallback.assert_called_once()
            call_kwargs = mock_fallback.call_args.kwargs
            assert call_kwargs["serialized"] is True

    @pytest.mark.asyncio
    async def test_fanout_writer_serialized_exception_triggers_fallback(self):
        """Fanout writer write_serialized should catch exceptions."""
        from fapilog import _fanout_writer

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"
        mock_sink.write = AsyncMock(return_value=None)

        async def failing_write_serialized(view):
            raise SinkWriteError("write failed", sink_name="failing_sink")

        mock_sink.write_serialized = failing_write_serialized

        _, write_serialized_fn = _fanout_writer([mock_sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            await write_serialized_fn(b'{"message": "test"}')
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_fanout_writer_serialized_circuit_breaker_skip(self):
        """Fanout writer write_serialized should skip open circuit."""
        from fapilog import _fanout_writer
        from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"
        mock_sink.write = AsyncMock(return_value=False)

        async def failing_write_serialized(view):
            return False

        mock_sink.write_serialized = failing_write_serialized

        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=2)
        write_fn, write_serialized_fn = _fanout_writer(
            [mock_sink], circuit_config=config
        )

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            # Open the circuit via write() failures
            await write_fn({"message": "test"})
            await write_fn({"message": "test"})

            # Circuit should be open now
            mock_fallback.reset_mock()
            await write_serialized_fn(b'{"message": "test"}')
            # Skipped due to open circuit - no fallback
            mock_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_fanout_writer_serialized_records_success(self):
        """Fanout writer write_serialized should record success."""
        from fapilog import _fanout_writer
        from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig

        mock_sink = MagicMock()
        mock_sink.name = "ok_sink"
        mock_sink.write = AsyncMock(return_value=None)

        async def ok_write_serialized(view):
            return None

        mock_sink.write_serialized = ok_write_serialized

        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=3)
        _, write_serialized_fn = _fanout_writer([mock_sink], circuit_config=config)

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            await write_serialized_fn(b'{"message": "test"}')
            mock_fallback.assert_not_called()


class TestRoutingWriterSerializedPath:
    """Test RoutingSinkWriter write_serialized handles failure signals."""

    @pytest.mark.asyncio
    async def test_routing_writer_serialized_false_triggers_fallback(self):
        """Routing writer write_serialized should treat False as failure."""
        from fapilog.core.routing import RoutingSinkWriter

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"
        mock_sink.write = AsyncMock(return_value=None)

        async def failing_write_serialized(view):
            return False

        mock_sink.write_serialized = failing_write_serialized

        writer = RoutingSinkWriter(
            sinks=[mock_sink],
            rules=[({"INFO"}, ["failing_sink"])],
            fallback_sink_names=[],
        )

        with patch(
            "fapilog.plugins.sinks.fallback.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            await writer.write_serialized(
                b'{"level": "INFO", "message": "test"}', level="INFO"
            )
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_routing_writer_contains_fallback_exception(self):
        """Routing writer should contain exceptions from fallback handler."""
        from fapilog.core.routing import RoutingSinkWriter

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"

        async def failing_write(entry):
            return False

        mock_sink.write = failing_write
        mock_sink.write_serialized = AsyncMock(return_value=None)

        writer = RoutingSinkWriter(
            sinks=[mock_sink],
            rules=[({"INFO"}, ["failing_sink"])],
            fallback_sink_names=[],
        )

        with patch(
            "fapilog.plugins.sinks.fallback.handle_sink_write_failure",
            side_effect=RuntimeError("fallback failed"),
        ):
            # Should not raise - fallback exception should be contained
            await writer.write({"level": "INFO", "message": "test"})


class TestFallbackExceptionContainment:
    """Test that exceptions from fallback handler are contained."""

    @pytest.mark.asyncio
    async def test_fanout_writer_contains_fallback_exception_on_false(self):
        """Fanout writer should contain fallback exceptions when sink returns False."""
        from fapilog import _fanout_writer

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"

        async def failing_write(entry):
            return False

        mock_sink.write = failing_write
        mock_sink.write_serialized = AsyncMock(return_value=None)

        write_fn, _ = _fanout_writer([mock_sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            side_effect=RuntimeError("fallback failed"),
        ):
            # Should not raise - exception should be contained
            await write_fn({"message": "test"})

    @pytest.mark.asyncio
    async def test_fanout_writer_serialized_contains_fallback_exception(self):
        """Fanout writer write_serialized should contain fallback exceptions."""
        from fapilog import _fanout_writer

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"
        mock_sink.write = AsyncMock(return_value=None)

        async def failing_write_serialized(view):
            return False

        mock_sink.write_serialized = failing_write_serialized

        _, write_serialized_fn = _fanout_writer([mock_sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            side_effect=RuntimeError("fallback failed"),
        ):
            # Should not raise
            await write_serialized_fn(b'{"message": "test"}')

    @pytest.mark.asyncio
    async def test_fanout_writer_serialized_circuit_breaker_on_false(self):
        """Fanout writer write_serialized should record circuit breaker failure on False."""
        from fapilog import _fanout_writer
        from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"
        mock_sink.write = AsyncMock(return_value=None)

        async def failing_write_serialized(view):
            return False

        mock_sink.write_serialized = failing_write_serialized

        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=2)
        _, write_serialized_fn = _fanout_writer([mock_sink], circuit_config=config)

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            # Two failures should open the circuit
            await write_serialized_fn(b'{"message": "test"}')
            await write_serialized_fn(b'{"message": "test"}')
            assert mock_fallback.call_count == 2

            # Third call should be skipped (circuit open)
            mock_fallback.reset_mock()
            await write_serialized_fn(b'{"message": "test"}')
            mock_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_fanout_writer_serialized_circuit_breaker_on_exception(self):
        """Fanout writer write_serialized should record circuit breaker failure on exception."""
        from fapilog import _fanout_writer
        from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig

        mock_sink = MagicMock()
        mock_sink.name = "failing_sink"
        mock_sink.write = AsyncMock(return_value=None)

        async def failing_write_serialized(view):
            raise SinkWriteError("write failed", sink_name="failing_sink")

        mock_sink.write_serialized = failing_write_serialized

        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=2)
        _, write_serialized_fn = _fanout_writer([mock_sink], circuit_config=config)

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure"
        ) as mock_fallback:
            mock_fallback.return_value = None
            # Two failures should open the circuit
            await write_serialized_fn(b'{"message": "test"}')
            await write_serialized_fn(b'{"message": "test"}')
            assert mock_fallback.call_count == 2

            # Third call should be skipped (circuit open)
            mock_fallback.reset_mock()
            await write_serialized_fn(b'{"message": "test"}')
            mock_fallback.assert_not_called()
