from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade
from fapilog.plugins.health import AggregatedHealth, HealthStatus, check_plugin_health
from fapilog.plugins.sinks.mmap_persistence import MemoryMappedPersistence
from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig
from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


class _DummySink:
    name = "dummy"

    async def write(self, entry: dict[str, Any]) -> None:
        return None

    async def health_check(self) -> bool:
        return True


class _FailingSink(_DummySink):
    async def health_check(self) -> bool:
        return False


class _NoHealthCheckPlugin:
    """Plugin without health_check method."""

    name = "no_health"


class _SlowHealthCheckPlugin:
    """Plugin with slow health check that will timeout."""

    name = "slow"

    async def health_check(self) -> bool:
        await asyncio.sleep(10)
        return True


class _ExceptionHealthCheckPlugin:
    """Plugin whose health check raises an exception."""

    name = "exception"

    async def health_check(self) -> bool:
        raise RuntimeError("health check failed")


@pytest.mark.asyncio
async def test_default_health_check_true() -> None:
    sink = _DummySink()
    result = await check_plugin_health(sink, "sink")
    assert result.healthy is True
    assert result.status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_health_check_failure() -> None:
    sink = _FailingSink()
    result = await check_plugin_health(sink, "sink")
    assert result.healthy is False
    assert result.status == HealthStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_plugin_without_health_check_method() -> None:
    """Plugin without health_check returns UNKNOWN status."""
    plugin = _NoHealthCheckPlugin()
    result = await check_plugin_health(plugin, "sink")
    assert result.status == HealthStatus.UNKNOWN
    assert result.name == "no_health"


@pytest.mark.asyncio
async def test_health_check_timeout() -> None:
    """Health check that times out returns UNHEALTHY with error message."""
    plugin = _SlowHealthCheckPlugin()
    result = await check_plugin_health(plugin, "sink", timeout_seconds=0.01)
    assert result.healthy is False
    assert result.status == HealthStatus.UNHEALTHY
    assert result.last_error is not None
    assert "timed out" in result.last_error


@pytest.mark.asyncio
async def test_health_check_exception() -> None:
    """Health check that raises exception returns UNHEALTHY with error."""
    plugin = _ExceptionHealthCheckPlugin()
    result = await check_plugin_health(plugin, "sink")
    assert result.healthy is False
    assert result.status == HealthStatus.UNHEALTHY
    assert result.last_error == "health check failed"


@pytest.mark.asyncio
async def test_stdout_health_check() -> None:
    sink = StdoutJsonSink()
    ok = await sink.health_check()
    assert ok in (True, False)  # should not raise


@pytest.mark.asyncio
async def test_rotating_file_health_check(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(directory=tmp_path)
    sink = RotatingFileSink(cfg)
    await sink.start()
    assert await sink.health_check() is True
    await sink.stop()


@pytest.mark.asyncio
async def test_mmap_persistence_health_check(tmp_path: Path) -> None:
    path = tmp_path / "mmap.dat"
    mm = MemoryMappedPersistence(path)
    await mm.open()
    assert await mm.health_check() is True
    await mm.close()


class _DummyHealthEnricher:
    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def health_check(self) -> bool:
        return True


class _DummyHealthRedactor:
    name = "r"

    async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
        return event

    async def health_check(self) -> bool:
        return True


class _DummyHealthSink:
    async def start(self) -> None:
        return None

    async def write(self, entry: dict[str, Any]) -> None:
        return None

    async def health_check(self) -> bool:
        return True


class _DummyHealthProcessor:
    name = "proc"

    async def process(self, view: memoryview) -> memoryview:
        return view

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_logger_check_health_aggregates() -> None:
    sink = _DummyHealthSink()
    processor = _DummyHealthProcessor()
    logger = SyncLoggerFacade(
        name="h",
        queue_capacity=4,
        batch_max_size=2,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=False,
        sink_write=sink.write,
        enrichers=[_DummyHealthEnricher()],
    )
    logger._sinks = [sink]  # noqa: SLF001
    logger._redactors = [_DummyHealthRedactor()]  # noqa: SLF001
    logger._processors = [processor]  # noqa: SLF001
    health = await logger.check_health()
    assert health.all_healthy is True


@pytest.mark.asyncio
async def test_aggregated_health_helpers() -> None:
    # Build minimal AggregatedHealth to assert property
    from datetime import datetime, timezone

    agg = AggregatedHealth(
        overall_status=HealthStatus.HEALTHY,
        timestamp=datetime.now(timezone.utc),
        plugins=[],
        healthy_count=1,
        unhealthy_count=0,
        degraded_count=0,
    )
    assert agg.all_healthy is True
