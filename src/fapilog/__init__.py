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

# Keep references to background drain tasks to avoid GC warnings in tests
_PENDING_DRAIN_TASKS: list[object] = []


def get_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
) -> _SyncLoggerFacade:
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
    # Default pipeline: choose sink by env (rotating file vs stdout)
    import os as _os
    from pathlib import Path as _Path
    from typing import Any as _Any

    from .plugins.sinks.rotating_file import RotatingFileSink as _RotatingFileSink
    from .plugins.sinks.rotating_file import (
        RotatingFileSinkConfig as _RotatingFileSinkConfig,
    )

    file_dir = _os.getenv("FAPILOG_FILE__DIRECTORY")
    sink: _Any
    if file_dir:
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
        # Ensure sink is started for file mode
        import asyncio as _asyncio

        try:
            _asyncio.run(sink.start())
        except RuntimeError:
            loop = _asyncio.get_event_loop()
            loop.create_task(sink.start())
    else:
        sink = _StdoutJsonSink()

    async def _sink_write(entry: dict) -> None:
        await sink.write(entry)

    async def _sink_write_serialized(view: object) -> None:
        # Duck-typed: only call if sink implements it
        try:
            await sink.write_serialized(view)
        except AttributeError:
            # Sink lacks fast-path method; ignore
            return None

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


@contextmanager
def runtime(*, settings: _Settings | None = None) -> Iterator[_SyncLoggerFacade]:
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

        try:
            _ = asyncio.run(logger.stop_and_drain())
        except RuntimeError:
            # Already inside a running loop; fire-and-forget best-effort
            try:
                loop = asyncio.get_event_loop()
                task = loop.create_task(logger.stop_and_drain())
                # Keep a strong reference to avoid GC-related warnings
                _PENDING_DRAIN_TASKS.append(task)

                def _on_done(_t: object) -> None:
                    try:
                        _PENDING_DRAIN_TASKS.remove(task)
                    except ValueError:
                        return

                task.add_done_callback(_on_done)
            except Exception:
                # Last resort: run drain in a background thread
                import threading as _threading

                def _runner() -> None:  # pragma: no cover - rare fallback
                    import asyncio as _asyncio

                    try:
                        _asyncio.run(logger.stop_and_drain())
                    except Exception:
                        return

                _threading.Thread(target=_runner, daemon=True).start()


# Version info for compatibility
__version__ = "3.0.0-alpha.1"
__author__ = "Chris Haste"
__email__ = "chris@haste.dev"
VERSION = __version__
