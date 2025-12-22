"""
Public entrypoints for Fapilog v3.

Provides zero-config `get_logger()` and `runtime()` per Story #79.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator

from .core.logger import AsyncLoggerFacade, SyncLoggerFacade
from .core.settings import Settings as _Settings
from .metrics.metrics import MetricsCollector as _MetricsCollector
from .plugins.sinks.stdout_json import StdoutJsonSink as _StdoutJsonSink

# Public exports
Settings = _Settings

__all__ = [
    "get_logger",
    "get_async_logger",
    "runtime",
    "runtime_async",
    "Settings",
    "__version__",
    "VERSION",
]

# Keep references to background drain tasks to avoid GC warnings in tests
_PENDING_DRAIN_TASKS: list[object] = []


def get_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
) -> SyncLoggerFacade:
    """Return a ready-to-use sync logger facade wired to a container pipeline.

    This function provides a zero-config, container-scoped logger that
    automatically configures sinks, enrichers, and metrics based on environment
    variables or custom settings. Each logger instance is isolated with no
    global state.

    @docs:use_cases
    - Web applications need request-scoped logging with correlation IDs
    - Microservices require zero-config logging that works out of the box
    - Development teams want simple logging setup without complex configuration
    - Production systems benefit from container isolation and zero global state
    - FastAPI applications need request context integration for tracing

    @docs:examples
    ```python
    from fapilog import get_logger

    # Zero-config usage (uses environment variables)
    logger = get_logger()
    logger.info("Application started")

    # With custom name for better identification
    logger = get_logger("user_service")
    logger.info("User authentication successful")

    # With custom settings
    from fapilog import Settings
    settings = Settings(core__enable_metrics=True)
    logger = get_logger(settings=settings)
    logger.info("Metrics-enabled logger ready")

    # Cleanup when done
    logger.close()
    ```

    @docs:notes
    - Zero-config by default: reads environment variables
    - Container-scoped isolation: no global mutable state between instances
    - Automatic sink selection: file or stdout via FAPILOG_FILE__DIRECTORY
    - Built-in enrichers: runtime info and context variables
    - Thread-safe across multiple threads
    - Async-aware: works seamlessly with asyncio applications
    - See Environment Configuration in docs for all options
    """
    # Default pipeline: choose sink based on settings/env
    import os as _os
    from pathlib import Path as _Path
    from typing import Any as _Any

    from .plugins.sinks.rotating_file import RotatingFileSink as _RotatingFileSink
    from .plugins.sinks.rotating_file import (
        RotatingFileSinkConfig as _RotatingFileSinkConfig,
    )

    cfg_source = settings or _Settings()
    http_cfg = cfg_source.http
    http_endpoint = http_cfg.endpoint
    file_dir = _os.getenv("FAPILOG_FILE__DIRECTORY")
    sink: _Any
    if http_endpoint:
        from .core.retry import RetryConfig as _RetryConfig
        from .plugins.sinks.http_client import (
            HttpSink as _HttpSink,
        )
        from .plugins.sinks.http_client import (
            HttpSinkConfig as _HttpSinkConfig,
        )

        retry: _RetryConfig | None = None
        if http_cfg.retry_max_attempts:
            retry = _RetryConfig(
                max_attempts=http_cfg.retry_max_attempts,
                base_delay=http_cfg.retry_backoff_seconds or 0.2,
            )
        sink = _HttpSink(
            _HttpSinkConfig(
                endpoint=http_endpoint,
                headers=http_cfg.resolved_headers(),
                retry=retry,
                timeout_seconds=http_cfg.timeout_seconds,
            )
        )
    elif file_dir:
        rfc = _RotatingFileSinkConfig(
            directory=_Path(file_dir),
            filename_prefix=_os.getenv("FAPILOG_FILE__FILENAME_PREFIX", "fapilog"),
            mode=_os.getenv("FAPILOG_FILE__MODE", "json"),
            max_bytes=int(_os.getenv("FAPILOG_FILE__MAX_BYTES", "10485760")),
            interval_seconds=(
                int(_os.getenv("FAPILOG_FILE__INTERVAL_SECONDS", "0")) or None
            ),
            max_files=(int(_os.getenv("FAPILOG_FILE__MAX_FILES", "0")) or None),
            max_total_bytes=(
                int(_os.getenv("FAPILOG_FILE__MAX_TOTAL_BYTES", "0")) or None
            ),
            compress_rotated=(
                _os.getenv("FAPILOG_FILE__COMPRESS_ROTATED", "false").lower()
                in {"1", "true", "yes"}
            ),
        )
        sink = _RotatingFileSink(rfc)
        # Sink will be started lazily when first used
    else:
        sink = _StdoutJsonSink()

    async def _sink_write(entry: dict) -> None:
        # Ensure sink is started if it has a start method
        if hasattr(sink, "start") and not getattr(sink, "_started", False):
            try:
                await sink.start()
                sink._started = True
            except Exception:
                # If start fails, emit diagnostics and continue without it
                try:
                    from .core import diagnostics as _diag

                    _diag.warn(
                        "sink",
                        "sink start failed",
                        sink_type=type(sink).__name__,
                    )
                except Exception:
                    pass
        await sink.write(entry)

    async def _sink_write_serialized(view: object) -> None:
        # Duck-typed: only call if sink implements it
        try:
            await sink.write_serialized(view)
        except AttributeError:
            # Sink lacks fast-path method; ignore
            return None

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

    logger = SyncLoggerFacade(
        name=name,
        queue_capacity=cfg.max_queue_size,
        batch_max_size=cfg.batch_max_size,
        batch_timeout_seconds=cfg.batch_timeout_seconds,
        backpressure_wait_ms=cfg.backpressure_wait_ms,
        drop_on_full=cfg.drop_on_full,
        sink_write=_sink_write,
        sink_write_serialized=_sink_write_serialized,
        enrichers=default_enrichers,
        metrics=metrics,
        exceptions_enabled=cfg.exceptions_enabled,
        exceptions_max_frames=cfg.exceptions_max_frames,
        exceptions_max_stack_chars=cfg.exceptions_max_stack_chars,
        serialize_in_flush=cfg.serialize_in_flush,
    )
    # Apply default bound context if enabled
    try:
        if cfg.context_binding_enabled and cfg.default_bound_context:
            # Bind default context for current task if provided
            # Safe even if bind is absent in older versions (no-attr ignored)
            logger.bind(**cfg.default_bound_context)
    except Exception:
        pass
    # Policy warning if sensitive fields policy is declared
    try:
        if cfg.sensitive_fields_policy:
            from .core.diagnostics import warn as _warn

            _warn(
                "redactor",
                "sensitive fields policy present",
                fields=len(cfg.sensitive_fields_policy),
                _rate_limit_key="policy",
            )
    except Exception:
        pass
    # Configure default redactors if enabled
    try:
        if cfg.enable_redactors and cfg.redactors_order:
            from .plugins.redactors import BaseRedactor
            from .plugins.redactors.field_mask import (
                FieldMaskConfig,
                FieldMaskRedactor,
            )
            from .plugins.redactors.regex_mask import (
                RegexMaskConfig,
                RegexMaskRedactor,
            )
            from .plugins.redactors.url_credentials import (
                UrlCredentialsRedactor,
            )

            # Default patterns for regex-mask
            default_pattern = (
                r"(?i).*\b(password|pass|secret|api[_-]?key|token|"
                r"authorization|set-cookie|ssn|email)\b.*"
            )
            redactors: list[BaseRedactor] = []
            for name in cfg.redactors_order:
                if name == "field-mask":
                    # Wire field-mask redactor with guardrails from settings
                    redactors.append(
                        FieldMaskRedactor(
                            config=FieldMaskConfig(
                                fields_to_mask=list(cfg.sensitive_fields_policy or []),
                                max_depth=(cfg.redaction_max_depth or 16),
                                max_keys_scanned=(
                                    cfg.redaction_max_keys_scanned or 1000
                                ),
                            )
                        )
                    )
                elif name == "regex-mask":
                    redactors.append(
                        RegexMaskRedactor(
                            config=RegexMaskConfig(
                                patterns=[default_pattern],
                                max_depth=(cfg.redaction_max_depth or 16),
                                max_keys_scanned=(
                                    cfg.redaction_max_keys_scanned or 1000
                                ),
                            )
                        )
                    )
                elif name == "url-credentials":
                    redactors.append(UrlCredentialsRedactor())
            # Inject into logger: assign internal redactors
            logger._redactors = redactors
    except Exception:
        # Redaction is best-effort; failures should not block logging
        pass
    # Optional: install unhandled exception hooks
    try:
        if cfg.capture_unhandled_enabled:
            from .core.errors import (
                capture_unhandled_exceptions as _cap_unhandled,
            )

            _cap_unhandled(logger)
    except Exception:
        pass
    logger.start()
    return logger


async def get_async_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
) -> AsyncLoggerFacade:
    """Return a ready-to-use async logger facade wired to a container pipeline.

    This function provides a zero-config, container-scoped async logger that
    automatically configures sinks, enrichers, and metrics based on environment
    variables or custom settings. Each logger instance is isolated with no
    global state.

    @docs:use_cases
    - FastAPI applications need async-first logging with awaitable methods
    - Async microservices require zero-config logging that works with event loops
    - Development teams want simple async logging setup without complex configuration
    - Production systems benefit from container isolation and zero global state
    - Async applications need logging that integrates cleanly with event loops

    @docs:examples
    ```python
    from fapilog import get_async_logger

    # Zero-config usage (uses environment variables)
    logger = await get_async_logger()
    await logger.info("Application started")

    # With custom name for better identification
    logger = await get_async_logger("user_service")
    await logger.info("User authentication successful")

    # With custom settings
    from fapilog import Settings
    settings = Settings(core__enable_metrics=True)
    logger = await get_async_logger(settings=settings)
    await logger.info("Metrics-enabled logger ready")

    # Cleanup when done
    await logger.drain()
    ```

    @docs:notes
    - Zero-config by default: reads environment variables
    - Container-scoped isolation: no global mutable state between instances
    - Automatic sink selection: file or stdout via FAPILOG_FILE__DIRECTORY
    - Built-in enrichers: runtime info and context variables
    - Async-safe: works seamlessly with asyncio applications
    - See Environment Configuration in docs for all options
    """
    # Default pipeline: choose sink based on settings/env
    import os as _os
    from pathlib import Path as _Path
    from typing import Any as _Any

    from .plugins.sinks.rotating_file import RotatingFileSink as _RotatingFileSink
    from .plugins.sinks.rotating_file import (
        RotatingFileSinkConfig as _RotatingFileSinkConfig,
    )

    cfg_source = settings or _Settings()
    http_cfg = cfg_source.http
    http_endpoint = http_cfg.endpoint
    file_dir = _os.getenv("FAPILOG_FILE__DIRECTORY")
    sink: _Any
    if http_endpoint:
        from .core.retry import RetryConfig as _RetryConfig
        from .plugins.sinks.http_client import (
            HttpSink as _HttpSink,
        )
        from .plugins.sinks.http_client import (
            HttpSinkConfig as _HttpSinkConfig,
        )

        retry: _RetryConfig | None = None
        if http_cfg.retry_max_attempts:
            retry = _RetryConfig(
                max_attempts=http_cfg.retry_max_attempts,
                base_delay=http_cfg.retry_backoff_seconds or 0.2,
            )
        sink = _HttpSink(
            _HttpSinkConfig(
                endpoint=http_endpoint,
                headers=http_cfg.resolved_headers(),
                retry=retry,
                timeout_seconds=http_cfg.timeout_seconds,
            )
        )
    elif file_dir:
        rfc = _RotatingFileSinkConfig(
            directory=_Path(file_dir),
            filename_prefix=_os.getenv("FAPILOG_FILE__FILENAME_PREFIX", "fapilog"),
            mode=_os.getenv("FAPILOG_FILE__MODE", "json"),
            max_bytes=int(_os.getenv("FAPILOG_FILE__MAX_BYTES", "10485760")),
            interval_seconds=(
                int(_os.getenv("FAPILOG_FILE__INTERVAL_SECONDS", "0")) or None
            ),
            max_files=(int(_os.getenv("FAPILOG_FILE__MAX_FILES", "0")) or None),
            max_total_bytes=(
                int(_os.getenv("FAPILOG_FILE__MAX_TOTAL_BYTES", "0")) or None
            ),
            compress_rotated=(
                _os.getenv("FAPILOG_FILE__COMPRESS_ROTATED", "false").lower()
                in {"1", "true", "yes"}
            ),
        )
        sink = _RotatingFileSink(rfc)
        # Sink will be started lazily when first used
    else:
        sink = _StdoutJsonSink()

    async def _sink_write(entry: dict) -> None:
        # Ensure sink is started if it has a start method
        if hasattr(sink, "start") and not getattr(sink, "_started", False):
            try:
                await sink.start()
                sink._started = True
            except Exception:
                # If start fails, emit diagnostics and continue without it
                try:
                    from .core import diagnostics as _diag

                    _diag.warn(
                        "sink",
                        "sink start failed",
                        sink_type=type(sink).__name__,
                    )
                except Exception:
                    pass
        await sink.write(entry)

    async def _sink_write_serialized(view: object) -> None:
        # Duck-typed: only call if sink implements it
        try:
            await sink.write_serialized(view)
        except AttributeError:
            # Sink lacks fast-path method; ignore
            return None

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

    logger = AsyncLoggerFacade(
        name=name,
        queue_capacity=cfg.max_queue_size,
        batch_max_size=cfg.batch_max_size,
        batch_timeout_seconds=cfg.batch_timeout_seconds,
        backpressure_wait_ms=cfg.backpressure_wait_ms,
        drop_on_full=cfg.drop_on_full,
        sink_write=_sink_write,
        sink_write_serialized=_sink_write_serialized,
        enrichers=default_enrichers,
        metrics=metrics,
        exceptions_enabled=cfg.exceptions_enabled,
        exceptions_max_frames=cfg.exceptions_max_frames,
        exceptions_max_stack_chars=cfg.exceptions_max_stack_chars,
        serialize_in_flush=cfg.serialize_in_flush,
    )
    # Apply default bound context if enabled
    try:
        if cfg.context_binding_enabled and cfg.default_bound_context:
            # Bind default context for current task if provided
            # Safe even if bind is absent in older versions (no-attr ignored)
            logger.bind(**cfg.default_bound_context)
    except Exception:
        pass
    # Policy warning if sensitive fields policy is declared
    try:
        if cfg.sensitive_fields_policy:
            from .core.diagnostics import warn as _warn

            _warn(
                "redactor",
                "sensitive fields policy present",
                fields=len(cfg.sensitive_fields_policy),
                _rate_limit_key="policy",
            )
    except Exception:
        pass
    # Configure default redactors if enabled
    try:
        if cfg.enable_redactors and cfg.redactors_order:
            from .plugins.redactors import BaseRedactor
            from .plugins.redactors.field_mask import (
                FieldMaskConfig,
                FieldMaskRedactor,
            )
            from .plugins.redactors.regex_mask import (
                RegexMaskConfig,
                RegexMaskRedactor,
            )
            from .plugins.redactors.url_credentials import (
                UrlCredentialsRedactor,
            )

            # Default patterns for regex-mask
            default_pattern = (
                r"(?i).*\b(password|pass|secret|api[_-]?key|token|"
                r"authorization|set-cookie|ssn|email)\b.*"
            )
            redactors: list[BaseRedactor] = []
            for name in cfg.redactors_order:
                if name == "field-mask":
                    # Wire field-mask redactor with guardrails from settings
                    redactors.append(
                        FieldMaskRedactor(
                            config=FieldMaskConfig(
                                fields_to_mask=list(cfg.sensitive_fields_policy or []),
                                max_depth=(cfg.redaction_max_depth or 16),
                                max_keys_scanned=(
                                    cfg.redaction_max_keys_scanned or 1000
                                ),
                            )
                        )
                    )
                elif name == "regex-mask":
                    redactors.append(
                        RegexMaskRedactor(
                            config=RegexMaskConfig(
                                patterns=[default_pattern],
                                max_depth=(cfg.redaction_max_depth or 16),
                                max_keys_scanned=(
                                    cfg.redaction_max_keys_scanned or 1000
                                ),
                            )
                        )
                    )
                elif name == "url-credentials":
                    redactors.append(UrlCredentialsRedactor())
            # Inject into logger: assign internal redactors
            logger._redactors = redactors
    except Exception:
        # Redaction is best-effort; failures should not block logging
        pass
    # Optional: install unhandled exception hooks
    try:
        if cfg.capture_unhandled_enabled:
            from .core.errors import (
                capture_unhandled_exceptions as _cap_unhandled,
            )

            _cap_unhandled(logger)
    except Exception:
        pass
    logger.start()
    return logger


@asynccontextmanager
async def runtime_async(
    *, settings: _Settings | None = None
) -> AsyncIterator[AsyncLoggerFacade]:
    """Async context manager that initializes and drains the default async runtime.

    This function provides an async context manager that automatically handles logger
    lifecycle including initialization, usage, and cleanup. It's perfect for
    async applications that need guaranteed cleanup of logging resources.
    """
    logger = await get_async_logger(settings=settings)
    try:
        yield logger
    finally:
        # Drain the logger gracefully
        try:
            await logger.drain()
        except Exception:
            # Best-effort cleanup; log but don't raise
            try:
                from .core.diagnostics import warn as _warn

                _warn("runtime", "Failed to drain async logger during cleanup")
            except Exception:
                pass


@contextmanager
def runtime(*, settings: _Settings | None = None) -> Iterator[SyncLoggerFacade]:
    """Context manager that initializes and drains the default runtime.

    This function provides a context manager that automatically handles logger
    lifecycle including initialization, usage, and cleanup. It's perfect for
    applications that need guaranteed cleanup of logging resources.
    """
    logger = get_logger(settings=settings)
    try:
        yield logger
    finally:
        # Flush synchronously by running the async close
        import asyncio

        coro = logger.stop_and_drain()
        try:
            _ = asyncio.run(coro)
        except RuntimeError:
            try:
                coro.close()
            except Exception:
                pass
            # Already inside a running loop; run drain in a background thread
            import threading as _threading

            def _runner() -> None:  # pragma: no cover - rare fallback
                import asyncio as _asyncio

                try:
                    coro_inner = logger.stop_and_drain()
                    _asyncio.run(coro_inner)
                except Exception:
                    try:
                        coro_inner.close()
                    except Exception:
                        pass
                    return

            _threading.Thread(target=_runner, daemon=True).start()


# Version info for compatibility (injected by hatch-vcs at build time)
try:
    from ._version import __version__
except Exception:  # pragma: no cover - fallback for editable installs
    __version__ = "0.0.0+local"
__author__ = "Chris Haste"
__email__ = "chris@haste.dev"
VERSION = __version__
