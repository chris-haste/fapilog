"""
Tests for plugin lifecycle management (Story 4.34).

Verifies that enrichers and redactors have their start() and stop()
lifecycle methods called during logger initialization and shutdown.
"""

from __future__ import annotations

import pytest

from fapilog import Settings, get_async_logger, get_logger
from fapilog.plugins.enrichers import BaseEnricher
from fapilog.plugins.processors import BaseProcessor
from fapilog.plugins.redactors import BaseRedactor


class TrackingEnricher(BaseEnricher):
    """Test enricher that tracks lifecycle calls."""

    name = "tracking_enricher"

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.start_called_count = 0
        self.stop_called_count = 0

    async def start(self) -> None:
        self.started = True
        self.start_called_count += 1

    async def stop(self) -> None:
        self.stopped = True
        self.stop_called_count += 1

    async def enrich(self, event: dict) -> dict:
        return {"enriched_by": self.name}


class TrackingRedactor(BaseRedactor):
    """Test redactor that tracks lifecycle calls."""

    name = "tracking_redactor"

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.start_called_count = 0
        self.stop_called_count = 0

    async def start(self) -> None:
        self.started = True
        self.start_called_count += 1

    async def stop(self) -> None:
        self.stopped = True
        self.stop_called_count += 1

    async def redact(self, event: dict) -> dict:
        return event


class TrackingProcessor(BaseProcessor):
    """Test processor that tracks lifecycle calls."""

    name = "tracking_processor"

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.start_called_count = 0
        self.stop_called_count = 0

    async def start(self) -> None:
        self.started = True
        self.start_called_count += 1

    async def stop(self) -> None:
        self.stopped = True
        self.stop_called_count += 1

    async def process(self, view: memoryview) -> memoryview:
        return view


class FailingStartEnricher(BaseEnricher):
    """Enricher that fails on start."""

    name = "failing_start_enricher"

    async def start(self) -> None:
        raise RuntimeError("start failed intentionally")

    async def enrich(self, event: dict) -> dict:
        return {}


class FailingStartRedactor(BaseRedactor):
    """Redactor that fails on start."""

    name = "failing_start_redactor"

    async def start(self) -> None:
        raise RuntimeError("start failed intentionally")

    async def redact(self, event: dict) -> dict:
        return event


class FailingStopEnricher(BaseEnricher):
    """Enricher that fails on stop."""

    name = "failing_stop_enricher"

    def __init__(self) -> None:
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        raise RuntimeError("stop failed intentionally")

    async def enrich(self, event: dict) -> dict:
        return {}


class FailingStopRedactor(BaseRedactor):
    """Redactor that fails on stop."""

    name = "failing_stop_redactor"

    def __init__(self) -> None:
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        raise RuntimeError("stop failed intentionally")

    async def redact(self, event: dict) -> dict:
        return event


class NoLifecycleEnricher(BaseEnricher):
    """Enricher without lifecycle methods (backward compatibility)."""

    name = "no_lifecycle_enricher"

    async def enrich(self, event: dict) -> dict:
        return {"no_lifecycle": True}


class NoLifecycleRedactor(BaseRedactor):
    """Redactor without lifecycle methods (backward compatibility)."""

    name = "no_lifecycle_redactor"

    async def redact(self, event: dict) -> dict:
        return event


# -----------------------------------------------------------------------------
# Tests for _start_plugins helper
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_plugins_calls_start_on_enrichers():
    """_start_plugins should call start() on plugins that have it."""
    from fapilog import _start_plugins

    enricher = TrackingEnricher()
    assert not enricher.started

    result = await _start_plugins([enricher], "enricher")

    assert enricher.started
    assert enricher.start_called_count == 1
    assert enricher in result


@pytest.mark.asyncio
async def test_start_plugins_calls_start_on_redactors():
    """_start_plugins should call start() on redactors."""
    from fapilog import _start_plugins

    redactor = TrackingRedactor()
    assert not redactor.started

    result = await _start_plugins([redactor], "redactor")

    assert redactor.started
    assert redactor.start_called_count == 1
    assert redactor in result


@pytest.mark.asyncio
async def test_start_plugins_excludes_failed_plugins():
    """Failed start() should exclude plugin from returned list."""
    from fapilog import _start_plugins

    failing = FailingStartEnricher()
    working = TrackingEnricher()

    result = await _start_plugins([failing, working], "enricher")

    assert failing not in result
    assert working in result
    assert working.started


