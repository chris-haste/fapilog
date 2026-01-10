"""
Public entrypoints for Fapilog v3.

Provides zero-config `get_logger()` and `runtime()` per Story #79.
"""

from __future__ import annotations

import asyncio as _asyncio
import os as _os
from contextlib import asynccontextmanager as _asynccontextmanager
from contextlib import contextmanager as _contextmanager
from dataclasses import dataclass
from pathlib import Path as _Path
from typing import Any as _Any
from typing import AsyncIterator as _AsyncIterator
from typing import Callable as _Callable
from typing import Coroutine as _Coroutine
from typing import Iterator as _Iterator
from typing import cast as _cast

from .core.events import LogEvent
from .core.logger import AsyncLoggerFacade as _AsyncLoggerFacade
from .core.logger import DrainResult
from .core.logger import SyncLoggerFacade as _SyncLoggerFacade
from .core.retry import RetryConfig as _RetryConfig
from .core.settings import Settings as _Settings
from .metrics.metrics import MetricsCollector as _MetricsCollector
from .plugins import loader as _loader
from .plugins.enrichers import BaseEnricher as _BaseEnricher
from .plugins.filters.level import LEVEL_PRIORITY as _LEVEL_PRIORITY
from .plugins.processors import BaseProcessor as _BaseProcessor
from .plugins.processors.size_guard import SizeGuardConfig as _SizeGuardConfig
from .plugins.redactors import BaseRedactor as _BaseRedactor
from .plugins.redactors.field_mask import FieldMaskConfig as _FieldMaskConfig
from .plugins.redactors.regex_mask import RegexMaskConfig as _RegexMaskConfig
from .plugins.redactors.url_credentials import (
    UrlCredentialsConfig as _UrlCredentialsConfig,
)
from .plugins.sinks.audit import AuditSinkConfig as _AuditSinkConfig
from .plugins.sinks.contrib.cloudwatch import (
    CloudWatchSinkConfig as _CloudWatchSinkConfig,
)
from .plugins.sinks.contrib.postgres import PostgresSinkConfig as _PostgresSinkConfig
from .plugins.sinks.http_client import HttpSinkConfig as _HttpSinkConfig
from .plugins.sinks.rotating_file import (
    RotatingFileSinkConfig as _RotatingFileSinkConfig,
)
from .plugins.sinks.stdout_json import StdoutJsonSink as _StdoutJsonSink
from .plugins.sinks.webhook import WebhookSinkConfig as _WebhookSinkConfig

# Public exports
Settings = _Settings

