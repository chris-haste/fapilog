"""
Mock implementations for testing fapilog plugins.

Provides configurable mocks for sinks, enrichers, redactors, and processors.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockSinkConfig:
    """Configuration for mock sink."""

    fail_after: int | None = None  # Fail after N writes
    fail_with: Exception | None = None  # Exception to raise
    latency_seconds: float = 0.0  # Simulated latency
    health_status: bool = True


class MockSink:
    """Mock sink for testing that captures written events.

    Features:
    - Captures all written events for inspection
    - Configurable failure behavior
    - Configurable latency
    - Tracks lifecycle calls
    """

    name = "mock"

    def __init__(self, config: MockSinkConfig | None = None) -> None:
        self._config = config or MockSinkConfig()
        self.events: list[dict[str, Any]] = []
        self.write_count: int = 0
        self.start_called: bool = False
        self.stop_called: bool = False
        self.health_check_count: int = 0

    async def start(self) -> None:
        self.start_called = True

    async def stop(self) -> None:
        self.stop_called = True

    async def write(self, entry: dict[str, Any]) -> None:
        if self._config.latency_seconds > 0:
            await asyncio.sleep(self._config.latency_seconds)

        self.write_count += 1

        if self._config.fail_after is not None:
            if self.write_count > self._config.fail_after:
                raise self._config.fail_with or RuntimeError("Mock failure")

        self.events.append(entry.copy())

    async def health_check(self) -> bool:
        self.health_check_count += 1
        return self._config.health_status

    def reset(self) -> None:
        """Reset state for reuse in multiple tests."""
        self.events.clear()
        self.write_count = 0
        self.start_called = False
        self.stop_called = False
        self.health_check_count = 0

    def assert_event_count(self, expected: int) -> None:
        """Assert number of events written."""
        assert len(self.events) == expected, (
            f"Expected {expected} events, got {len(self.events)}"
        )

    def assert_event_contains(self, index: int, **kwargs: Any) -> None:
        """Assert event at index contains specified fields."""
        if index >= len(self.events):
            raise AssertionError(f"No event at index {index}")

        event = self.events[index]
        for key, value in kwargs.items():
            assert key in event, f"Event missing field: {key}"
            assert event[key] == value, (
                f"Event[{key}] expected {value!r}, got {event[key]!r}"
            )


@dataclass
class MockEnricherConfig:
    """Configuration for mock enricher."""

    fields_to_add: dict[str, Any] = field(default_factory=dict)
    fail_on_call: int | None = None  # Fail on Nth call
    latency_seconds: float = 0.0


class MockEnricher:
    """Mock enricher for testing that adds configurable fields.

    Features:
    - Adds configured fields to events
    - Tracks all enriched events
    - Configurable failure behavior
    """

    name = "mock"

    def __init__(self, config: MockEnricherConfig | None = None) -> None:
        self._config = config or MockEnricherConfig()
        self.enriched_events: list[dict[str, Any]] = []
        self.call_count: int = 0
        self.start_called: bool = False
        self.stop_called: bool = False

    async def start(self) -> None:
        self.start_called = True

    async def stop(self) -> None:
        self.stop_called = True

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1

        if self._config.fail_on_call is not None:
            if self.call_count == self._config.fail_on_call:
                raise RuntimeError("Mock enricher failure")

        if self._config.latency_seconds > 0:
            await asyncio.sleep(self._config.latency_seconds)

        self.enriched_events.append(event.copy())
        return self._config.fields_to_add.copy()

    async def health_check(self) -> bool:
        return True

    def reset(self) -> None:
        self.enriched_events.clear()
        self.call_count = 0
        self.start_called = False
        self.stop_called = False


@dataclass
class MockRedactorConfig:
    """Configuration for mock redactor."""

    fields_to_mask: list[str] = field(default_factory=list)
    mask_string: str = "***MOCK***"


class MockRedactor:
    """Mock redactor for testing that masks configured fields."""

    name = "mock"

    def __init__(self, config: MockRedactorConfig | None = None) -> None:
        self._config = config or MockRedactorConfig()
        self.redacted_events: list[dict[str, Any]] = []
        self.call_count: int = 0

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        result: dict[str, Any] = self._deep_copy_dict(event)

        for field_path in self._config.fields_to_mask:
            self._mask_field(result, field_path.split("."))

        self.redacted_events.append(result)
        return result

    def _deep_copy_dict(self, obj: dict[str, Any]) -> dict[str, Any]:
        """Deep copy a dict structure."""
        return {k: self._deep_copy_value(v) for k, v in obj.items()}

    def _deep_copy_value(self, obj: Any) -> Any:
        """Deep copy a value (dict/list or primitive)."""
        if isinstance(obj, dict):
            return {k: self._deep_copy_value(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy_value(item) for item in obj]
        return obj

    def _mask_field(self, obj: dict[str, Any], path: list[str]) -> None:
        if not path:
            return

        key = path[0]
        if len(path) == 1:
            if key in obj:
                obj[key] = self._config.mask_string
        else:
            if key in obj and isinstance(obj[key], dict):
                self._mask_field(obj[key], path[1:])

    async def health_check(self) -> bool:
        return True


class MockProcessor:
    """Mock processor for testing."""

    name = "mock"

    def __init__(self) -> None:
        self.processed_views: list[memoryview] = []
        self.call_count: int = 0

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def process(self, view: memoryview) -> memoryview:
        self.call_count += 1
        self.processed_views.append(view)
        return view

    async def health_check(self) -> bool:
        return True


@dataclass
class MockFilterConfig:
    """Configuration for mock filter."""

    drop_levels: list[str] = field(default_factory=list)
    drop_rate: float = 0.0
    fail_on_call: int | None = None
    latency_seconds: float = 0.0


class MockFilter:
    """Mock filter for testing filter chains."""

    name = "mock"

    def __init__(self, config: MockFilterConfig | None = None) -> None:
        self._config = config or MockFilterConfig()
        self.filtered_events: list[dict[str, Any]] = []
        self.dropped_events: list[dict[str, Any]] = []
        self.call_count: int = 0
        self.start_called: bool = False
        self.stop_called: bool = False

    async def start(self) -> None:
        self.start_called = True

    async def stop(self) -> None:
        self.stop_called = True

    async def filter(self, event: dict[str, Any]) -> dict[str, Any] | None:
        self.call_count += 1

        if self._config.fail_on_call is not None:
            if self.call_count == self._config.fail_on_call:
                raise RuntimeError("Mock filter failure")

        if self._config.latency_seconds > 0:
            await asyncio.sleep(self._config.latency_seconds)

        level = str(event.get("level", "")).upper()
        drop_levels = {lvl.upper() for lvl in self._config.drop_levels}
        if level in drop_levels:
            self.dropped_events.append(event.copy())
            return None

        if self._config.drop_rate > 0:
            import random

            if random.random() < self._config.drop_rate:
                self.dropped_events.append(event.copy())
                return None

        self.filtered_events.append(event.copy())
        return event

    async def health_check(self) -> bool:
        return True

    def reset(self) -> None:
        self.filtered_events.clear()
        self.dropped_events.clear()
        self.call_count = 0
        self.start_called = False
        self.stop_called = False


# Mark as used for static analysis (public API used by tests)
_VULTURE_USED: tuple[object, ...] = (
    MockSink,
    MockSink.reset,
    MockSink.assert_event_count,
    MockSink.assert_event_contains,
    MockSinkConfig,
    MockEnricher,
    MockEnricher.reset,
    MockEnricherConfig,
    MockRedactor,
    MockRedactorConfig,
    MockProcessor,
    MockFilter,
    MockFilter.reset,
    MockFilterConfig,
)
