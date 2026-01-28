"""
Public entrypoints for Fapilog v3.

Provides zero-config `get_logger()` and `runtime()` per Story #79.
"""

from __future__ import annotations

import asyncio as _asyncio
import os as _os
import sys as _sys
import threading as _threading
from contextlib import asynccontextmanager as _asynccontextmanager
from contextlib import contextmanager as _contextmanager
from contextlib import suppress as _suppress
from dataclasses import dataclass
from typing import Any as _Any
from typing import AsyncIterator as _AsyncIterator
from typing import Callable as _Callable
from typing import Coroutine as _Coroutine
from typing import Iterator as _Iterator
from typing import Literal as _Literal
from typing import cast as _cast

from . import sinks as sinks
from .builder import AsyncLoggerBuilder, LoggerBuilder

# Preset discovery (public API)
from .core.config_builders import _build_pipeline as _build_pipeline_impl
from .core.config_builders import _default_sink_names, _sink_configs
from .core.events import LogEvent
from .core.logger import AsyncLoggerFacade as _AsyncLoggerFacade
from .core.logger import DrainResult
from .core.logger import SyncLoggerFacade as _SyncLoggerFacade
from .core.presets import list_presets
from .core.settings import Settings as _Settings
from .core.shutdown import install_shutdown_handlers
from .metrics.metrics import MetricsCollector as _MetricsCollector
from .plugins import loader as _loader
from .plugins.enrichers import BaseEnricher as _BaseEnricher
from .plugins.filters.level import LEVEL_PRIORITY as _LEVEL_PRIORITY
from .plugins.processors import BaseProcessor as _BaseProcessor
from .plugins.redactors import BaseRedactor as _BaseRedactor
from .plugins.sinks.stdout_json import StdoutJsonSink as _StdoutJsonSink

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
    "list_presets",
    "LoggerBuilder",
    "AsyncLoggerBuilder",
    "sinks",
    "get_cached_loggers",
    "clear_logger_cache",
    "install_shutdown_handlers",
    "__version__",
    "VERSION",
]

# Keep references to background drain tasks to avoid GC warnings in tests
_PENDING_DRAIN_TASKS: list[object] = []

# Logger instance caches with lock for thread safety (Story 10.29)
_async_logger_cache: dict[str, _AsyncLoggerFacade] = {}
_sync_logger_cache: dict[str, _SyncLoggerFacade] = {}
_cache_lock = _threading.Lock()
_DEFAULT_LOGGER_KEY = "__fapilog_default__"


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


def _apply_default_log_level(
    settings: _Settings,
    *,
    preset: str | None,
) -> _Settings:
    if preset is not None:
        return settings
    try:
        explicit = "log_level" in settings.core.model_fields_set
    except Exception:
        explicit = False
    if not explicit and _os.getenv("FAPILOG_CORE__LOG_LEVEL"):
        explicit = True
    if explicit:
        return settings
    from .core.defaults import get_default_log_level

    updated: _Settings = settings.model_copy(deep=True)
    updated.core.log_level = _cast(
        _Literal["DEBUG", "INFO", "WARNING", "ERROR"],
        get_default_log_level(),
    )
    return updated


def _apply_environment_config(
    settings: _Settings,
    env_config: dict[str, _Any],
) -> _Settings:
    """Apply environment-specific configuration to settings.

    Merges environment config with existing settings. Environment config
    takes precedence for explicitly set values.
    """
    updated: _Settings = settings.model_copy(deep=True)

    # Apply core settings
    core_config = env_config.get("core", {})
    for key, value in core_config.items():
        if hasattr(updated.core, key):
            setattr(updated.core, key, value)

    # Apply enrichers (merge with existing)
    env_enrichers = env_config.get("enrichers", [])
    if env_enrichers:
        existing = list(updated.core.enrichers or [])
        for enricher in env_enrichers:
            if enricher not in existing:
                existing.append(enricher)
        updated.core.enrichers = existing

    return updated


