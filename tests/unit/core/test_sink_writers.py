"""Tests for SinkWriterGroup class (Story 5.29).

This module tests the class-based sink writer that replaces the closure-based
_fanout_writer function. Tests cover:
- Class instantiation with various configs
- Sequential and parallel write behavior
- Circuit breaker integration
- Error handling via handle_sink_write_failure
- Serialized write behavior
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig


class MockSink:
    """Mock sink for testing SinkWriterGroup."""

    def __init__(self, name: str = "test_sink") -> None:
        self.name = name
        self.write = AsyncMock(return_value=None)
        self.write_serialized = AsyncMock(return_value=None)
        self._started = False

    async def start(self) -> None:
        self._started = True


class FailingSink:
    """Sink that always raises on write."""

    def __init__(self, name: str = "failing_sink") -> None:
        self.name = name

    async def write(self, entry: dict[str, Any]) -> None:
        raise RuntimeError("Sink write failed")

    async def write_serialized(self, view: object) -> None:
        raise RuntimeError("Serialized write failed")


class FalseReturnSink:
    """Sink that returns False on write (signals failure per Story 4.41)."""

    def __init__(self, name: str = "false_sink") -> None:
        self.name = name

    async def write(self, entry: dict[str, Any]) -> bool:
        return False

    async def write_serialized(self, view: object) -> bool:
        return False


class TestSinkWriterGroupImport:
    """Verify SinkWriterGroup can be imported from core.sink_writers."""

    def test_sink_writer_group_importable(self) -> None:
        """SinkWriterGroup can be imported from fapilog.core.sink_writers."""
        from fapilog.core.sink_writers import SinkWriterGroup

        assert callable(SinkWriterGroup)

    def test_make_sink_writer_importable(self) -> None:
        """make_sink_writer can be imported from fapilog.core.sink_writers."""
        from fapilog.core.sink_writers import make_sink_writer

        assert callable(make_sink_writer)


class TestSinkWriterGroupInstantiation:
    """Test SinkWriterGroup initialization with various configurations."""

    def test_instantiation_with_single_sink(self) -> None:
        """SinkWriterGroup initializes with a single sink."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        group = SinkWriterGroup([sink])

        assert group._sinks == [sink]
        assert len(group._writers) == 1

    def test_instantiation_with_multiple_sinks(self) -> None:
        """SinkWriterGroup initializes with multiple sinks."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sinks = [MockSink("sink1"), MockSink("sink2"), MockSink("sink3")]
        group = SinkWriterGroup(sinks)

        assert len(group._sinks) == 3
        assert len(group._writers) == 3

    def test_instantiation_with_parallel_flag(self) -> None:
        """SinkWriterGroup stores parallel flag correctly."""
        from fapilog.core.sink_writers import SinkWriterGroup

        group = SinkWriterGroup([MockSink()], parallel=True)

        assert group._parallel is True

    def test_instantiation_with_circuit_config(self) -> None:
        """SinkWriterGroup creates breakers when circuit_config enabled."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        config = SinkCircuitBreakerConfig(enabled=True)
        group = SinkWriterGroup([sink], circuit_config=config)

        assert len(group._breakers) == 1
        assert id(sink) in group._breakers

    def test_instantiation_without_circuit_config(self) -> None:
        """SinkWriterGroup has empty breakers when circuit_config disabled."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        group = SinkWriterGroup([sink], circuit_config=None)

        assert group._breakers == {}

    def test_instantiation_with_disabled_circuit_config(self) -> None:
        """SinkWriterGroup has empty breakers when circuit_config.enabled=False."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        config = SinkCircuitBreakerConfig(enabled=False)
        group = SinkWriterGroup([sink], circuit_config=config)

        assert group._breakers == {}


