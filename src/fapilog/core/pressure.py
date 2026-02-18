"""Pressure monitoring and escalation state machine for adaptive pipeline.

Story 1.44: Foundation for adaptive burst handling. Provides:
- PressureLevel: Four-level pressure enum
- EscalationStateMachine: Hysteresis-based level computation with cooldown
- PressureMonitor: Asyncio task that samples queue metrics and dispatches callbacks
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .logger import AdaptiveDrainSummary


class PressureLevel(str, Enum):
    """Four-level pressure classification for adaptive pipeline."""

    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


# Ordered list for index-based level arithmetic
_LEVELS = [
    PressureLevel.NORMAL,
    PressureLevel.ELEVATED,
    PressureLevel.HIGH,
    PressureLevel.CRITICAL,
]


class EscalationStateMachine:
    """Compute pressure level from fill ratio with hysteresis and cooldown.

    - Escalation and de-escalation use different thresholds to prevent oscillation.
    - Only one level change per evaluate() call.
    - Cooldown enforces minimum time between transitions.
    """

    def __init__(
        self,
        *,
        cooldown_seconds: float = 2.0,
        escalate_to_elevated: float = 0.60,
        escalate_to_high: float = 0.80,
        escalate_to_critical: float = 0.92,
        deescalate_from_critical: float = 0.75,
        deescalate_from_high: float = 0.60,
        deescalate_from_elevated: float = 0.40,
    ) -> None:
        self._level = PressureLevel.NORMAL
        self._cooldown = cooldown_seconds
        self._last_transition_time: float = 0.0
        self._first_evaluation = True

        # Escalation thresholds (fill >= threshold triggers escalation)
        self._escalation: dict[PressureLevel, float] = {
            PressureLevel.ELEVATED: escalate_to_elevated,
            PressureLevel.HIGH: escalate_to_high,
            PressureLevel.CRITICAL: escalate_to_critical,
        }

        # De-escalation thresholds (fill < threshold triggers de-escalation)
        self._deescalation: dict[PressureLevel, float] = {
            PressureLevel.HIGH: deescalate_from_critical,
            PressureLevel.ELEVATED: deescalate_from_high,
            PressureLevel.NORMAL: deescalate_from_elevated,
        }

    @property
    def current_level(self) -> PressureLevel:
        return self._level

    def evaluate(self, fill_ratio: float) -> PressureLevel:
        """Evaluate fill ratio and return (possibly updated) pressure level.

        At most one level change per call. Cooldown blocks transitions
        if insufficient time has passed since the last transition.
        """
        now = time.monotonic()

        # Check cooldown (first evaluation always allowed)
        if (
            not self._first_evaluation
            and (now - self._last_transition_time) < self._cooldown
        ):
            return self._level

        idx = _LEVELS.index(self._level)

        # Check escalation (one step up)
        if idx < len(_LEVELS) - 1:
            next_level = _LEVELS[idx + 1]
            threshold = self._escalation.get(next_level)
            if threshold is not None and fill_ratio >= threshold:
                self._level = next_level
                self._last_transition_time = now
                self._first_evaluation = False
                return self._level

        # Check de-escalation (one step down)
        if idx > 0:
            prev_level = _LEVELS[idx - 1]
            threshold = self._deescalation.get(prev_level)
            if threshold is not None and fill_ratio < threshold:
                self._level = prev_level
                self._last_transition_time = now
                self._first_evaluation = False
                return self._level

        return self._level


# Type alias for pressure change callbacks
PressureCallback = Callable[[PressureLevel, PressureLevel], None]

# Type alias for diagnostic writer
DiagnosticWriter = Callable[[dict[str, Any]], None]

# Type alias for metric setter (sets gauge value)
MetricSetter = Callable[[int], None]

# Type alias for depth gauge setter (queue_label, depth)
DepthGaugeSetter = Callable[[str, int], None]


class PressureMonitor:
    """Asyncio task that samples queue fill ratio and dispatches pressure changes.

    Runs alongside workers in the event loop, sampling at configurable intervals.
    Callbacks are invoked synchronously within the monitor's asyncio task.
    """

    def __init__(
        self,
        *,
        queue: Any,
        check_interval_seconds: float = 0.25,
        cooldown_seconds: float = 2.0,
        escalate_to_elevated: float = 0.60,
        escalate_to_high: float = 0.80,
        escalate_to_critical: float = 0.92,
        deescalate_from_critical: float = 0.75,
        deescalate_from_high: float = 0.60,
        deescalate_from_elevated: float = 0.40,
        diagnostic_writer: DiagnosticWriter | None = None,
        metric_setter: MetricSetter | None = None,
        circuit_pressure_boost: float = 0.20,
        depth_gauge_setter: DepthGaugeSetter | None = None,
    ) -> None:
        self._queue = queue
        self._check_interval = check_interval_seconds
        self._state_machine = EscalationStateMachine(
            cooldown_seconds=cooldown_seconds,
            escalate_to_elevated=escalate_to_elevated,
            escalate_to_high=escalate_to_high,
            escalate_to_critical=escalate_to_critical,
            deescalate_from_critical=deescalate_from_critical,
            deescalate_from_high=deescalate_from_high,
            deescalate_from_elevated=deescalate_from_elevated,
        )
        self._callbacks: list[PressureCallback] = []
        self._diagnostic_writer = diagnostic_writer
        self._metric_setter = metric_setter
        self._depth_gauge_setter = depth_gauge_setter
        self._stopped = False
        self._circuit_boost: float = 0.0
        self._circuit_boost_per_open: float = circuit_pressure_boost
        # Adaptive summary counters (Story 10.58)
        self._escalation_count = 0
        self._deescalation_count = 0
        self._peak_level = PressureLevel.NORMAL
        self._level_entered_at: float = time.monotonic()
        self._time_at_level: dict[PressureLevel, float] = dict.fromkeys(
            PressureLevel, 0.0
        )
        # Actuator counters (incremented by callbacks)
        self._filters_swapped = 0
        self._workers_scaled = 0
        self._peak_workers: int = 0
        self._batch_resize_count = 0

    @property
    def pressure_level(self) -> PressureLevel:
        return self._state_machine.current_level

    def on_level_change(self, callback: PressureCallback) -> None:
        """Register a callback invoked on pressure level changes."""
        self._callbacks.append(callback)

    def on_circuit_state_change(self, sink_name: str, new_state: object) -> None:
        """Adjust circuit pressure boost when a sink circuit changes state.

        Called by SinkCircuitBreaker.on_state_change callback.
        OPEN adds boost, CLOSED removes it.
        """
        # Import locally to avoid circular dependency at module level
        from .circuit_breaker import CircuitState

        if new_state == CircuitState.OPEN:
            self._circuit_boost += self._circuit_boost_per_open
        elif new_state == CircuitState.CLOSED:
            self._circuit_boost = max(
                0.0, self._circuit_boost - self._circuit_boost_per_open
            )

    def stop(self) -> None:
        """Signal the monitor to stop after the current tick."""
        self._stopped = True

    async def run(self) -> None:
        """Main monitor loop. Runs until stop() is called."""
        while not self._stopped:
            self._tick()
            await asyncio.sleep(self._check_interval)

    def _tick(self) -> None:
        """Single evaluation cycle: sample, evaluate, dispatch."""
        capacity = self._queue.capacity
        if capacity <= 0:
            return
        # Use main_qsize() for DualQueue (Story 1.52) — protected queue
        # depth is a separate signal, not part of adaptive pressure.
        from .concurrency import DualQueue

        if isinstance(self._queue, DualQueue):
            depth = self._queue.main_qsize()
            self._set_depth_gauges(depth, self._queue.protected_qsize())
        else:
            depth = self._queue.qsize()
        raw_fill = depth / capacity
        fill_ratio = min(1.0, raw_fill + self._circuit_boost)

        old_level = self._state_machine.current_level
        new_level = self._state_machine.evaluate(fill_ratio)

        if new_level != old_level:
            # Accumulate time at old level (Story 10.58)
            now = time.monotonic()
            self._time_at_level[old_level] += now - self._level_entered_at
            self._level_entered_at = now
            # Count direction
            if _LEVELS.index(new_level) > _LEVELS.index(old_level):
                self._escalation_count += 1
            else:
                self._deescalation_count += 1
            # Track peak
            if _LEVELS.index(new_level) > _LEVELS.index(self._peak_level):
                self._peak_level = new_level

            self._emit_diagnostic(old_level, new_level, fill_ratio)
            self._update_metric(new_level)
            self._dispatch_callbacks(old_level, new_level)

    def _set_depth_gauges(self, main_depth: int, protected_depth: int) -> None:
        """Report queue depths to gauge setter if configured."""
        if self._depth_gauge_setter is None:
            return
        try:
            self._depth_gauge_setter("main", main_depth)
            self._depth_gauge_setter("protected", protected_depth)
        except Exception:
            pass

    def _emit_diagnostic(
        self,
        old_level: PressureLevel,
        new_level: PressureLevel,
        fill_ratio: float,
    ) -> None:
        if self._diagnostic_writer is None:
            return
        try:
            self._diagnostic_writer(
                {
                    "component": "adaptive-controller",
                    "message": "pressure level changed",
                    "from_level": old_level.value,
                    "to_level": new_level.value,
                    "fill_ratio": round(fill_ratio, 4),
                }
            )
        except Exception:
            pass

    def _update_metric(self, level: PressureLevel) -> None:
        if self._metric_setter is None:
            return
        try:
            self._metric_setter(_LEVELS.index(level))
        except Exception:
            pass

    def _dispatch_callbacks(
        self, old_level: PressureLevel, new_level: PressureLevel
    ) -> None:
        for cb in self._callbacks:
            try:
                cb(old_level, new_level)
            except Exception:
                pass

    # -- Actuator counter methods (Story 10.58) --

    def record_filter_swap(self) -> None:
        """Increment filter swap counter."""
        self._filters_swapped += 1

    def record_worker_scaling(self, count: int) -> None:
        """Record a worker scaling event and track peak."""
        self._workers_scaled += 1
        if count > self._peak_workers:
            self._peak_workers = count

    def record_batch_resize(self) -> None:
        """Increment batch resize counter."""
        self._batch_resize_count += 1

    def snapshot(self) -> AdaptiveDrainSummary:
        """Capture current adaptive summary. Call before teardown."""
        from .logger import AdaptiveDrainSummary

        # Finalize time-at-level for current level
        now = time.monotonic()
        time_at_level = dict(self._time_at_level)
        time_at_level[self._state_machine.current_level] += now - self._level_entered_at
        return AdaptiveDrainSummary(
            peak_pressure_level=self._peak_level,
            escalation_count=self._escalation_count,
            deescalation_count=self._deescalation_count,
            time_at_level=time_at_level,
            filters_swapped=self._filters_swapped,
            workers_scaled=self._workers_scaled,
            peak_workers=self._peak_workers,
            batch_resize_count=self._batch_resize_count,
        )


# Mark public API for vulture (Story 1.44, 4.73, 10.58)
_VULTURE_USED: tuple[object, ...] = (
    PressureMonitor.pressure_level,
    PressureMonitor.on_level_change,
    PressureMonitor.on_circuit_state_change,
    PressureMonitor.stop,
    PressureMonitor.run,
    PressureMonitor.record_filter_swap,
    PressureMonitor.record_worker_scaling,
    PressureMonitor.record_batch_resize,
    PressureMonitor.snapshot,
    MetricSetter,
    DepthGaugeSetter,
    DiagnosticWriter,
    PressureCallback,
)
