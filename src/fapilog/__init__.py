"""
Public entrypoints for Fapilog v3.

Provides zero-config `get_logger()` and `runtime()` per Story #79.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from .core.logger import SyncLoggerFacade
from .core.settings import Settings
from .metrics.metrics import MetricsCollector
from .plugins.sinks.stdout_json import StdoutJsonSink

__all__ = ["get_logger", "runtime", "__version__", "VERSION"]


_GLOBAL_DEFAULTS = Settings()  # evaluate env once for defaults


def get_logger(name: str | None = None) -> SyncLoggerFacade:
    """Return a ready-to-use sync logger facade wired to default pipeline."""
    # Default pipeline: stdout JSON sink
    sink = StdoutJsonSink()

    async def _sink_write(entry: dict) -> None:
        await sink.write(entry)

    cfg = _GLOBAL_DEFAULTS.core
    metrics: MetricsCollector | None = None
    if _GLOBAL_DEFAULTS.core.enable_metrics:
        metrics = MetricsCollector(enabled=True)
    logger = SyncLoggerFacade(
        name=name,
        queue_capacity=cfg.max_queue_size,
        batch_max_size=cfg.batch_max_size,
        batch_timeout_seconds=cfg.batch_timeout_seconds,
        backpressure_wait_ms=cfg.backpressure_wait_ms,
        drop_on_full=cfg.drop_on_full,
        sink_write=_sink_write,
        metrics=metrics,
    )
    logger.start()
    return logger


@contextmanager
def runtime() -> Iterator[SyncLoggerFacade]:
    """Context manager that initializes and drains the default runtime.

    Yields a default logger; on exit, flushes and returns a drain result via
    StopIteration.value for advanced callers.
    """
    logger = get_logger()
    try:
        yield logger
    finally:
        # Flush synchronously by running the async close
        import asyncio

        try:
            _ = asyncio.run(logger.stop_and_drain())
        except RuntimeError:
            # Already inside a running loop; fire-and-forget best-effort
            loop = asyncio.get_event_loop()
            loop.create_task(logger.stop_and_drain())


# Version info for compatibility
__version__ = "3.0.0-alpha.1"
__author__ = "Chris Haste"
__email__ = "chris@haste.dev"
VERSION = __version__