def _stdout_is_tty() -> bool:
    try:
        isatty = getattr(_sys.stdout, "isatty", None)
        return bool(isatty and isatty())
    except Exception:
        return False


def _resolve_format(
    fmt: _Literal["json", "pretty", "auto"] | None,
    settings: _Settings,
) -> str | None:
    if fmt is None:
        return None
    fmt_norm = str(fmt).lower()
    if fmt_norm not in {"json", "pretty", "auto"}:
        raise ValueError(f"Invalid format '{fmt}'. Valid formats: json, pretty, auto.")
    if fmt_norm == "auto":
        if not settings.core.sinks and _default_sink_names(settings) != ["stdout_json"]:
            return None
        return "pretty" if _stdout_is_tty() else "json"
    return fmt_norm


def _apply_format(settings: _Settings, fmt: str) -> None:
    target = "stdout_pretty" if fmt == "pretty" else "stdout_json"
    sinks = list(settings.core.sinks or [])
    if not sinks:
        settings.core.sinks = [target]
        return
    updated: list[str] = []
    replaced = False
    for name in sinks:
        norm = _normalize(name)
        if norm in {"stdout_json", "stdout_pretty"}:
            if not replaced:
                updated.append(target)
                replaced = True
            continue
        updated.append(name)
    if not replaced:
        updated.insert(0, target)
    settings.core.sinks = updated


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
            plugin = _loader.load_plugin(
                group,
                name,
                cfg,
                allow_external=settings.plugins.allow_external,
                allowlist=settings.plugins.allowlist,
            )
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
    """Build logging pipeline (backward-compatible wrapper).

    This wrapper maintains the original signature for backward compatibility.
    Internally delegates to config_builders._build_pipeline with _load_plugins.
    """
    return _build_pipeline_impl(settings, _load_plugins)


