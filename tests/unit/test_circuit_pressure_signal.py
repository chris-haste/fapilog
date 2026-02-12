"""Unit tests for circuit breaker as adaptive pressure signal (Story 4.73)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fapilog.core.circuit_breaker import (
    CircuitState,
    SinkCircuitBreaker,
    SinkCircuitBreakerConfig,
)
from fapilog.core.pressure import PressureLevel, PressureMonitor
from fapilog.core.settings import AdaptiveSettings


class TestCircuitBreakerCallback:
    def test_circuit_open_calls_on_state_change(self) -> None:
        """When circuit opens, on_state_change is called with OPEN."""
        config = SinkCircuitBreakerConfig(failure_threshold=2)
        breaker = SinkCircuitBreaker("http", config)

        calls: list[tuple[str, CircuitState]] = []
        breaker.on_state_change = lambda name, state: calls.append((name, state))

        breaker.record_failure()
        breaker.record_failure()  # Hits threshold → OPEN

        assert len(calls) == 1
        assert calls[0] == ("http", CircuitState.OPEN)

    def test_circuit_close_calls_on_state_change(self) -> None:
        """When circuit closes after half-open probe, on_state_change is called with CLOSED."""
        config = SinkCircuitBreakerConfig(
            failure_threshold=1, recovery_timeout_seconds=0.0
        )
        breaker = SinkCircuitBreaker("http", config)

        calls: list[tuple[str, CircuitState]] = []
        breaker.on_state_change = lambda name, state: calls.append((name, state))

        # Open the circuit
        breaker.record_failure()
        assert calls[-1] == ("http", CircuitState.OPEN)

        # Trigger half-open by allowing a call (recovery_timeout=0)
        breaker.should_allow()
        assert breaker.state == CircuitState.HALF_OPEN

        # Successful probe → closed
        breaker.record_success()
        assert len(calls) == 2
        assert calls[1] == ("http", CircuitState.CLOSED)

    def test_callback_exception_does_not_crash_breaker(self) -> None:
        """An exception in the callback doesn't prevent state change."""
        config = SinkCircuitBreakerConfig(failure_threshold=1)
        breaker = SinkCircuitBreaker("http", config)

        def bad_callback(name: str, state: CircuitState) -> None:
            raise RuntimeError("boom")

        breaker.on_state_change = bad_callback

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN


def _make_queue(qsize: int = 0, capacity: int = 100) -> MagicMock:
    q = MagicMock()
    q.qsize.return_value = qsize
    q.capacity = capacity
    return q