__all__ = [
    "get_logger",
    "get_async_logger",
    "runtime",
    "runtime_async",
    "Settings",
    "DrainResult",
    "LogEvent",
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


def _apply_plugin_settings(settings: _Settings) -> None:
    """Apply plugin validation mode and related settings to the loader."""

    mode_map = {
        "disabled": _loader.ValidationMode.DISABLED,
        "warn": _loader.ValidationMode.WARN,
        "strict": _loader.ValidationMode.STRICT,
    }
    mode = mode_map.get(
        (settings.plugins.validation_mode or "disabled").lower(),
        _loader.ValidationMode.DISABLED,
    )
    _loader.set_validation_mode(mode)


def _sink_configs(settings: _Settings) -> dict[str, dict[str, _Any]]:
    scfg = settings.sink_config
    configs: dict[str, dict[str, _Any]] = {
        "stdout_json": {},
        "rotating_file": {
            "config": _RotatingFileSinkConfig(
                directory=_Path(scfg.rotating_file.directory)
                if scfg.rotating_file.directory
                else _Path("."),
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
            "config": _HttpSinkConfig(
                endpoint=settings.http.endpoint or "",
                headers=settings.http.resolved_headers(),
                retry=_RetryConfig(
                    max_attempts=settings.http.retry_max_attempts,
                    base_delay=settings.http.retry_backoff_seconds or 1.0,
                )
                if settings.http.retry_max_attempts
                else None,
                timeout_seconds=settings.http.timeout_seconds,
                batch_size=settings.http.batch_size,
                batch_timeout_seconds=settings.http.batch_timeout_seconds,
                batch_format=settings.http.batch_format,
                batch_wrapper_key=settings.http.batch_wrapper_key,
            )
        },
        "webhook": {
            "config": _WebhookSinkConfig(
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
                batch_size=scfg.webhook.batch_size,
                batch_timeout_seconds=scfg.webhook.batch_timeout_seconds,
            )
        },
        "loki": {
            "config": {
                "url": scfg.loki.url,
                "tenant_id": scfg.loki.tenant_id,
                "labels": scfg.loki.labels,
                "label_keys": scfg.loki.label_keys,
                "batch_size": scfg.loki.batch_size,
                "batch_timeout_seconds": scfg.loki.batch_timeout_seconds,
                "timeout_seconds": scfg.loki.timeout_seconds,
                "max_retries": scfg.loki.max_retries,
                "retry_base_delay": scfg.loki.retry_base_delay,
                "auth_username": scfg.loki.auth_username,
                "auth_password": scfg.loki.auth_password,
                "auth_token": scfg.loki.auth_token,
                "circuit_breaker_enabled": scfg.loki.circuit_breaker_enabled,
                "circuit_breaker_threshold": scfg.loki.circuit_breaker_threshold,
            }
        },
        "cloudwatch": {
            "config": _CloudWatchSinkConfig(
                log_group_name=scfg.cloudwatch.log_group_name,
                log_stream_name=scfg.cloudwatch.log_stream_name,
                region=scfg.cloudwatch.region,
                create_log_group=scfg.cloudwatch.create_log_group,
                create_log_stream=scfg.cloudwatch.create_log_stream,
                batch_size=scfg.cloudwatch.batch_size,
                batch_timeout_seconds=scfg.cloudwatch.batch_timeout_seconds,
                endpoint_url=scfg.cloudwatch.endpoint_url,
                max_retries=scfg.cloudwatch.max_retries,
                retry_base_delay=scfg.cloudwatch.retry_base_delay,
                circuit_breaker_enabled=scfg.cloudwatch.circuit_breaker_enabled,
                circuit_breaker_threshold=scfg.cloudwatch.circuit_breaker_threshold,
            )
        },
        "postgres": {
            "config": _PostgresSinkConfig(
                dsn=scfg.postgres.dsn,
                host=scfg.postgres.host,
                port=scfg.postgres.port,
                database=scfg.postgres.database,
                user=scfg.postgres.user,
                password=scfg.postgres.password,
                table_name=scfg.postgres.table_name,
                schema_name=scfg.postgres.schema_name,
                create_table=scfg.postgres.create_table,
                min_pool_size=scfg.postgres.min_pool_size,
                max_pool_size=scfg.postgres.max_pool_size,
                pool_acquire_timeout=scfg.postgres.pool_acquire_timeout,
                batch_size=scfg.postgres.batch_size,
                batch_timeout_seconds=scfg.postgres.batch_timeout_seconds,
                max_retries=scfg.postgres.max_retries,
                retry_base_delay=scfg.postgres.retry_base_delay,
                circuit_breaker_enabled=scfg.postgres.circuit_breaker_enabled,
                circuit_breaker_threshold=scfg.postgres.circuit_breaker_threshold,
                use_jsonb=scfg.postgres.use_jsonb,
                include_raw_json=scfg.postgres.include_raw_json,
                extract_fields=scfg.postgres.extract_fields,
            )
        },
        "audit": {
            "config": _AuditSinkConfig(
                compliance_level=scfg.audit.compliance_level,
                storage_path=scfg.audit.storage_path,
                retention_days=scfg.audit.retention_days,
                encrypt_logs=scfg.audit.encrypt_logs,
                require_integrity=scfg.audit.require_integrity,
                real_time_alerts=scfg.audit.real_time_alerts,
            )
        },
        "sealed": scfg.sealed.model_dump(exclude_none=True),
    }
    configs.update(scfg.extra)
    return configs


def _enricher_configs(settings: _Settings) -> dict[str, dict[str, _Any]]:
    ecfg = settings.enricher_config
    cfg: dict[str, dict[str, _Any]] = {
        "runtime_info": ecfg.runtime_info,
        "context_vars": ecfg.context_vars,
        "integrity": ecfg.integrity.model_dump(exclude_none=True),
    }
    cfg.update(ecfg.extra)
    return cfg


def _redactor_configs(settings: _Settings) -> dict[str, dict[str, _Any]]:
    rcfg = settings.redactor_config
    cfg: dict[str, dict[str, _Any]] = {
        "field_mask": {"config": _FieldMaskConfig(**rcfg.field_mask.model_dump())},
        "regex_mask": {"config": _RegexMaskConfig(**rcfg.regex_mask.model_dump())},
        "url_credentials": {
            "config": _UrlCredentialsConfig(**rcfg.url_credentials.model_dump())
        },
    }
    cfg.update(rcfg.extra)
    return cfg


def _filter_configs(settings: _Settings) -> dict[str, dict[str, _Any]]:
    fcfg = settings.filter_config
    cfg: dict[str, dict[str, _Any]] = {
        "level": fcfg.level,
        "sampling": fcfg.sampling,
        "rate_limit": fcfg.rate_limit,
        "adaptive_sampling": fcfg.adaptive_sampling,
        "trace_sampling": fcfg.trace_sampling,
        "first_occurrence": fcfg.first_occurrence,
    }
    cfg.update(fcfg.extra)
    return cfg


def _processor_configs(
    settings: _Settings, metrics: _MetricsCollector | None = None
) -> dict[str, dict[str, _Any]]:
    pcfg = settings.processor_config
    cfg: dict[str, dict[str, _Any]] = {
        "zero_copy": pcfg.zero_copy,
    }
    cfg["size_guard"] = {
        "config": _SizeGuardConfig(**pcfg.size_guard.model_dump()),
    }
    if metrics is not None:
        cfg["size_guard"]["metrics"] = metrics
    cfg.update(pcfg.extra)
    return cfg


def _default_sink_names(settings: _Settings) -> list[str]:
    if settings.http.endpoint:
        return ["http"]
    if _os.getenv("FAPILOG_FILE__DIRECTORY"):
        return ["rotating_file"]
    return ["stdout_json"]


def _default_env_sink_cfg(name: str) -> dict[str, _Any]:
    if name == "rotating_file":
        return {
            "config": _RotatingFileSinkConfig(
                directory=_Path(_os.getenv("FAPILOG_FILE__DIRECTORY", ".")),
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
                compress_rotated=_os.getenv(
                    "FAPILOG_FILE__COMPRESS_ROTATED", "false"
                ).lower()
                in {"1", "true", "yes"},
            )
        }
    return {}


def _load_plugins(
    group: str, names: list[str], settings: _Settings, cfgs: dict[str, dict[str, _Any]]
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
) -> tuple[
    list[object],
    list[object],
    list[object],
    list[object],
    list[object],
    _MetricsCollector | None,
]:
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

    processor_names = list(core_cfg.processors or [])
    processors = _load_plugins(
        "fapilog.processors",
        processor_names,
        settings,
        _processor_configs(settings, metrics),
    )

    filter_names = list(core_cfg.filters or [])
    filter_cfgs = _filter_configs(settings)

    # Auto-level filter when log_level set and no explicit override
    if (
        not core_cfg.filters
        and core_cfg.log_level
        and _normalize(core_cfg.log_level) != "debug"
    ):
        filter_names.insert(0, "level")
        level_cfg = filter_cfgs.setdefault("level", {})
        level_cfg.setdefault("config", {})
        level_cfg["config"].setdefault("min_level", core_cfg.log_level)

    filters = _load_plugins(
        "fapilog.filters",
        filter_names,
        settings,
        filter_cfgs,
    )

    return sinks, enrichers, redactors, processors, filters, metrics


def _make_sink_writer(sink: _Any) -> tuple[_Any, _Any]:
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


def _fanout_writer(
    sinks: list[object],
    *,
    parallel: bool = False,
    circuit_config: _Any | None = None,
) -> tuple[_Any, _Any]:
    """Create fanout writer with optional parallelization and circuit breakers.

    Args:
        sinks: List of sink instances
        parallel: If True, write to sinks in parallel
        circuit_config: Optional SinkCircuitBreakerConfig for fault isolation
    """
    from .core.circuit_breaker import SinkCircuitBreaker

    writers = [_make_sink_writer(s) for s in sinks]

    # Create circuit breakers for each sink if enabled
    breakers: dict[int, SinkCircuitBreaker] = {}
    if circuit_config is not None and getattr(circuit_config, "enabled", False):
        for sink in sinks:
            name = getattr(sink, "name", type(sink).__name__)
            breakers[id(sink)] = SinkCircuitBreaker(name, circuit_config)

    async def _write_one(
        sink: object,
        write_fn: _Any,
        entry: dict,
    ) -> None:
        """Write to a single sink with circuit breaker protection."""
        breaker = breakers.get(id(sink))

        if breaker and not breaker.should_allow():
            return  # Skip - circuit is open

        try:
            await write_fn(entry)
            if breaker:
                breaker.record_success()
        except Exception:
            if breaker:
                breaker.record_failure()
            # Contain error - don't propagate

    async def _write_sequential(entry: dict) -> None:
        for i, (write, _) in enumerate(writers):
            await _write_one(sinks[i], write, entry)

    async def _write_parallel(entry: dict) -> None:
        if len(writers) <= 1:
            # Single sink, no need for gather
            if writers:
                await _write_one(sinks[0], writers[0][0], entry)
            return

        tasks = []
        for i, (write, _) in enumerate(writers):
            sink = sinks[i]
            breaker = breakers.get(id(sink))

            if breaker and not breaker.should_allow():
                continue  # Skip - circuit is open

            tasks.append(_write_one(sink, write, entry))

        if tasks:
            await _asyncio.gather(*tasks, return_exceptions=True)

    async def _write(entry: dict) -> None:
        if parallel and len(writers) > 1:
            await _write_parallel(entry)
        else:
            await _write_sequential(entry)

    async def _write_serialized(view: object) -> None:
        for _, write_s in writers:
            try:
                await write_s(view)
            except Exception:
                pass  # Contain errors

    return _write, _write_serialized


def _routing_or_fanout_writer(
    sinks: list[object],
    cfg_source: _Settings,
    circuit_config: _Any | None,
) -> tuple[_Any, _Any]:
    """Return sink writer honoring routing configuration when enabled."""
    routing = getattr(cfg_source, "sink_routing", None)
    routing_enabled = routing is not None and routing.enabled and bool(routing.rules)
    if routing_enabled:
        try:
            from .core.routing import build_routing_writer
        except Exception:
            routing_enabled = False
        else:
            return build_routing_writer(
                sinks,
                routing,
                parallel=cfg_source.core.sink_parallel_writes,
                circuit_config=circuit_config,
            )

    return _fanout_writer(
        sinks,
        parallel=cfg_source.core.sink_parallel_writes,
        circuit_config=circuit_config,
    )


@dataclass(slots=True)
class _LoggerSetup:
    """Container for logger configuration results (internal use)."""

    settings: _Settings
    sinks: list[object]
    enrichers: list[object]
    redactors: list[object]
    processors: list[object]
    filters: list[object]
    metrics: _MetricsCollector | None
    sink_write: _Callable[[dict[str, _Any]], _Coroutine[_Any, _Any, None]]
    sink_write_serialized: _Callable[[object], _Coroutine[_Any, _Any, None]] | None
    circuit_config: _Any  # SinkCircuitBreakerConfig | None (lazy import)
    level_gate: int | None


def _configure_logger_common(
    settings: _Settings | None,
    sinks: list[object] | None,
) -> _LoggerSetup:
    """
    Configure logger components without creating facade.

    Shared setup logic for sync and async loggers. Returns unstarted plugins.
    """
    cfg_source = settings or _Settings()
    _apply_plugin_settings(cfg_source)
    built_sinks, enrichers, redactors, processors, filters, metrics = _build_pipeline(
        cfg_source
    )

    if sinks is not None:
        built_sinks = list(sinks)

    circuit_config = None
    if cfg_source.core.sink_circuit_breaker_enabled:
        from .core.circuit_breaker import SinkCircuitBreakerConfig

        circuit_config = SinkCircuitBreakerConfig(
            enabled=True,
            failure_threshold=cfg_source.core.sink_circuit_breaker_failure_threshold,
            recovery_timeout_seconds=cfg_source.core.sink_circuit_breaker_recovery_timeout_seconds,
        )

    sink_write, sink_write_serialized = _routing_or_fanout_writer(
        built_sinks,
        cfg_source,
        circuit_config,
    )

    level_gate = None
    if not cfg_source.core.filters:
        lvl = cfg_source.core.log_level.upper()
        if lvl != "DEBUG":
            level_gate = _LEVEL_PRIORITY.get(lvl, None)

    return _LoggerSetup(
        settings=cfg_source,
        sinks=built_sinks,
        enrichers=enrichers,
        redactors=redactors,
        processors=processors,
        filters=filters,
        metrics=metrics,
        sink_write=sink_write,
        sink_write_serialized=sink_write_serialized,
        circuit_config=circuit_config,
        level_gate=level_gate,
    )


async def _start_plugins(
    plugins: list[_Any],
    plugin_type: str,
) -> list[_Any]:
    """Start plugins, returning only successfully started ones.

    Plugins without a start() method are included without calling start().
    Plugins that fail during start() are excluded and a diagnostic is emitted.
    """
    started: list[_Any] = []
    for plugin in plugins:
        try:
            if hasattr(plugin, "start"):
                await plugin.start()
            started.append(plugin)
        except Exception as exc:
            try:
                from .core import diagnostics as _diag

                _diag.warn(
                    plugin_type,
                    "plugin start failed",
                    plugin=getattr(plugin, "name", type(plugin).__name__),
                    error=str(exc),
                )
            except Exception:
                pass
    return started


def _start_plugins_sync(
    enrichers: list[_Any],
    redactors: list[_Any],
    processors: list[_Any],
    filters: list[_Any],
) -> tuple[list[_Any], list[_Any], list[_Any], list[_Any]]:
    """
    Start plugins in sync context, falling back safely on failure.

    If an event loop is running, startup is offloaded to a thread to avoid
    blocking the loop. On failure, returns the original unstarted plugins.
    """

    async def _do_start() -> tuple[list[_Any], list[_Any], list[_Any], list[_Any]]:
        return (
            await _start_plugins(enrichers, "enricher"),
            await _start_plugins(redactors, "redactor"),
            await _start_plugins(processors, "processor"),
            await _start_plugins(filters, "filter"),
        )

    def _run_sync() -> tuple[list[_Any], list[_Any], list[_Any], list[_Any]]:
        coro = _do_start()
        try:
            return _asyncio.run(coro)
        except Exception:
            try:
                coro.close()
            except Exception:
                pass
            raise

    try:
        _asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_sync)
            return future.result(timeout=5.0)
    except RuntimeError:
        try:
            return _run_sync()
        except Exception:
            return enrichers, redactors, processors, filters
    except Exception:
        return enrichers, redactors, processors, filters


async def _stop_plugins(plugins: list[_Any], plugin_type: str) -> None:
    """Stop all plugins, containing errors.

    Plugins are stopped in reverse order to respect dependency ordering.
    Errors during stop() are logged but do not prevent other plugins from stopping.
    """
    for plugin in reversed(plugins):
        try:
            if hasattr(plugin, "stop"):
                await plugin.stop()
        except Exception as exc:
            try:
                from .core import diagnostics as _diag

                _diag.warn(
                    plugin_type,
                    "plugin stop failed",
                    plugin=getattr(plugin, "name", type(plugin).__name__),
                    error=str(exc),
                )
            except Exception:
                pass


def _apply_logger_extras(
    logger: _SyncLoggerFacade | _AsyncLoggerFacade,
    setup: _LoggerSetup,
    *,
    started_enrichers: list[_Any],
    started_redactors: list[_Any],
    started_processors: list[_Any],
    started_filters: list[_Any],
) -> None:
    """Apply post-creation configuration to logger."""
    cfg = setup.settings

    try:
        if cfg.core.context_binding_enabled and cfg.core.default_bound_context:
            logger.bind(**cfg.core.default_bound_context)
    except Exception:
        pass

    try:
        if cfg.core.sensitive_fields_policy:
            from .core.diagnostics import warn as _warn

            _warn(
                "redactor",
                "sensitive fields policy present",
                fields=len(cfg.core.sensitive_fields_policy),
                _rate_limit_key="policy",
            )
    except Exception:
        pass

    try:
        if cfg.core.capture_unhandled_enabled:
            from .core.errors import capture_unhandled_exceptions as _cap_unhandled

            _cap_unhandled(logger)
    except Exception:
        pass

    logger._redactors = _cast(list[_BaseRedactor], started_redactors)  # noqa: SLF001
    logger._processors = _cast(list[_BaseProcessor], started_processors)  # noqa: SLF001
    logger._filters = started_filters  # noqa: SLF001
    logger._sinks = setup.sinks  # noqa: SLF001


def get_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
    sinks: list[object] | None = None,
) -> _SyncLoggerFacade:
    setup = _configure_logger_common(settings, sinks)

    (
        enrichers,
        redactors,
        processors,
        filters,
    ) = _start_plugins_sync(
        setup.enrichers,
        setup.redactors,
        setup.processors,
        setup.filters,
    )

    cfg = setup.settings
    logger = _SyncLoggerFacade(
        name=name,
        queue_capacity=cfg.core.max_queue_size,
        batch_max_size=cfg.core.batch_max_size,
        batch_timeout_seconds=cfg.core.batch_timeout_seconds,
        backpressure_wait_ms=cfg.core.backpressure_wait_ms,
        drop_on_full=cfg.core.drop_on_full,
        sink_write=setup.sink_write,
        sink_write_serialized=setup.sink_write_serialized,
        enrichers=_cast(list[_BaseEnricher], enrichers),
        processors=_cast(list[_BaseProcessor], processors),
        filters=filters,
        metrics=setup.metrics,
        exceptions_enabled=cfg.core.exceptions_enabled,
        exceptions_max_frames=cfg.core.exceptions_max_frames,
        exceptions_max_stack_chars=cfg.core.exceptions_max_stack_chars,
        serialize_in_flush=cfg.core.serialize_in_flush,
        num_workers=cfg.core.worker_count,
        level_gate=setup.level_gate,
    )

    _apply_logger_extras(
        logger,
        setup,
        started_enrichers=enrichers,
        started_redactors=redactors,
        started_processors=processors,
        started_filters=filters,
    )
    logger.start()
    return logger