@pytest.mark.asyncio
async def test_start_plugins_handles_no_lifecycle_methods():
    """Plugins without start() should still be included."""
    from fapilog import _start_plugins

    enricher = NoLifecycleEnricher()

    result = await _start_plugins([enricher], "enricher")

    assert enricher in result


# -----------------------------------------------------------------------------
# Tests for _stop_plugins helper
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_plugins_calls_stop_on_enrichers():
    """_stop_plugins should call stop() on plugins."""
    from fapilog import _stop_plugins

    enricher = TrackingEnricher()
    enricher.started = True

    await _stop_plugins([enricher], "enricher")

    assert enricher.stopped
    assert enricher.stop_called_count == 1


@pytest.mark.asyncio
async def test_stop_plugins_calls_stop_on_redactors():
    """_stop_plugins should call stop() on redactors."""
    from fapilog import _stop_plugins

    redactor = TrackingRedactor()
    redactor.started = True

    await _stop_plugins([redactor], "redactor")

    assert redactor.stopped
    assert redactor.stop_called_count == 1


@pytest.mark.asyncio
async def test_stop_plugins_continues_on_failure():
    """Failed stop() should not prevent other plugins from stopping."""
    from fapilog import _stop_plugins

    failing = FailingStopEnricher()
    failing.started = True
    working = TrackingEnricher()
    working.started = True

    # Should not raise, should continue with other plugins
    await _stop_plugins([failing, working], "enricher")

    assert working.stopped


@pytest.mark.asyncio
async def test_stop_plugins_calls_in_reverse_order():
    """_stop_plugins should call stop() in reverse order."""
    from fapilog import _stop_plugins

    stop_order: list[str] = []

    class OrderedEnricher(BaseEnricher):
        name = "ordered"

        def __init__(self, order_id: str) -> None:
            self.order_id = order_id

        async def stop(self) -> None:
            stop_order.append(self.order_id)

        async def enrich(self, event: dict) -> dict:
            return {}

    e1 = OrderedEnricher("first")
    e2 = OrderedEnricher("second")
    e3 = OrderedEnricher("third")

    await _stop_plugins([e1, e2, e3], "enricher")

    assert stop_order == ["third", "second", "first"]


@pytest.mark.asyncio
async def test_stop_plugins_handles_no_lifecycle_methods():
    """Plugins without stop() should be handled gracefully."""
    from fapilog import _stop_plugins

    enricher = NoLifecycleEnricher()

    # Should not raise
    await _stop_plugins([enricher], "enricher")


# -----------------------------------------------------------------------------
# Tests for get_async_logger lifecycle integration
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_logger_starts_enrichers(monkeypatch):
    """get_async_logger should call start() on enrichers."""
    enricher = TrackingEnricher()

    # Patch _build_pipeline to return our test enricher
    def mock_build_pipeline(settings):
        return [], [enricher], [], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))
    assert enricher.started

    await logger.drain()


@pytest.mark.asyncio
async def test_async_logger_starts_redactors(monkeypatch):
    """get_async_logger should call start() on redactors."""
    redactor = TrackingRedactor()

    def mock_build_pipeline(settings):
        return [], [], [redactor], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))
    assert redactor.started

    await logger.drain()


@pytest.mark.asyncio
async def test_async_logger_starts_processors(monkeypatch):
    """get_async_logger should call start() on processors."""
    processor = TrackingProcessor()

    def mock_build_pipeline(settings):
        return [], [], [], [processor], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))
    assert processor.started

    await logger.drain()


@pytest.mark.asyncio
async def test_async_logger_excludes_failed_enrichers(monkeypatch):
    """Failed enricher start should exclude it from active list."""
    failing = FailingStartEnricher()
    working = TrackingEnricher()

    def mock_build_pipeline(settings):
        return [], [failing, working], [], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))

    # Failing enricher should not be in the logger's enricher list
    assert failing not in logger._enrichers
    assert working in logger._enrichers

    await logger.drain()


@pytest.mark.asyncio
async def test_async_logger_stops_enrichers_on_drain(monkeypatch):
    """drain() should call stop() on enrichers."""
    enricher = TrackingEnricher()

    def mock_build_pipeline(settings):
        return [], [enricher], [], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))
    assert enricher.started
    assert not enricher.stopped

    await logger.drain()

    assert enricher.stopped


@pytest.mark.asyncio
async def test_async_logger_stops_redactors_on_drain(monkeypatch):
    """drain() should call stop() on redactors."""
    redactor = TrackingRedactor()

    def mock_build_pipeline(settings):
        return [], [], [redactor], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))
    assert redactor.started
    assert not redactor.stopped

    await logger.drain()

    assert redactor.stopped


