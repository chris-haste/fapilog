"""
Tests for sink circuit breaker and fault isolation (Story 4.35).

Verifies that sink failures are isolated via circuit breakers and
that parallel fanout works correctly.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import get_test_timeout
from fapilog.core.circuit_breaker import CircuitState

# -----------------------------------------------------------------------------
# Tests for SinkCircuitBreaker
# -----------------------------------------------------------------------------


class TestSinkCircuitBreaker:
    """Tests for the SinkCircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """Circuit breaker starts in closed state."""
        from fapilog.core.circuit_breaker import (
            SinkCircuitBreaker,
            SinkCircuitBreakerConfig,
        )

        config = SinkCircuitBreakerConfig()
        breaker = SinkCircuitBreaker("test_sink", config)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.should_allow()
        assert not breaker.is_open

    def test_circuit_opens_after_threshold_failures(self):
        """Circuit opens after reaching failure threshold."""
        from fapilog.core.circuit_breaker import (
            SinkCircuitBreaker,
            SinkCircuitBreakerConfig,
        )

        config = SinkCircuitBreakerConfig(failure_threshold=3)
        breaker = SinkCircuitBreaker("test_sink", config)

        # Record failures up to threshold
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open
        assert not breaker.should_allow()

    def test_success_resets_failure_count(self):
        """Successful call resets failure count in closed state."""
        from fapilog.core.circuit_breaker import (
            SinkCircuitBreaker,
            SinkCircuitBreakerConfig,
        )

        config = SinkCircuitBreakerConfig(failure_threshold=3)
        breaker = SinkCircuitBreaker("test_sink", config)

        # Record some failures
        breaker.record_failure()
        breaker.record_failure()
        assert breaker._failure_count == 2

        # Success resets count
        breaker.record_success()
        assert breaker._failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_circuit_transitions_to_half_open_after_timeout(self):
        """Circuit transitions to half-open after recovery timeout.

        Uses CI timeout multiplier for adequate margin on slow CI runners.
        """
        from fapilog.core.circuit_breaker import (
            SinkCircuitBreaker,
            SinkCircuitBreakerConfig,
        )

        config = SinkCircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=get_test_timeout(0.05),
        )
        breaker = SinkCircuitBreaker("test_sink", config)

        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert not breaker.should_allow()

        # Wait for recovery timeout with adequate margin
        time.sleep(get_test_timeout(0.06))

        # should_allow() should transition to half-open
        assert breaker.should_allow()
        assert breaker.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes_circuit(self):
        """Successful call in half-open state closes the circuit."""
        from fapilog.core.circuit_breaker import (
            SinkCircuitBreaker,
            SinkCircuitBreakerConfig,
        )

        config = SinkCircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=get_test_timeout(0.01),
        )
        breaker = SinkCircuitBreaker("test_sink", config)

        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait and transition to half-open
        time.sleep(get_test_timeout(0.02))
        breaker.should_allow()
        assert breaker.state == CircuitState.HALF_OPEN

        # Success closes the circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0

    def test_failure_in_half_open_reopens_circuit(self):
        """Failure in half-open state reopens the circuit."""
        from fapilog.core.circuit_breaker import (
            SinkCircuitBreaker,
            SinkCircuitBreakerConfig,
        )

        config = SinkCircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=get_test_timeout(0.01),
        )
        breaker = SinkCircuitBreaker("test_sink", config)

        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait and transition to half-open
        time.sleep(get_test_timeout(0.02))
        breaker.should_allow()
        assert breaker.state == CircuitState.HALF_OPEN

        # Failure reopens the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_half_open_limits_calls(self):
        """Half-open state limits number of probe calls.

        should_allow() atomically increments and checks the call limit.
        """
        from fapilog.core.circuit_breaker import (
            SinkCircuitBreaker,
            SinkCircuitBreakerConfig,
        )

        config = SinkCircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=get_test_timeout(0.01),
            half_open_max_calls=2,
        )
        breaker = SinkCircuitBreaker("test_sink", config)

        # Open and transition to half-open (counts as call 1)
        breaker.record_failure()
        time.sleep(get_test_timeout(0.02))
        assert breaker.should_allow()  # Transitions to HALF_OPEN, call 1
        assert breaker.state == CircuitState.HALF_OPEN

        # Second call should be allowed (call 2, at limit)
        assert breaker.should_allow()

        # Third call should be denied (exceeds half_open_max_calls=2)
        assert not breaker.should_allow()


# -----------------------------------------------------------------------------
# Tests for Parallel Fanout Writer
# -----------------------------------------------------------------------------


