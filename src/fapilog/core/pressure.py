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
from typing import Any


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
        self._stopped = False

    @property
    def pressure_level(self) -> PressureLevel:
        return self._state_machine.current_level

    def on_level_change(self, callback: PressureCallback) -> None:
        """Register a callback invoked on pressure level changes."""
        self._callbacks.append(callback)

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
        fill_ratio = self._queue.qsize() / capacity

        old_level = self._state_machine.current_level
        new_level = self._state_machine.evaluate(fill_ratio)

        if new_level != old_level:
            self._emit_diagnostic(old_level, new_level, fill_ratio)
            self._update_metric(new_level)
            self._dispatch_callbacks(old_level, new_level)

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


# Mark public API for vulture (Story 1.44)
_VULTURE_USED: tuple[object, ...] = (
    PressureMonitor.pressure_level,
    PressureMonitor.on_level_change,
    PressureMonitor.stop,
    PressureMonitor.run,
    MetricSetter,
    DiagnosticWriter,
    PressureCallback,
)
