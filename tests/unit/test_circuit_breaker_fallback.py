"""Tests for circuit breaker fallback sink routing (Story 4.72).

Tests cover:
- Fallback sink configuration on SinkCircuitBreakerConfig
- Fallback routing in SinkWriterGroup (_write_one, _write_one_serialized, _write_parallel)
- Fallback error containment (no recursive fallback)
- Backward compatibility (no fallback = silent skip)
- Diagnostic emission on fallback activation
- Fallback write metric tracking
- Builder API support
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig


class MockSink:
    """Mock sink for testing."""

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


class TestSinkCircuitBreakerConfigFallback:
    """Test fallback_sink field on SinkCircuitBreakerConfig."""

    def test_fallback_sink_defaults_to_none(self) -> None:
        """SinkCircuitBreakerConfig.fallback_sink defaults to None."""
        config = SinkCircuitBreakerConfig()
        assert config.fallback_sink is None

    def test_fallback_sink_set_to_name(self) -> None:
        """SinkCircuitBreakerConfig accepts fallback_sink name."""
        config = SinkCircuitBreakerConfig(fallback_sink="rotating_file")
        assert config.fallback_sink == "rotating_file"


class TestFallbackRoutingSequential:
    """Test fallback routing in sequential write mode (_write_one)."""

    @pytest.mark.asyncio
    async def test_fallback_receives_events_on_open_circuit(self) -> None:
        """AC1: When circuit is open, events route to the fallback sink."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = MockSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        # Force circuit open
        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        entry = {"message": "test", "level": "INFO"}
        await group.write(entry)

        # Primary should NOT be called
        primary.write.assert_not_called()
        # Fallback SHOULD be called
        fallback.write.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_no_fallback_configured_skips_silently(self) -> None:
        """AC3: Without fallback_sink, circuit-open events are still skipped."""
        from fapilog.core.sink_writers import SinkWriterGroup

        primary = MockSink("http")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        group = SinkWriterGroup([primary], circuit_config=config)

        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        await group.write({"message": "test"})

        primary.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_not_used_when_circuit_closed(self) -> None:
        """Fallback is NOT used when circuit is closed (normal operation)."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = MockSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        entry = {"message": "test"}
        await group.write(entry)

        # Primary is called normally
        primary.write.assert_called_once_with(entry)
        # Fallback NOT called
        fallback.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_error_contained(self) -> None:
        """AC4: If fallback sink also fails, error is contained via handle_sink_write_failure."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = FailingSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ) as mock_handler:
            # Should not raise
            await group.write({"message": "test"})

            # Failure handler should be called for the fallback error
            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert isinstance(call_kwargs["error"], RuntimeError)


class TestFallbackRoutingParallel:
    """Test fallback routing in parallel write mode (_write_parallel)."""

    @pytest.mark.asyncio
    async def test_fallback_works_in_parallel_mode(self) -> None:
        """AC8: Fallback routing works in parallel write mode."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        healthy = MockSink("stdout_json")
        fallback = MockSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary, healthy],
            parallel=True,
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        # Only primary circuit is open
        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        entry = {"message": "test"}
        await group.write(entry)

        # Primary skipped, fallback receives the event
        primary.write.assert_not_called()
        fallback.write.assert_called_once_with(entry)
        # Healthy sink still receives the event
        healthy.write.assert_called_once_with(entry)


class TestFallbackRoutingSerialized:
    """Test fallback routing for serialized writes."""

    @pytest.mark.asyncio
    async def test_serialized_fallback_on_open_circuit(self) -> None:
        """Fallback routing works for write_serialized path."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = MockSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        view = MagicMock()
        await group.write_serialized(view)

        primary.write_serialized.assert_not_called()
        fallback.write_serialized.assert_called_once_with(view)


class TestFallbackDiagnostic:
    """Test diagnostic emission on fallback activation (AC5)."""

    @pytest.mark.asyncio
    async def test_fallback_diagnostic_emitted(self) -> None:
        """AC5: When events start routing to fallback, emit a diagnostic."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = MockSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        with patch("fapilog.core.sink_writers.warn") as mock_warn:
            await group.write({"message": "test"})

            mock_warn.assert_called_once()
            args = mock_warn.call_args
            assert args[0][0] == "circuit-breaker"
            assert "fallback" in args[0][1].lower()


class TestFallbackMetric:
    """Test fallback write metric tracking (AC6)."""

    @pytest.mark.asyncio
    async def test_fallback_metric_incremented(self) -> None:
        """AC6: Fallback write count is tracked in metrics."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = MockSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        await group.write({"message": "test"})

        assert group._fallback_write_count == 1

        # Write again
        await group.write({"message": "test2"})
        assert group._fallback_write_count == 2