class TestParallelFanoutWriter:
    """Tests for parallel fanout with circuit breakers."""

    @pytest.mark.asyncio
    async def test_sequential_fanout_writes_to_all_sinks(self):
        """Sequential fanout writes to all sinks."""
        from fapilog import _fanout_writer

        sink1 = MagicMock()
        sink1.write = AsyncMock()
        sink2 = MagicMock()
        sink2.write = AsyncMock()

        write, _ = _fanout_writer([sink1, sink2])
        await write({"message": "test"})

        sink1.write.assert_called_once()
        sink2.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_parallel_fanout_writes_to_all_sinks(self):
        """Parallel fanout writes to all sinks concurrently."""
        from fapilog import _fanout_writer

        sink1 = MagicMock()
        sink1.write = AsyncMock()
        sink2 = MagicMock()
        sink2.write = AsyncMock()

        write, _ = _fanout_writer(
            [sink1, sink2],
            parallel=True,
        )
        await write({"message": "test"})

        sink1.write.assert_called_once()
        sink2.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_parallel_fanout_isolates_failures(self):
        """Failure in one sink doesn't block others in parallel mode."""
        from fapilog import _fanout_writer

        sink1 = MagicMock()
        sink1.write = AsyncMock(side_effect=RuntimeError("sink1 failed"))
        sink2 = MagicMock()
        sink2.write = AsyncMock()

        write, _ = _fanout_writer([sink1, sink2], parallel=True)

        # Should not raise, and sink2 should still be called
        await write({"message": "test"})

        sink1.write.assert_called_once()
        sink2.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_skips_open_sink(self):
        """Open circuit skips writes to that sink."""
        from fapilog import _fanout_writer
        from fapilog.core.circuit_breaker import SinkCircuitBreakerConfig

        sink1 = MagicMock()
        sink1.name = "sink1"
        sink1.write = AsyncMock(side_effect=RuntimeError("always fails"))
        sink2 = MagicMock()
        sink2.name = "sink2"
        sink2.write = AsyncMock()

        config = SinkCircuitBreakerConfig(failure_threshold=2)
        write, _ = _fanout_writer([sink1, sink2], circuit_config=config)

        # First two calls - circuit still closed, will try sink1
        await write({"message": "test1"})
        await write({"message": "test2"})

        # Circuit for sink1 should now be open
        # Third call should skip sink1
        sink1.write.reset_mock()
        sink2.write.reset_mock()
        await write({"message": "test3"})

        # sink1 should not be called (circuit open)
        sink1.write.assert_not_called()
        # sink2 should be called exactly once for the third write
        sink2.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_disabled_by_default(self):
        """Circuit breaker is disabled when no config provided."""
        from fapilog import _fanout_writer

        sink1 = MagicMock()
        sink1.write = AsyncMock(side_effect=RuntimeError("fails"))

        write, _ = _fanout_writer([sink1])

        # Without circuit breaker, each call tries the sink
        for _ in range(10):
            try:
                await write({"message": "test"})
            except RuntimeError:
                pass

        # All 10 calls should have tried the sink
        assert sink1.write.call_count == 10


# -----------------------------------------------------------------------------
# Tests for Settings Integration
# -----------------------------------------------------------------------------


class TestCircuitBreakerSettings:
    """Tests for circuit breaker settings."""

    def test_settings_have_circuit_breaker_config(self):
        """Settings include sink circuit breaker configuration."""
        from fapilog import Settings

        settings = Settings()

        # Should have sink fault isolation settings
        assert hasattr(settings.core, "sink_circuit_breaker_enabled")
        assert hasattr(settings.core, "sink_circuit_breaker_failure_threshold")
        assert hasattr(settings.core, "sink_circuit_breaker_recovery_timeout_seconds")
        assert hasattr(settings.core, "sink_parallel_writes")

    def test_circuit_breaker_disabled_by_default(self):
        """Circuit breaker is disabled by default."""
        from fapilog import Settings

        settings = Settings()

        assert settings.core.sink_circuit_breaker_enabled is False

    def test_circuit_breaker_configurable_via_env(self, monkeypatch):
        """Circuit breaker can be configured via environment variables."""
        from fapilog import Settings

        monkeypatch.setenv("FAPILOG_CORE__SINK_CIRCUIT_BREAKER_ENABLED", "true")
        monkeypatch.setenv("FAPILOG_CORE__SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "10")
        monkeypatch.setenv(
            "FAPILOG_CORE__SINK_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS", "60.0"
        )
        monkeypatch.setenv("FAPILOG_CORE__SINK_PARALLEL_WRITES", "true")

        settings = Settings()

        assert settings.core.sink_circuit_breaker_enabled is True
        assert settings.core.sink_circuit_breaker_failure_threshold == 10
        assert settings.core.sink_circuit_breaker_recovery_timeout_seconds == 60.0
        assert settings.core.sink_parallel_writes is True


# -----------------------------------------------------------------------------
# Tests for Diagnostics
# -----------------------------------------------------------------------------


class TestCircuitBreakerDiagnostics:
    """Tests for circuit breaker diagnostics."""

    def test_state_change_emits_diagnostic(self):
        """Circuit state changes emit diagnostics."""
        from fapilog.core.circuit_breaker import (
            SinkCircuitBreaker,
            SinkCircuitBreakerConfig,
        )

        config = SinkCircuitBreakerConfig(failure_threshold=1)
        breaker = SinkCircuitBreaker("test_sink", config)

        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            breaker.record_failure()

            # Should have emitted diagnostic about circuit opening
            mock_warn.assert_called()
            call_args = mock_warn.call_args
            assert "circuit" in call_args[0][1].lower() or "open" in str(call_args)


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with logger."""

    @pytest.mark.asyncio
    async def test_logger_uses_circuit_breaker_when_enabled(self, monkeypatch):
        """Logger uses circuit breaker when enabled in settings."""
        from fapilog import Settings, get_async_logger

        monkeypatch.setenv("FAPILOG_CORE__SINK_CIRCUIT_BREAKER_ENABLED", "true")
        monkeypatch.setenv("FAPILOG_CORE__SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "2")

        settings = Settings(plugins__enabled=False)
        logger = await get_async_logger(settings=settings)

        # Logger should be created successfully with circuit breaker
        assert callable(logger.info)

        await logger.drain()

    @pytest.mark.asyncio
    async def test_logger_parallel_writes_when_enabled(self, monkeypatch):
        """Logger uses parallel writes when enabled in settings."""
        from fapilog import Settings, get_async_logger

        monkeypatch.setenv("FAPILOG_CORE__SINK_PARALLEL_WRITES", "true")

        settings = Settings(plugins__enabled=False)
        logger = await get_async_logger(settings=settings)

        assert callable(logger.info)

        await logger.drain()