def _fanout_writer(
    sinks: list[object],
    *,
    parallel: bool = False,
    circuit_config: _Any | None = None,
) -> tuple[_Any, _Any]:
    """Create fanout writer with optional parallelization and circuit breakers.

    Delegates to SinkWriterGroup for cleaner, class-based implementation.

    Args:
        sinks: List of sink instances
        parallel: If True, write to sinks in parallel
        circuit_config: Optional SinkCircuitBreakerConfig for fault isolation
    """
    from .core.sink_writers import SinkWriterGroup

    group = SinkWriterGroup(sinks, parallel=parallel, circuit_config=circuit_config)
    return group.write, group.write_serialized


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
    """Start plugins synchronously, handling event loop edge cases.

    This function must work in three scenarios:

    1. Called from sync code with no event loop:
       - asyncio.get_running_loop() raises RuntimeError
       - Safe to use asyncio.run() directly

    2. Called from within a running event loop (e.g., Jupyter, async framework):
       - asyncio.get_running_loop() succeeds
       - Cannot use asyncio.run() (raises "loop already running")
       - Must offload to a separate thread with no loop

    3. Startup fails for any reason:
       - Return original unstarted plugins
       - Fail-open: logging should never crash the application

    Threading Safety:
        ThreadPoolExecutor is used with max_workers=1 to serialize startup.
        5-second timeout prevents hangs if plugins are slow.

    See Also:
        docs/architecture/async-sync-boundary.md for detailed explanation.
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
            with _suppress(Exception):
                coro.close()
            raise

    try:
        # Check if we're inside a running event loop
        _asyncio.get_running_loop()
        # Case 2: Loop is running - cannot use asyncio.run() here.
        # Offload to a thread that has no event loop.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_sync)
            return future.result(timeout=5.0)
    except RuntimeError:
        # Case 1: No running loop - safe to use asyncio.run() directly
        try:
            return _run_sync()
        except Exception:
            # Case 3: Startup failed - return originals (fail-open for logging)
            return enrichers, redactors, processors, filters
    except Exception:
        # Case 3: Any other failure - return originals (fail-open for logging)
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


def _prepare_logger(
    name: str | None,
    *,
    preset: str | None,
    format: _Literal["json", "pretty", "auto"] | None,
    settings: _Settings | None,
    sinks: list[object] | None,
    auto_detect: bool,
    environment: str | None,
) -> tuple[_LoggerSetup, _Settings]:
    """Prepare logger configuration without starting plugins.

    This function handles all shared validation, preset handling, environment
    configuration, and format resolution for both sync and async logger creation.

    Args:
        name: Optional logger name (currently unused, passed for future use).
        preset: Built-in preset name (dev, production, fastapi, minimal).
        format: Output format ("json", "pretty", "auto").
        settings: Explicit Settings object (mutually exclusive with preset/format).
        sinks: Custom sink instances (overrides configured sinks).
        auto_detect: Enable automatic environment detection.
        environment: Explicit environment type override.

    Returns:
        Tuple of (_LoggerSetup, Settings) ready for plugin startup.

    Raises:
        ValueError: If mutually exclusive parameters are provided together.
    """
    # Validate mutual exclusivity
    if format is not None and settings is not None:
        raise ValueError(
            "Cannot specify both 'format' and 'settings'. "
            "Use format for simple output control or settings for full control."
        )
    if preset is not None and settings is not None:
        raise ValueError(
            "Cannot specify both 'preset' and 'settings'. "
            "Use preset for quick setup or settings for full control."
        )
    if environment is not None and settings is not None:
        raise ValueError(
            "Cannot specify both 'environment' and 'settings'. "
            "Use environment for quick setup or settings for full control."
        )
    if environment is not None and preset is not None:
        raise ValueError(
            "Cannot specify both 'environment' and 'preset'. "
            "Use one or the other for configuration."
        )

    implicit_settings = settings is None and preset is None and environment is None

    # Apply preset if provided
    if preset is not None:
        from .core.presets import get_preset
        from .redaction import resolve_preset_fields

        preset_config = get_preset(preset)

        # Collect redaction presets to apply
        redaction_presets_to_apply: list[str] = []

        # Handle legacy _apply_credentials_preset marker
        if preset_config.pop("_apply_credentials_preset", False):
            redaction_presets_to_apply.append("CREDENTIALS")

        # Handle new _apply_redaction_presets list
        additional_presets = preset_config.pop("_apply_redaction_presets", [])
        redaction_presets_to_apply.extend(additional_presets)

        # Apply all collected redaction presets
        for redaction_preset_name in redaction_presets_to_apply:
            preset_fields, preset_patterns = resolve_preset_fields(
                redaction_preset_name
            )
            # Add fields with data. prefix
            prefixed_fields = [f"data.{f}" for f in preset_fields]

            # Merge into preset config
            redactor_config = preset_config.setdefault("redactor_config", {})
            field_mask_config = redactor_config.setdefault("field_mask", {})
            existing_fields = field_mask_config.setdefault("fields_to_mask", [])
            for f in prefixed_fields:
                if f not in existing_fields:
                    existing_fields.append(f)

            regex_mask_config = redactor_config.setdefault("regex_mask", {})
            existing_patterns = regex_mask_config.setdefault("patterns", [])
            for p in preset_patterns:
                if p not in existing_patterns:
                    existing_patterns.append(p)

        settings = _Settings(**preset_config)

    cfg_source = settings or _Settings()

    # Apply environment configuration (explicit or auto-detected)
    if environment is not None:
        from .core.environment import get_environment_config

        env_config = get_environment_config(environment)  # type: ignore[arg-type]
        cfg_source = _apply_environment_config(cfg_source, env_config)
    elif auto_detect and settings is None and preset is None:
        from .core.environment import detect_environment, get_environment_config

        detected_env = detect_environment()
        env_config = get_environment_config(detected_env)
        cfg_source = _apply_environment_config(cfg_source, env_config)

    cfg_source = _apply_default_log_level(cfg_source, preset=preset)
    fmt_input = format
    if fmt_input is None and implicit_settings:
        fmt_input = "auto"
    fmt = _resolve_format(fmt_input, cfg_source)
    if fmt:
        _apply_format(cfg_source, fmt)

    setup = _configure_logger_common(cfg_source, sinks)
    return setup, cfg_source


def _create_and_start_facade(
    facade_cls: type,
    name: str | None,
    setup: _LoggerSetup,
    enrichers: list[object],
    redactors: list[object],
    processors: list[object],
    filters: list[object],
) -> object:
    """Create a logger facade, apply extras, and start it."""
    cfg = setup.settings
    logger = facade_cls(
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


def get_logger(
    name: str | None = None,
    *,
    preset: str | None = None,
    format: _Literal["json", "pretty", "auto"] | None = None,
    settings: _Settings | None = None,
    sinks: list[object] | None = None,
    auto_detect: bool = True,
    environment: str | None = None,
    reuse: bool = True,
) -> _SyncLoggerFacade:
    """Return a sync logger with optional preset or output format controls.

    Args:
        name: Optional logger name. Loggers with the same name return the same
            cached instance by default (like stdlib logging.getLogger).
        preset: Built-in preset name (dev, production, fastapi, minimal).
        format: Output format ("json", "pretty", "auto"); defaults to auto when
            no settings are provided.
        settings: Explicit Settings object (mutually exclusive with preset/format).
        sinks: Custom sink instances (overrides configured sinks).
        auto_detect: Enable automatic environment detection (default True).
            When True, detects Lambda/Kubernetes/Docker/CI environments and
            applies appropriate configurations.
        environment: Explicit environment type override ("local", "docker",
            "kubernetes", "lambda", "ci"). Mutually exclusive with preset/settings.
        reuse: If True (default), return cached instance for this name.
            Set to False to create a new independent instance (useful for tests).

    Priority order (highest to lowest):
        1. Explicit settings parameter
        2. Explicit preset parameter
        3. Explicit environment parameter
        4. Auto-detection (if auto_detect=True)
        5. Story 10.6 defaults

    Note:
        Cached loggers persist for the application lifetime. For short-lived
        scripts, use `runtime()` context manager for automatic cleanup.
    """
    cache_key = name or _DEFAULT_LOGGER_KEY

    # Fast path: check cache without lock
    if reuse and cache_key in _sync_logger_cache:
        return _sync_logger_cache[cache_key]

    setup, _ = _prepare_logger(
        name,
        preset=preset,
        format=format,
        settings=settings,
        sinks=sinks,
        auto_detect=auto_detect,
        environment=environment,
    )

    enrichers, redactors, processors, filters = _start_plugins_sync(
        setup.enrichers,
        setup.redactors,
        setup.processors,
        setup.filters,
    )

    facade = _cast(
        _SyncLoggerFacade,
        _create_and_start_facade(
            _SyncLoggerFacade, name, setup, enrichers, redactors, processors, filters
        ),
    )

    if reuse:
        with _cache_lock:
            # Double-check pattern: another thread may have created it
            if cache_key in _sync_logger_cache:  # pragma: no cover - race condition
                # Drain ours, return existing (rare race condition)
                try:
                    coro = facade.stop_and_drain()
                    _asyncio.run(coro)
                except Exception:
                    with _suppress(Exception):
                        coro.close()
                return _sync_logger_cache[cache_key]
            _sync_logger_cache[cache_key] = facade

    return facade


async def get_async_logger(
    name: str | None = None,
    *,
    preset: str | None = None,
    format: _Literal["json", "pretty", "auto"] | None = None,
    settings: _Settings | None = None,
    sinks: list[object] | None = None,
    auto_detect: bool = True,
    environment: str | None = None,
    reuse: bool = True,
) -> _AsyncLoggerFacade:
    """Return an async logger with optional preset or output format controls.

    Args:
        name: Optional logger name. Loggers with the same name return the same
            cached instance by default (like stdlib logging.getLogger).
        preset: Built-in preset name (dev, production, fastapi, minimal).
        format: Output format ("json", "pretty", "auto"); defaults to auto when
            no settings are provided.
        settings: Explicit Settings object (mutually exclusive with preset/format).
        sinks: Custom sink instances (overrides configured sinks).
        auto_detect: Enable automatic environment detection (default True).
            When True, detects Lambda/Kubernetes/Docker/CI environments and
            applies appropriate configurations.
        environment: Explicit environment type override ("local", "docker",
            "kubernetes", "lambda", "ci"). Mutually exclusive with preset/settings.
        reuse: If True (default), return cached instance for this name.
            Set to False to create a new independent instance (useful for tests).

    Priority order (highest to lowest):
        1. Explicit settings parameter
        2. Explicit preset parameter
        3. Explicit environment parameter
        4. Auto-detection (if auto_detect=True)
        5. Story 10.6 defaults

    Note:
        Cached loggers persist for the application lifetime. For short-lived
        scripts, use `runtime_async()` context manager for automatic cleanup.
    """
    cache_key = name or _DEFAULT_LOGGER_KEY

    # Fast path: check cache without lock
    if reuse and cache_key in _async_logger_cache:
        return _async_logger_cache[cache_key]

    setup, _ = _prepare_logger(
        name,
        preset=preset,
        format=format,
        settings=settings,
        sinks=sinks,
        auto_detect=auto_detect,
        environment=environment,
    )

    enrichers = await _start_plugins(setup.enrichers, "enricher")
    redactors = await _start_plugins(setup.redactors, "redactor")
    processors = await _start_plugins(setup.processors, "processor")
    filters = await _start_plugins(setup.filters, "filter")

    facade = _cast(
        _AsyncLoggerFacade,
        _create_and_start_facade(
            _AsyncLoggerFacade, name, setup, enrichers, redactors, processors, filters
        ),
    )

    if reuse:
        with _cache_lock:
            # Double-check pattern: another coroutine may have created it
            if cache_key in _async_logger_cache:  # pragma: no cover - race condition
                # Another coroutine created it, drain ours and return theirs
                await facade.drain()
                return _async_logger_cache[cache_key]
            _async_logger_cache[cache_key] = facade

    return facade


@_asynccontextmanager
async def runtime_async(
    *, settings: _Settings | None = None
) -> _AsyncIterator[_AsyncLoggerFacade]:
    """Async context manager that initializes and drains the default async runtime.

    Uses reuse=False internally to ensure the logger is independent from the
    cache and can be safely drained without affecting other users of the
    default logger name.
    """
    logger = await get_async_logger(settings=settings, reuse=False)
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


def get_cached_loggers() -> dict[str, str]:
    """Return names of all cached loggers.

    Returns:
        Dict mapping cache keys to logger types ("async" or "sync").

    Example:
        >>> get_cached_loggers()
        {'my-service': 'async', 'other-service': 'sync'}
    """
    with _cache_lock:
        result: dict[str, str] = {}
        for key in _async_logger_cache:
            result[key] = "async"
        for key in _sync_logger_cache:
            result[key] = "sync"
        return result


async def clear_logger_cache() -> None:
    """Drain and remove all cached loggers.

    Useful for test cleanup or application shutdown. Drains all loggers
    to ensure clean shutdown of worker tasks before clearing the cache.

    Example:
        >>> await clear_logger_cache()
    """
    with _cache_lock:
        async_loggers = list(_async_logger_cache.values())
        sync_loggers = list(_sync_logger_cache.values())
        _async_logger_cache.clear()
        _sync_logger_cache.clear()

    # Drain outside lock to avoid deadlocks
    for async_logger in async_loggers:
        try:
            await async_logger.drain()
        except Exception:  # pragma: no cover - defensive
            pass

    for sync_logger in sync_loggers:
        try:
            await sync_logger.stop_and_drain()
        except Exception:  # pragma: no cover - defensive
            pass


# Version info for compatibility (injected by hatch-vcs at build time)
try:
    from ._version import __version__
except Exception:  # pragma: no cover - fallback for editable installs
    __version__ = "0.0.0+local"
__author__ = "Chris Haste"
__email__ = "chris@haste.dev"
VERSION = __version__