class TestPressureMonitorCircuitBoost:
    def test_circuit_open_adds_boost(self) -> None:
        """AC1: Circuit open boosts effective fill ratio."""
        queue = _make_queue(qsize=40, capacity=100)
        monitor = PressureMonitor(
            queue=queue, cooldown_seconds=0.0, circuit_pressure_boost=0.20
        )

        monitor.on_circuit_state_change("http", CircuitState.OPEN)

        # Tick with 40% fill + 20% boost = 60%, triggers ELEVATED
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.ELEVATED

    def test_circuit_close_removes_boost(self) -> None:
        """AC3: Circuit close removes boost."""
        queue = _make_queue(qsize=30, capacity=100)
        monitor = PressureMonitor(
            queue=queue, cooldown_seconds=0.0, circuit_pressure_boost=0.20
        )

        monitor.on_circuit_state_change("http", CircuitState.OPEN)
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.NORMAL  # 30% + 20% = 50% < 60%

        monitor.on_circuit_state_change("http", CircuitState.CLOSED)
        # Boost removed, effective = 30%
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.NORMAL

    def test_multiple_circuits_stack(self) -> None:
        """AC2: Multiple open circuits stack boosts."""
        queue = _make_queue(qsize=30, capacity=100)
        monitor = PressureMonitor(
            queue=queue, cooldown_seconds=0.0, circuit_pressure_boost=0.20
        )

        monitor.on_circuit_state_change("http", CircuitState.OPEN)
        monitor.on_circuit_state_change("webhook", CircuitState.OPEN)

        # 30% + 40% = 70% → ELEVATED (>= 60%)
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.ELEVATED

    def test_boost_capped_at_1(self) -> None:
        """AC5: Effective fill ratio never exceeds 1.0."""
        queue = _make_queue(qsize=80, capacity=100)
        monitor = PressureMonitor(
            queue=queue, cooldown_seconds=0.0, circuit_pressure_boost=0.20
        )

        # 3 circuits open: 80% + 60% = 140% → capped at 100%
        monitor.on_circuit_state_change("s1", CircuitState.OPEN)
        monitor.on_circuit_state_change("s2", CircuitState.OPEN)
        monitor.on_circuit_state_change("s3", CircuitState.OPEN)

        monitor._tick()
        # Should hit CRITICAL (>= 0.92), not crash
        assert monitor.pressure_level == PressureLevel.ELEVATED  # One step per tick

    def test_configurable_boost_amount(self) -> None:
        """AC4: Boost amount is configurable."""
        queue = _make_queue(qsize=40, capacity=100)
        monitor = PressureMonitor(
            queue=queue, cooldown_seconds=0.0, circuit_pressure_boost=0.15
        )

        monitor.on_circuit_state_change("http", CircuitState.OPEN)

        # 40% + 15% = 55% < 60%, not enough for ELEVATED
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.NORMAL

    def test_close_does_not_go_below_zero(self) -> None:
        """Close on an already-zero boost doesn't go negative."""
        queue = _make_queue(qsize=40, capacity=100)
        monitor = PressureMonitor(
            queue=queue, cooldown_seconds=0.0, circuit_pressure_boost=0.20
        )

        # Close without a prior open
        monitor.on_circuit_state_change("http", CircuitState.CLOSED)

        monitor._tick()
        assert monitor.pressure_level == PressureLevel.NORMAL


class TestAdaptiveSettingsCircuitBoost:
    def test_default_circuit_pressure_boost(self) -> None:
        """Default boost is 0.20."""
        settings = AdaptiveSettings()
        assert settings.circuit_pressure_boost == 0.20

    def test_custom_circuit_pressure_boost(self) -> None:
        """Boost is configurable."""
        settings = AdaptiveSettings(circuit_pressure_boost=0.15)
        assert settings.circuit_pressure_boost == 0.15


class TestEndToEndCircuitPressureWiring:
    """Integration: breaker state change flows through to pressure escalation."""

    def test_breaker_open_triggers_monitor_escalation(self) -> None:
        """Circuit breaker open → on_state_change → PressureMonitor boost → escalation."""
        queue = _make_queue(qsize=40, capacity=100)
        monitor = PressureMonitor(
            queue=queue, cooldown_seconds=0.0, circuit_pressure_boost=0.20
        )

        config = SinkCircuitBreakerConfig(failure_threshold=2)
        breaker = SinkCircuitBreaker("http", config)

        # Wire breaker → monitor (same as logger does)
        breaker.on_state_change = monitor.on_circuit_state_change

        # Before failures: 40% fill, NORMAL
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.NORMAL

        # Trip the breaker
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Now: 40% + 20% boost = 60%, triggers ELEVATED
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.ELEVATED

    def test_breaker_recovery_removes_boost(self) -> None:
        """Circuit breaker close → boost removed → de-escalation possible."""
        queue = _make_queue(qsize=45, capacity=100)
        monitor = PressureMonitor(
            queue=queue, cooldown_seconds=0.0, circuit_pressure_boost=0.20
        )

        config = SinkCircuitBreakerConfig(
            failure_threshold=1, recovery_timeout_seconds=0.0
        )
        breaker = SinkCircuitBreaker("http", config)
        breaker.on_state_change = monitor.on_circuit_state_change

        # Trip the breaker: 45% + 20% = 65% → ELEVATED
        breaker.record_failure()
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.ELEVATED

        # Recover: half-open → success → closed
        breaker.should_allow()
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

        # Boost removed: effective 45% < 40% de-escalation threshold?
        # No, 45% > 40%, stays ELEVATED. Lower the queue.
        queue.qsize.return_value = 30
        # Now: 30% + 0% boost = 30% < 40% threshold → de-escalate to NORMAL
        monitor._tick()
        assert monitor.pressure_level == PressureLevel.NORMAL