class TestFallbackPerSinkConfig:
    """Test per-sink fallback configuration (AC2)."""

    @pytest.mark.asyncio
    async def test_different_sinks_can_have_different_fallbacks(self) -> None:
        """AC2: Different sinks can have different fallback targets."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        http_sink = MockSink("http")
        webhook_sink = MockSink("webhook")
        file_sink = MockSink("rotating_file")
        stdout_sink = MockSink("stdout_json")

        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        # HTTP -> file, Webhook -> stdout
        fb_file_w, fb_file_ws = make_sink_writer(file_sink)
        fb_stdout_w, fb_stdout_ws = make_sink_writer(stdout_sink)
        fallback_writers = {
            id(http_sink): (fb_file_w, fb_file_ws),
            id(webhook_sink): (fb_stdout_w, fb_stdout_ws),
        }

        group = SinkWriterGroup(
            [http_sink, webhook_sink],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        # Open both circuits
        for sink in [http_sink, webhook_sink]:
            breaker = group._breakers[id(sink)]
            breaker.should_allow = MagicMock(return_value=False)

        entry = {"message": "test"}
        await group.write(entry)

        # HTTP fallback -> file
        file_sink.write.assert_called_once_with(entry)
        # Webhook fallback -> stdout
        stdout_sink.write.assert_called_once_with(entry)


class TestSettingsFallbackSink:
    """Test fallback_sink field on CoreSettings."""

    def test_settings_fallback_sink_default_none(self) -> None:
        """CoreSettings has sink_circuit_breaker_fallback_sink defaulting to None."""
        from fapilog.core.settings import CoreSettings

        core = CoreSettings()
        assert core.sink_circuit_breaker_fallback_sink is None

    def test_settings_fallback_sink_configurable(self) -> None:
        """CoreSettings accepts fallback_sink name."""
        from fapilog.core.settings import CoreSettings

        core = CoreSettings(sink_circuit_breaker_fallback_sink="rotating_file")
        assert core.sink_circuit_breaker_fallback_sink == "rotating_file"


class TestBuilderFallbackSink:
    """Test builder API for fallback_sink (AC7)."""

    def test_with_circuit_breaker_fallback_sink(self) -> None:
        """AC7: Builder API supports fallback_sink parameter."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_circuit_breaker(
            enabled=True,
            fallback_sink="rotating_file",
        )

        assert result is builder
        core_config = builder._config.get("core", {})
        assert core_config["sink_circuit_breaker_fallback_sink"] == "rotating_file"

    def test_with_circuit_breaker_no_fallback_by_default(self) -> None:
        """Builder with_circuit_breaker without fallback_sink omits field."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_circuit_breaker(enabled=True)

        core_config = builder._config.get("core", {})
        assert "sink_circuit_breaker_fallback_sink" not in core_config


class TestFallbackWritesMetricCollector:
    """Test fallback writes metric on MetricsCollector."""

    @pytest.mark.asyncio
    async def test_record_fallback_writes_tracks_count(self) -> None:
        """MetricsCollector.record_fallback_writes increments in-memory counter."""
        from fapilog.metrics.metrics import MetricsCollector

        metrics = MetricsCollector(enabled=False)
        assert metrics._fallback_write_count == 0

        await metrics.record_fallback_writes(primary_sink="http", fallback_sink="file")
        assert metrics._fallback_write_count == 1

        await metrics.record_fallback_writes(primary_sink="http", fallback_sink="file")
        assert metrics._fallback_write_count == 2


class TestFallbackSerializedErrors:
    """Test fallback error containment for serialized writes."""

    @pytest.mark.asyncio
    async def test_serialized_fallback_error_contained(self) -> None:
        """Fallback serialized write errors are contained via handle_sink_write_failure."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = FailingSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
        ) as mock_handler:
            view = MagicMock()
            await group.write_serialized(view)

            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args.kwargs
            assert call_kwargs["serialized"] is True
            assert isinstance(call_kwargs["error"], RuntimeError)

    @pytest.mark.asyncio
    async def test_serialized_fallback_handler_exception_contained(self) -> None:
        """If handle_sink_write_failure also raises, error is still contained."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = FailingSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
            side_effect=RuntimeError("handler also fails"),
        ):
            # Should not raise even when handler fails
            view = MagicMock()
            await group.write_serialized(view)

    @pytest.mark.asyncio
    async def test_fallback_handler_exception_contained_for_write(self) -> None:
        """If handle_sink_write_failure raises during write fallback, error is contained."""
        from fapilog.core.sink_writers import SinkWriterGroup, make_sink_writer

        primary = MockSink("http")
        fallback = FailingSink("rotating_file")
        config = SinkCircuitBreakerConfig(enabled=True, failure_threshold=1)

        fb_write, fb_write_s = make_sink_writer(fallback)
        fallback_writers = {id(primary): (fb_write, fb_write_s)}

        group = SinkWriterGroup(
            [primary],
            circuit_config=config,
            fallback_writers=fallback_writers,
        )

        breaker = group._breakers[id(primary)]
        breaker.should_allow = MagicMock(return_value=False)

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            new_callable=AsyncMock,
            side_effect=RuntimeError("handler also fails"),
        ):
            # Should not raise even when handler fails
            await group.write({"message": "test"})


class TestFallbackWritesPrometheusMetric:
    """Test fallback writes metric with Prometheus enabled."""

    @pytest.mark.asyncio
    async def test_prometheus_counter_labeled(self) -> None:
        """Prometheus counter labels with primary_sink and fallback_sink."""
        from fapilog.metrics.metrics import MetricsCollector

        metrics = MetricsCollector(enabled=True)
        await metrics.record_fallback_writes(
            primary_sink="http", fallback_sink="rotating_file"
        )

        assert metrics._fallback_write_count == 1
        if metrics._c_fallback_writes is not None:
            sample = metrics._c_fallback_writes.labels(
                primary_sink="http", fallback_sink="rotating_file"
            )
            assert sample._value.get() == 1.0


class TestFallbackResolution:
    """Test fallback sink resolution during writer construction."""

    def test_resolve_returns_empty_when_no_config(self) -> None:
        """_resolve_fallback_writers returns empty dict when config is None."""
        from fapilog import _resolve_fallback_writers

        result = _resolve_fallback_writers([MockSink()], None)
        assert result == {}

    def test_resolve_returns_empty_when_no_fallback_name(self) -> None:
        """_resolve_fallback_writers returns empty when fallback_sink is None."""
        from fapilog import _resolve_fallback_writers

        config = SinkCircuitBreakerConfig(enabled=True, fallback_sink=None)
        result = _resolve_fallback_writers([MockSink()], config)
        assert result == {}

    def test_resolve_returns_empty_when_sink_not_found(self) -> None:
        """_resolve_fallback_writers returns empty when fallback name doesn't match."""
        from fapilog import _resolve_fallback_writers

        config = SinkCircuitBreakerConfig(enabled=True, fallback_sink="nonexistent")
        result = _resolve_fallback_writers([MockSink("http")], config)
        assert result == {}

    def test_resolve_maps_primary_to_fallback(self) -> None:
        """_resolve_fallback_writers maps non-fallback sinks to fallback writers."""
        from fapilog import _resolve_fallback_writers

        primary = MockSink("http")
        fallback = MockSink("rotating_file")
        sinks = [primary, fallback]

        config = SinkCircuitBreakerConfig(
            enabled=True,
            fallback_sink="rotating_file",
        )

        fb_writers = _resolve_fallback_writers(sinks, config)

        # Primary should have a fallback, fallback (rotating_file) should not
        assert id(primary) in fb_writers
        assert id(fallback) not in fb_writers

    def test_resolve_excludes_fallback_from_own_mapping(self) -> None:
        """Fallback sink should not fall back to itself."""
        from fapilog import _resolve_fallback_writers

        http = MockSink("http")
        webhook = MockSink("webhook")
        file = MockSink("rotating_file")
        sinks = [http, webhook, file]

        config = SinkCircuitBreakerConfig(enabled=True, fallback_sink="rotating_file")
        fb_writers = _resolve_fallback_writers(sinks, config)

        assert id(http) in fb_writers
        assert id(webhook) in fb_writers
        assert id(file) not in fb_writers