async def get_async_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
    sinks: list[object] | None = None,
) -> _AsyncLoggerFacade:
    setup = _configure_logger_common(settings, sinks)

    enrichers = await _start_plugins(setup.enrichers, "enricher")
    redactors = await _start_plugins(setup.redactors, "redactor")
    processors = await _start_plugins(setup.processors, "processor")
    filters = await _start_plugins(setup.filters, "filter")

    cfg = setup.settings
    logger = _AsyncLoggerFacade(
        name=name,
        queue_capacity=cfg.core.max_queue_size,
        batch_max_size=cfg.core.batch_max_size,
        batch_timeout_seconds=cfg.core.batch_timeout_seconds,
        backpressure_wait_ms=cfg.core.backpressure_wait_ms,
        drop_on_full=cfg.core.drop_on_full,
        sink_write=setup.sink_write,
        sink_write_serialized=setup.sink_write_serialized,
        enrichers=_cast(list[_BaseEnricher], enrichers),
        processors=_cast(list[_BaseProcessor], processors),
        filters=filters,
        metrics=setup.metrics,
        exceptions_enabled=cfg.core.exceptions_enabled,
        exceptions_max_frames=cfg.core.exceptions_max_frames,
        exceptions_max_stack_chars=cfg.core.exceptions_max_stack_chars,
        serialize_in_flush=cfg.core.serialize_in_flush,
        num_workers=cfg.core.worker_count,
        level_gate=setup.level_gate,
    )

    _apply_logger_extras(
        logger,
        setup,
        started_enrichers=enrichers,
        started_redactors=redactors,
        started_processors=processors,
        started_filters=filters,
    )
    logger.start()
    return logger


@_asynccontextmanager
async def runtime_async(
    *, settings: _Settings | None = None
) -> _AsyncIterator[_AsyncLoggerFacade]:
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


@_contextmanager
def runtime(
    *,
    settings: _Settings | None = None,
    allow_in_event_loop: bool = False,
) -> _Iterator[_SyncLoggerFacade]:
    """Context manager that initializes and drains the default runtime."""
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
        coro = logger.stop_and_drain()
        try:
            loop: _asyncio.AbstractEventLoop | None = _asyncio.get_running_loop()
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
                _ = _asyncio.run(coro)
            except RuntimeError:
                try:
                    coro.close()
                except Exception:
                    pass
                import threading as _threading

                def _runner() -> None:  # pragma: no cover - rare fallback
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
