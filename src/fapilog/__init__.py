"""
Public entrypoints for Fapilog v3.

Provides zero-config `get_logger()` and `runtime()` per Story #79.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, cast

from .core.logger import AsyncLoggerFacade, SyncLoggerFacade
from .core.retry import RetryConfig as _RetryConfig
from .core.settings import Settings as _Settings
from .metrics.metrics import MetricsCollector as _MetricsCollector
from .plugins import loader as _loader
from .plugins.enrichers import BaseEnricher as _BaseEnricher
from .plugins.redactors import BaseRedactor as _BaseRedactor
from .plugins.redactors.field_mask import FieldMaskConfig
from .plugins.redactors.regex_mask import RegexMaskConfig
from .plugins.redactors.url_credentials import UrlCredentialsConfig
from .plugins.sinks.http_client import HttpSinkConfig
from .plugins.sinks.rotating_file import RotatingFileSinkConfig
from .plugins.sinks.stdout_json import StdoutJsonSink as _StdoutJsonSink
from .plugins.sinks.webhook import WebhookSinkConfig

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


def _normalize(name: str) -> str:
    return name.replace("-", "_").lower()


def _plugin_allowed(name: str, settings: _Settings) -> bool:
    allow = (
        {_normalize(n) for n in settings.plugins.allowlist}
        if settings.plugins.allowlist
        else None
    )
    deny = {_normalize(n) for n in settings.plugins.denylist}
    n = _normalize(name)
    if allow is not None and n not in allow:
        return False
    if n in deny:
        return False
    return True


def _sink_configs(settings: _Settings) -> dict[str, dict[str, Any]]:
    scfg = settings.sink_config
    configs: dict[str, dict[str, Any]] = {
        "stdout_json": {},
        "rotating_file": {
            "config": RotatingFileSinkConfig(
                directory=Path(scfg.rotating_file.directory)
                if scfg.rotating_file.directory
                else Path("."),
                filename_prefix=scfg.rotating_file.filename_prefix,
                mode=scfg.rotating_file.mode,
                max_bytes=scfg.rotating_file.max_bytes,
                interval_seconds=scfg.rotating_file.interval_seconds,
                max_files=scfg.rotating_file.max_files,
                max_total_bytes=scfg.rotating_file.max_total_bytes,
                compress_rotated=scfg.rotating_file.compress_rotated,
            )
        },
        "http": {
            "config": HttpSinkConfig(
                endpoint=settings.http.endpoint or "",
                headers=settings.http.resolved_headers(),
                retry=_RetryConfig(
                    max_attempts=settings.http.retry_max_attempts,
                    base_delay=settings.http.retry_backoff_seconds or 1.0,
                )
                if settings.http.retry_max_attempts
                else None,
                timeout_seconds=settings.http.timeout_seconds,
            )
        },
        "webhook": {
            "config": WebhookSinkConfig(
                endpoint=scfg.webhook.endpoint or "",
                secret=scfg.webhook.secret,
                headers=scfg.webhook.headers,
                retry=_RetryConfig(
                    max_attempts=scfg.webhook.retry_max_attempts,
                    base_delay=scfg.webhook.retry_backoff_seconds or 1.0,
                )
                if scfg.webhook.retry_max_attempts
                else None,
                timeout_seconds=scfg.webhook.timeout_seconds,
            )
        },
        "sealed": scfg.sealed.model_dump(exclude_none=True),
    }
    configs.update(scfg.extra)
    return configs


def _enricher_configs(settings: _Settings) -> dict[str, dict[str, Any]]:
    ecfg = settings.enricher_config
    cfg: dict[str, dict[str, Any]] = {
        "runtime_info": ecfg.runtime_info,
        "context_vars": ecfg.context_vars,
        "integrity": ecfg.integrity.model_dump(exclude_none=True),
    }
    cfg.update(ecfg.extra)
    return cfg


def _redactor_configs(settings: _Settings) -> dict[str, dict[str, Any]]:
    rcfg = settings.redactor_config
    cfg: dict[str, dict[str, Any]] = {
        "field_mask": {"config": FieldMaskConfig(**rcfg.field_mask.model_dump())},
        "regex_mask": {"config": RegexMaskConfig(**rcfg.regex_mask.model_dump())},
        "url_credentials": {
            "config": UrlCredentialsConfig(**rcfg.url_credentials.model_dump())
        },
    }
    cfg.update(rcfg.extra)
    return cfg


def _default_sink_names(settings: _Settings) -> list[str]:
    if settings.http.endpoint:
        return ["http"]
    if os.getenv("FAPILOG_FILE__DIRECTORY"):
        return ["rotating_file"]
    return ["stdout_json"]


def _default_env_sink_cfg(name: str) -> dict[str, Any]:
    if name == "rotating_file":
        return {
            "config": RotatingFileSinkConfig(
                directory=Path(os.getenv("FAPILOG_FILE__DIRECTORY", ".")),
                filename_prefix=os.getenv("FAPILOG_FILE__FILENAME_PREFIX", "fapilog"),
                mode=os.getenv("FAPILOG_FILE__MODE", "json"),
                max_bytes=int(os.getenv("FAPILOG_FILE__MAX_BYTES", "10485760")),
                interval_seconds=(
                    int(os.getenv("FAPILOG_FILE__INTERVAL_SECONDS", "0")) or None
                ),
                max_files=(int(os.getenv("FAPILOG_FILE__MAX_FILES", "0")) or None),
                max_total_bytes=(
                    int(os.getenv("FAPILOG_FILE__MAX_TOTAL_BYTES", "0")) or None
                ),
                compress_rotated=os.getenv(
                    "FAPILOG_FILE__COMPRESS_ROTATED", "false"
                ).lower()
                in {"1", "true", "yes"},
            )
        }
    return {}


def _load_plugins(
    group: str, names: list[str], settings: _Settings, cfgs: dict[str, dict[str, Any]]
) -> list[object]:
    plugins: list[object] = []
    if not settings.plugins.enabled:
        return plugins
    for name in names:
        if not _plugin_allowed(name, settings):
            continue
        cfg = cfgs.get(_normalize(name), {})
        try:
            plugin = _loader.load_plugin(group, name, cfg)
            plugins.append(plugin)
        except (_loader.PluginNotFoundError, _loader.PluginLoadError) as exc:
            try:
                from .core import diagnostics as _diag

                _diag.warn(
                    "plugins",
                    "plugin load failed",
                    group=group,
                    plugin=name,
                    error=str(exc),
                )
            except Exception:
                pass
    return plugins


def _build_pipeline(
    settings: _Settings,
) -> tuple[list[object], list[object], list[object], _MetricsCollector | None]:
    core_cfg = settings.core
    metrics: _MetricsCollector | None = (
        _MetricsCollector(enabled=True) if core_cfg.enable_metrics else None
    )

    sink_names = list(core_cfg.sinks or _default_sink_names(settings))
    sink_cfgs = _sink_configs(settings)
    if not core_cfg.sinks:
        # Overlay env-only defaults for fallback selections
        sink_cfgs[_normalize(sink_names[0])].update(
            _default_env_sink_cfg(_normalize(sink_names[0]))
        )
    sinks = _load_plugins("fapilog.sinks", sink_names, settings, sink_cfgs)
    if not sinks:
        sinks = [_StdoutJsonSink()]

    enricher_names = list(core_cfg.enrichers or [])
    enrichers = _load_plugins(
        "fapilog.enrichers", enricher_names, settings, _enricher_configs(settings)
    )

    redactor_names = list(core_cfg.redactors or [])
    if not redactor_names and core_cfg.enable_redactors and core_cfg.redactors_order:
        redactor_names = list(core_cfg.redactors_order)
    redactors = _load_plugins(
        "fapilog.redactors", redactor_names, settings, _redactor_configs(settings)
    )

    integrity_plugin_name = core_cfg.integrity_plugin
    if integrity_plugin_name:
        try:
            from .plugins.integrity import load_integrity_plugin

            integrity = load_integrity_plugin(integrity_plugin_name)
            wrapped: list[object] = []
            for s in sinks:
                if hasattr(integrity, "wrap_sink"):
                    try:
                        s = integrity.wrap_sink(s, core_cfg.integrity_config)
                    except Exception as exc:
                        try:
                            from .core import diagnostics as _diag

                            _diag.warn(
                                "integrity",
                                "integrity sink wrapper failed",
                                plugin=integrity_plugin_name,
                                sink=type(s).__name__,
                                error=str(exc),
                            )
                        except Exception:
                            pass
                wrapped.append(s)
            sinks = wrapped
            if hasattr(integrity, "get_enricher"):
                try:
                    enricher = integrity.get_enricher(core_cfg.integrity_config)
                    if enricher is not None:
                        enrichers.append(enricher)
                except Exception as exc:
                    try:
                        from .core import diagnostics as _diag

                        _diag.warn(
                            "integrity",
                            "integrity enricher failed",
                            plugin=integrity_plugin_name,
                            error=str(exc),
                        )
                    except Exception:
                        pass
        except Exception as exc:
            try:
                from .core import diagnostics as _diag

                _diag.warn(
                    "integrity",
                    "integrity plugin load failed",
                    plugin=integrity_plugin_name,
                    error=str(exc),
                )
            except Exception:
                pass

    return sinks, enrichers, redactors, metrics


def _make_sink_writer(sink: Any) -> tuple[Any, Any]:
    async def _sink_write(entry: dict) -> None:
        if hasattr(sink, "start") and not getattr(sink, "_started", False):
            try:
                await sink.start()
                sink._started = True
            except Exception:
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
        try:
            await sink.write_serialized(view)
        except AttributeError:
            return None

    return _sink_write, _sink_write_serialized


def _fanout_writer(sinks: list[object]) -> tuple[Any, Any]:
    writers = [_make_sink_writer(s) for s in sinks]

    async def _write(entry: dict) -> None:
        for write, _ in writers:
            await write(entry)

    async def _write_serialized(view: object) -> None:
        for _, write_s in writers:
            await write_s(view)

    return _write, _write_serialized


def get_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
) -> SyncLoggerFacade:
    cfg_source = settings or _Settings()
    sinks, enrichers, redactors, metrics = _build_pipeline(cfg_source)
    sink_write, sink_write_serialized = _fanout_writer(sinks)

    logger = SyncLoggerFacade(
        name=name,
        queue_capacity=cfg_source.core.max_queue_size,
        batch_max_size=cfg_source.core.batch_max_size,
        batch_timeout_seconds=cfg_source.core.batch_timeout_seconds,
        backpressure_wait_ms=cfg_source.core.backpressure_wait_ms,
        drop_on_full=cfg_source.core.drop_on_full,
        sink_write=sink_write,
        sink_write_serialized=sink_write_serialized,
        enrichers=cast(list[_BaseEnricher], enrichers),
        metrics=metrics,
        exceptions_enabled=cfg_source.core.exceptions_enabled,
        exceptions_max_frames=cfg_source.core.exceptions_max_frames,
        exceptions_max_stack_chars=cfg_source.core.exceptions_max_stack_chars,
        serialize_in_flush=cfg_source.core.serialize_in_flush,
        num_workers=cfg_source.core.worker_count,
    )
    try:
        if (
            cfg_source.core.context_binding_enabled
            and cfg_source.core.default_bound_context
        ):
            logger.bind(**cfg_source.core.default_bound_context)
    except Exception:
        pass
    try:
        if cfg_source.core.sensitive_fields_policy:
            from .core.diagnostics import warn as _warn

            _warn(
                "redactor",
                "sensitive fields policy present",
                fields=len(cfg_source.core.sensitive_fields_policy),
                _rate_limit_key="policy",
            )
    except Exception:
        pass
    try:
        if cfg_source.core.capture_unhandled_enabled:
            from .core.errors import (
                capture_unhandled_exceptions as _cap_unhandled,
            )

            _cap_unhandled(logger)
    except Exception:
        pass
    logger.start()
    logger._redactors = cast(list[_BaseRedactor], redactors)  # noqa: SLF001
    logger._sinks = sinks  # noqa: SLF001
    return logger


async def get_async_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
) -> AsyncLoggerFacade:
    cfg_source = settings or _Settings()
    sinks, enrichers, redactors, metrics = _build_pipeline(cfg_source)
    sink_write, sink_write_serialized = _fanout_writer(sinks)

    logger = AsyncLoggerFacade(
        name=name,
        queue_capacity=cfg_source.core.max_queue_size,
        batch_max_size=cfg_source.core.batch_max_size,
        batch_timeout_seconds=cfg_source.core.batch_timeout_seconds,
        backpressure_wait_ms=cfg_source.core.backpressure_wait_ms,
        drop_on_full=cfg_source.core.drop_on_full,
        sink_write=sink_write,
        sink_write_serialized=sink_write_serialized,
        enrichers=cast(list[_BaseEnricher], enrichers),
        metrics=metrics,
        exceptions_enabled=cfg_source.core.exceptions_enabled,
        exceptions_max_frames=cfg_source.core.exceptions_max_frames,
        exceptions_max_stack_chars=cfg_source.core.exceptions_max_stack_chars,
        serialize_in_flush=cfg_source.core.serialize_in_flush,
        num_workers=cfg_source.core.worker_count,
    )
    try:
        if (
            cfg_source.core.context_binding_enabled
            and cfg_source.core.default_bound_context
        ):
            logger.bind(**cfg_source.core.default_bound_context)
    except Exception:
        pass
    try:
        if cfg_source.core.sensitive_fields_policy:
            from .core.diagnostics import warn as _warn

            _warn(
                "redactor",
                "sensitive fields policy present",
                fields=len(cfg_source.core.sensitive_fields_policy),
                _rate_limit_key="policy",
            )
    except Exception:
        pass
    try:
        if cfg_source.core.capture_unhandled_enabled:
            from .core.errors import (
                capture_unhandled_exceptions as _cap_unhandled,
            )

            _cap_unhandled(logger)
    except Exception:
        pass
    logger.start()
    logger._redactors = cast(list[_BaseRedactor], redactors)  # noqa: SLF001
    logger._sinks = sinks  # type: ignore[attr-defined]  # noqa: SLF001
    return logger


@asynccontextmanager
async def runtime_async(
    *, settings: _Settings | None = None
) -> AsyncIterator[AsyncLoggerFacade]:
    """Async context manager that initializes and drains the default async runtime."""
    logger = await get_async_logger(settings=settings)
    try:
        yield logger
    finally:
        # Drain the logger gracefully
        try:
            await logger.drain()
        except Exception:
            try:
                from .core.diagnostics import warn as _warn

                _warn("runtime", "Failed to drain async logger during cleanup")
            except Exception:
                pass


@contextmanager
def runtime(
    *,
    settings: _Settings | None = None,
    allow_in_event_loop: bool = False,
) -> Iterator[SyncLoggerFacade]:
    """Context manager that initializes and drains the default runtime."""
    import asyncio as _asyncio

    try:
        _asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        if not allow_in_event_loop:
            raise RuntimeError(
                "fapilog.runtime cannot be used inside an active event loop; "
                "use runtime_async or get_async_logger instead."
            )

    logger = get_logger(settings=settings)
    try:
        yield logger
    finally:
        import asyncio

        coro = logger.stop_and_drain()
        try:
            loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            try:
                task = loop.create_task(coro)
                task.add_done_callback(lambda _fut: None)
            except Exception:
                try:
                    coro.close()
                except Exception:
                    pass
        else:
            try:
                _ = asyncio.run(coro)
            except RuntimeError:
                try:
                    coro.close()
                except Exception:
                    pass
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
