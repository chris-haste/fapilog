"""
Public entrypoints for Fapilog v3.

Provides zero-config `get_logger()` and `runtime()` per Story #79.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from .core.logger import SyncLoggerFacade as _SyncLoggerFacade
from .core.settings import Settings as _Settings
from .metrics.metrics import MetricsCollector as _MetricsCollector
from .plugins.sinks.stdout_json import StdoutJsonSink as _StdoutJsonSink

__all__ = ["get_logger", "runtime", "__version__", "VERSION"]


def get_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
) -> _SyncLoggerFacade:
    """Return a ready-to-use sync logger facade wired to a
    container-scoped pipeline.

    - Zero-config: if `settings` is not provided, a fresh `Settings()` is
      created (reads env at call time) and treated as immutable for the
      lifetime of the returned logger instance.
    - Container-scoped: no global mutable state is retained; each logger owns
      its own configuration, metrics, and sink wiring.
    """
    # Default pipeline: stdout JSON sink
    sink = _StdoutJsonSink()

    async def _sink_write(entry: dict) -> None:
        await sink.write(entry)

    cfg_source = settings or _Settings()
    cfg = cfg_source.core
    metrics: _MetricsCollector | None = None
    if cfg.enable_metrics:
        metrics = _MetricsCollector(enabled=True)
    # Default built-in enrichers
    from .plugins.enrichers import BaseEnricher
    from .plugins.enrichers.context_vars import ContextVarsEnricher
    from .plugins.enrichers.runtime_info import RuntimeInfoEnricher

    default_enrichers: list[BaseEnricher] = [
        RuntimeInfoEnricher(),
        ContextVarsEnricher(),
    ]

    logger = _SyncLoggerFacade(
        name=name,
        queue_capacity=cfg.max_queue_size,
        batch_max_size=cfg.batch_max_size,
        batch_timeout_seconds=cfg.batch_timeout_seconds,
        backpressure_wait_ms=cfg.backpressure_wait_ms,
        drop_on_full=cfg.drop_on_full,
        sink_write=_sink_write,
        enrichers=default_enrichers,
        metrics=metrics,
    )
    # Policy warning if sensitive fields declared but redactors disabled
    try:
        if (not cfg.enable_redactors) and cfg.sensitive_fields_policy:
            from .core.diagnostics import warn as _warn

            _warn(
                "redactor",
                "sensitive fields policy present but redactors disabled",
                fields=len(cfg.sensitive_fields_policy),
            )
    except Exception:
        pass
    logger.start()
    return logger


@contextmanager
def runtime(*, settings: _Settings | None = None) -> Iterator[_SyncLoggerFacade]:
    """Context manager that initializes and drains the default runtime.

    Yields a default logger; on exit, flushes and returns a drain result via
    StopIteration.value for advanced callers.
    """
    logger = get_logger(settings=settings)
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