class TestSinkWriterGroupWrite:
    """Test SinkWriterGroup.write() method."""

    @pytest.mark.asyncio
    async def test_write_calls_sink_write(self) -> None:
        """write() calls sink.write with the entry."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        group = SinkWriterGroup([sink])
        entry = {"message": "test", "level": "INFO"}

        await group.write(entry)

        sink.write.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_write_sequential_multiple_sinks(self) -> None:
        """write() in sequential mode calls all sinks."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sinks = [MockSink("sink1"), MockSink("sink2")]
        group = SinkWriterGroup(sinks, parallel=False)
        entry = {"message": "test"}

        await group.write(entry)

        for sink in sinks:
            sink.write.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_write_parallel_multiple_sinks(self) -> None:
        """write() in parallel mode calls all sinks."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sinks = [MockSink("sink1"), MockSink("sink2")]
        group = SinkWriterGroup(sinks, parallel=True)
        entry = {"message": "test"}

        await group.write(entry)

        for sink in sinks:
            sink.write.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_write_single_sink_ignores_parallel_flag(self) -> None:
        """write() with single sink works regardless of parallel flag."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        group = SinkWriterGroup([sink], parallel=True)
        entry = {"message": "test"}

        await group.write(entry)

        sink.write.assert_called_once_with(entry)


class TestSinkWriterGroupWriteSerialized:
    """Test SinkWriterGroup.write_serialized() method."""

    @pytest.mark.asyncio
    async def test_write_serialized_calls_sink(self) -> None:
        """write_serialized() calls sink.write_serialized with the view."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        group = SinkWriterGroup([sink])
        view = MagicMock()

        await group.write_serialized(view)

        sink.write_serialized.assert_called_once_with(view)

    @pytest.mark.asyncio
    async def test_write_serialized_multiple_sinks(self) -> None:
        """write_serialized() calls all sinks."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sinks = [MockSink("sink1"), MockSink("sink2")]
        group = SinkWriterGroup(sinks)
        view = MagicMock()

        await group.write_serialized(view)

        for sink in sinks:
            sink.write_serialized.assert_called_once_with(view)


class TestSinkWriterGroupCircuitBreaker:
    """Test circuit breaker integration with SinkWriterGroup."""

    @pytest.mark.asyncio
    async def test_write_skips_sink_when_circuit_open(self) -> None:
        """write() skips sinks with open circuit breakers."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)
        group = SinkWriterGroup([sink], circuit_config=config)

        # Force circuit open by patching should_allow
        breaker = group._breakers[id(sink)]
        breaker.should_allow = MagicMock(return_value=False)

        await group.write({"message": "test"})

        sink.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_records_success_on_breaker(self) -> None:
        """write() records success when sink write succeeds."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = MockSink()
        config = SinkCircuitBreakerConfig(enabled=True)
        group = SinkWriterGroup([sink], circuit_config=config)

        breaker = group._breakers[id(sink)]
        breaker.record_success = MagicMock()

        await group.write({"message": "test"})

        breaker.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_records_failure_on_exception(self) -> None:
        """write() records failure when sink raises exception."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FailingSink()
        config = SinkCircuitBreakerConfig(enabled=True)
        group = SinkWriterGroup([sink], circuit_config=config)

        breaker = group._breakers[id(sink)]
        breaker.record_failure = MagicMock()

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ):
            await group.write({"message": "test"})

        breaker.record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_records_failure_on_false_return(self) -> None:
        """write() records failure when sink returns False."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FalseReturnSink()
        config = SinkCircuitBreakerConfig(enabled=True)
        group = SinkWriterGroup([sink], circuit_config=config)

        breaker = group._breakers[id(sink)]
        breaker.record_failure = MagicMock()

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ):
            await group.write({"message": "test"})

        breaker.record_failure.assert_called_once()