@pytest.mark.asyncio
async def test_async_logger_stops_processors_on_drain(monkeypatch):
    """drain() should call stop() on processors."""
    processor = TrackingProcessor()

    def mock_build_pipeline(settings):
        return [], [], [], [processor], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))
    assert processor.started
    assert not processor.stopped

    await logger.drain()

    assert processor.stopped


# -----------------------------------------------------------------------------
# Tests for sync logger lifecycle integration
# -----------------------------------------------------------------------------


def test_sync_logger_starts_enrichers(monkeypatch):
    """get_logger should call start() on enrichers."""
    import asyncio

    enricher = TrackingEnricher()

    def mock_build_pipeline(settings):
        return [], [enricher], [], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = get_logger(settings=Settings(plugins__enabled=False))
    assert enricher.started

    asyncio.run(logger.stop_and_drain())


def test_sync_logger_starts_redactors(monkeypatch):
    """get_logger should call start() on redactors."""
    import asyncio

    redactor = TrackingRedactor()

    def mock_build_pipeline(settings):
        return [], [], [redactor], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = get_logger(settings=Settings(plugins__enabled=False))
    assert redactor.started

    asyncio.run(logger.stop_and_drain())


def test_sync_logger_starts_processors(monkeypatch):
    """get_logger should call start() on processors."""
    import asyncio

    processor = TrackingProcessor()

    def mock_build_pipeline(settings):
        return [], [], [], [processor], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = get_logger(settings=Settings(plugins__enabled=False))
    assert processor.started

    asyncio.run(logger.stop_and_drain())


def test_sync_logger_excludes_failed_enrichers(monkeypatch):
    """Failed enricher start should exclude it from active list in sync logger."""
    import asyncio

    failing = FailingStartEnricher()
    working = TrackingEnricher()

    def mock_build_pipeline(settings):
        return [], [failing, working], [], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = get_logger(settings=Settings(plugins__enabled=False))

    assert failing not in logger._enrichers
    assert working in logger._enrichers

    asyncio.run(logger.stop_and_drain())


def test_sync_logger_stops_enrichers_on_drain(monkeypatch):
    """stop_and_drain() should call stop() on enrichers for sync logger."""
    import asyncio

    enricher = TrackingEnricher()

    def mock_build_pipeline(settings):
        return [], [enricher], [], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = get_logger(settings=Settings(plugins__enabled=False))
    assert enricher.started
    assert not enricher.stopped

    asyncio.run(logger.stop_and_drain())

    assert enricher.stopped


def test_sync_logger_stops_processors_on_drain(monkeypatch):
    """stop_and_drain() should call stop() on processors for sync logger."""
    import asyncio

    processor = TrackingProcessor()

    def mock_build_pipeline(settings):
        return [], [], [], [processor], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = get_logger(settings=Settings(plugins__enabled=False))
    assert processor.started
    assert not processor.stopped

    asyncio.run(logger.stop_and_drain())

    assert processor.stopped


# -----------------------------------------------------------------------------
# Tests for error containment
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_failure_does_not_prevent_other_stops(monkeypatch):
    """Failed stop() should not prevent other plugins from being stopped."""
    failing = FailingStopEnricher()
    working = TrackingEnricher()

    def mock_build_pipeline(settings):
        return [], [failing, working], [], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))

    # Both should have been started
    assert failing.started
    assert working.started

    # Drain should not raise even though failing.stop() raises
    await logger.drain()

    # Working enricher should still have been stopped
    assert working.stopped


# -----------------------------------------------------------------------------
# Tests for backward compatibility
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enricher_without_lifecycle_still_works(monkeypatch):
    """Enrichers without start/stop should work normally."""
    enricher = NoLifecycleEnricher()

    def mock_build_pipeline(settings):
        return [], [enricher], [], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))

    # Should be in the enricher list
    assert enricher in logger._enrichers

    # Should not raise on drain
    await logger.drain()


@pytest.mark.asyncio
async def test_redactor_without_lifecycle_still_works(monkeypatch):
    """Redactors without start/stop should work normally."""
    redactor = NoLifecycleRedactor()

    def mock_build_pipeline(settings):
        return [], [], [redactor], [], [], None

    monkeypatch.setattr("fapilog._build_pipeline", mock_build_pipeline)

    logger = await get_async_logger(settings=Settings(plugins__enabled=False))

    # Should be in the redactor list
    assert redactor in logger._redactors

    # Should not raise on drain
    await logger.drain()