class TestSinkWriterGroupErrorHandling:
    """Test error handling behavior with handle_sink_write_failure."""

    @pytest.mark.asyncio
    async def test_exception_calls_handle_sink_write_failure(self) -> None:
        """write() calls handle_sink_write_failure when sink raises."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FailingSink()
        group = SinkWriterGroup([sink])
        entry = {"message": "test"}

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ) as mock_handler:
            await group.write(entry)

            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["sink"] is sink
            assert isinstance(call_kwargs["error"], RuntimeError)
            assert call_kwargs["serialized"] is False

    @pytest.mark.asyncio
    async def test_false_return_calls_handle_sink_write_failure(self) -> None:
        """write() calls handle_sink_write_failure when sink returns False."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FalseReturnSink()
        group = SinkWriterGroup([sink])
        entry = {"message": "test"}

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ) as mock_handler:
            await group.write(entry)

            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["sink"] is sink
            assert call_kwargs["serialized"] is False

    @pytest.mark.asyncio
    async def test_error_contained_does_not_propagate(self) -> None:
        """write() contains errors - does not propagate to caller."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FailingSink()
        group = SinkWriterGroup([sink])

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ):
            # Should not raise
            await group.write({"message": "test"})

    @pytest.mark.asyncio
    async def test_one_sink_failure_does_not_affect_others(self) -> None:
        """In sequential mode, one sink failure doesn't prevent others."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sinks = [FailingSink("failing"), MockSink("healthy")]
        group = SinkWriterGroup(sinks, parallel=False)
        entry = {"message": "test"}

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ):
            await group.write(entry)

        # Healthy sink should still be called
        sinks[1].write.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_serialized_error_calls_handler_with_serialized_true(self) -> None:
        """write_serialized() calls handler with serialized=True."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FailingSink()
        group = SinkWriterGroup([sink])
        view = MagicMock()

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ) as mock_handler:
            await group.write_serialized(view)

            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["serialized"] is True


class TestMakeSinkWriter:
    """Test the make_sink_writer helper function."""

    @pytest.mark.asyncio
    async def test_make_sink_writer_returns_tuple(self) -> None:
        """make_sink_writer returns tuple of (write, write_serialized) functions."""
        from fapilog.core.sink_writers import make_sink_writer

        sink = MockSink()
        result = make_sink_writer(sink)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert callable(result[0])
        assert callable(result[1])

    @pytest.mark.asyncio
    async def test_make_sink_writer_write_calls_sink(self) -> None:
        """make_sink_writer write function calls sink.write."""
        from fapilog.core.sink_writers import make_sink_writer

        sink = MockSink()
        write_fn, _ = make_sink_writer(sink)
        entry = {"message": "test"}

        await write_fn(entry)

        sink.write.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_make_sink_writer_starts_sink_on_first_write(self) -> None:
        """make_sink_writer starts sink if not started on first write."""
        from fapilog.core.sink_writers import make_sink_writer

        sink = MockSink()
        sink._started = False
        write_fn, _ = make_sink_writer(sink)

        await write_fn({"message": "test"})

        assert sink._started is True

    @pytest.mark.asyncio
    async def test_make_sink_writer_write_serialized_calls_sink(self) -> None:
        """make_sink_writer write_serialized function calls sink.write_serialized."""
        from fapilog.core.sink_writers import make_sink_writer

        sink = MockSink()
        _, write_serialized_fn = make_sink_writer(sink)
        view = MagicMock()

        await write_serialized_fn(view)

        sink.write_serialized.assert_called_once_with(view)


class TestSinkWriterGroupRedactMode:
    """Test fallback redact_mode parameter (Story 4.46)."""

    @pytest.mark.asyncio
    async def test_write_passes_redact_mode_to_handler(self) -> None:
        """write() passes redact_mode to handle_sink_write_failure."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FailingSink()
        group = SinkWriterGroup([sink], redact_mode="none")
        entry = {"message": "test"}

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ) as mock_handler:
            await group.write(entry)

            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["redact_mode"] == "none"

    @pytest.mark.asyncio
    async def test_default_redact_mode_is_minimal(self) -> None:
        """SinkWriterGroup defaults redact_mode to 'minimal'."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FailingSink()
        group = SinkWriterGroup([sink])
        entry = {"message": "test"}

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ) as mock_handler:
            await group.write(entry)

            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["redact_mode"] == "minimal"

    @pytest.mark.asyncio
    async def test_write_serialized_passes_redact_mode(self) -> None:
        """write_serialized() passes redact_mode to handler."""
        from fapilog.core.sink_writers import SinkWriterGroup

        sink = FailingSink()
        group = SinkWriterGroup([sink], redact_mode="inherit")
        view = MagicMock()

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ) as mock_handler:
            await group.write_serialized(view)

            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["redact_mode"] == "inherit"
