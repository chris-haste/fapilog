"""Configuration builder functions extracted from __init__.py.

This module contains functions that build configuration dictionaries for
various plugin types (sinks, enrichers, redactors, filters, processors)
and the pipeline construction logic.

Story 5.25: Extract Config Builder Functions from __init__.py
"""

from __future__ import annotations

import os as _os
from pathlib import Path as _Path
from typing import Any as _Any
from typing import Callable as _Callable

from ..core.retry import RetryConfig as _RetryConfig
from ..core.settings import Settings as _Settings
from ..core.types import _parse_rotation_duration, _parse_size
from ..metrics.metrics import MetricsCollector as _MetricsCollector
from ..plugins.processors.size_guard import SizeGuardConfig as _SizeGuardConfig
from ..plugins.redactors.field_mask import FieldMaskConfig as _FieldMaskConfig
from ..plugins.redactors.regex_mask import RegexMaskConfig as _RegexMaskConfig
from ..plugins.redactors.url_credentials import (
    UrlCredentialsConfig as _UrlCredentialsConfig,
)
from ..plugins.sinks.contrib.cloudwatch import (
    CloudWatchSinkConfig as _CloudWatchSinkConfig,
)
from ..plugins.sinks.contrib.postgres import PostgresSinkConfig as _PostgresSinkConfig
from ..plugins.sinks.http_client import HttpSinkConfig as _HttpSinkConfig
from ..plugins.sinks.rotating_file import (
    RotatingFileSinkConfig as _RotatingFileSinkConfig,
)
from ..plugins.sinks.stdout_json import StdoutJsonSink as _StdoutJsonSink
from ..plugins.sinks.webhook import WebhookSinkConfig as _WebhookSinkConfig


def _normalize(name: str) -> str:
    """Normalize plugin name by replacing hyphens with underscores and lowercasing."""
    return name.replace("-", "_").lower()


def _sink_configs(settings: _Settings) -> dict[str, dict[str, _Any]]:
    """Build configuration dictionaries for all sink types.

    Args:
        settings: The application settings.

    Returns:
        Dictionary mapping sink names to their configuration dictionaries.
    """
    scfg = settings.sink_config
    configs: dict[str, dict[str, _Any]] = {
        "stdout_json": scfg.stdout_json,
        "stdout_pretty": {},
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
        "sealed": scfg.sealed.model_dump(exclude_none=True),
    }
    configs.update(scfg.extra)
    return configs


def _enricher_configs(settings: _Settings) -> dict[str, dict[str, _Any]]:
    """Build configuration dictionaries for all enricher types.

    Args:
        settings: The application settings.

    Returns:
        Dictionary mapping enricher names to their configuration dictionaries.
    """
    ecfg = settings.enricher_config
    cfg: dict[str, dict[str, _Any]] = {
        "runtime_info": ecfg.runtime_info,
        "context_vars": ecfg.context_vars,
        "integrity": ecfg.integrity.model_dump(exclude_none=True),
    }
    cfg.update(ecfg.extra)
    return cfg


def _redactor_configs(settings: _Settings) -> dict[str, dict[str, _Any]]:
    """Build configuration dictionaries for all redactor types.

    Args:
        settings: The application settings.

    Returns:
        Dictionary mapping redactor names to their configuration dictionaries.

    Note:
        Core guardrails (redaction_max_depth, redaction_max_keys_scanned) are
        passed to redactors that support them. These act as outer limits that
        override per-redactor settings when more restrictive.
    """
    rcfg = settings.redactor_config
    core = settings.core

    # Core guardrails to pass to redactors (None means no core override)
    core_max_depth = core.redaction_max_depth
    core_max_keys = core.redaction_max_keys_scanned

    cfg: dict[str, dict[str, _Any]] = {
        "field_mask": {
            "config": _FieldMaskConfig(**rcfg.field_mask.model_dump()),
            "core_max_depth": core_max_depth,
            "core_max_keys_scanned": core_max_keys,
        },
        "regex_mask": {
            "config": _RegexMaskConfig(**rcfg.regex_mask.model_dump()),
            "core_max_depth": core_max_depth,
            "core_max_keys_scanned": core_max_keys,
        },
        "url_credentials": {
            "config": _UrlCredentialsConfig(**rcfg.url_credentials.model_dump())
        },
    }
    cfg.update(rcfg.extra)
    return cfg


def _filter_configs(settings: _Settings) -> dict[str, dict[str, _Any]]:
    """Build configuration dictionaries for all filter types.

    Args:
        settings: The application settings.

    Returns:
        Dictionary mapping filter names to their configuration dictionaries.
    """
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
    """Build configuration dictionaries for all processor types.

    Args:
        settings: The application settings.
        metrics: Optional metrics collector to pass to size_guard processor.

    Returns:
        Dictionary mapping processor names to their configuration dictionaries.
    """
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
    """Determine default sink names based on settings and environment.

    Args:
        settings: The application settings.

    Returns:
        List of sink names to use as defaults.
    """
    if settings.http.endpoint:
        return ["http"]
    if _os.getenv("FAPILOG_FILE__DIRECTORY"):
        return ["rotating_file"]
    return ["stdout_json"]


def _default_env_sink_cfg(name: str) -> dict[str, _Any]:
    """Build default sink configuration from environment variables.

    Args:
        name: The sink name to build configuration for.

    Returns:
        Configuration dictionary for the sink, or empty dict if not supported.
    """
    if name == "rotating_file":
        max_bytes_raw = _os.getenv("FAPILOG_FILE__MAX_BYTES", "10485760")
        interval_raw = _os.getenv("FAPILOG_FILE__INTERVAL_SECONDS", "0")
        max_total_raw = _os.getenv("FAPILOG_FILE__MAX_TOTAL_BYTES", "0")
        interval_value = _parse_rotation_duration(interval_raw)
        max_bytes_value = _parse_size(max_bytes_raw)
        if max_bytes_value is None:
            max_bytes_value = 10 * 1024 * 1024
        max_total_value = _parse_size(max_total_raw)
        return {
            "config": _RotatingFileSinkConfig(
                directory=_Path(_os.getenv("FAPILOG_FILE__DIRECTORY", ".")),
                filename_prefix=_os.getenv("FAPILOG_FILE__FILENAME_PREFIX", "fapilog"),
                mode=_os.getenv("FAPILOG_FILE__MODE", "json"),
                max_bytes=max_bytes_value,
                interval_seconds=(
                    interval_value if interval_value and interval_value > 0 else None
                ),
                max_files=(int(_os.getenv("FAPILOG_FILE__MAX_FILES", "0")) or None),
                max_total_bytes=(
                    max_total_value if max_total_value and max_total_value > 0 else None
                ),
                compress_rotated=_os.getenv(
                    "FAPILOG_FILE__COMPRESS_ROTATED", "false"
                ).lower()
                in {"1", "true", "yes"},
            )
        }
    return {}


def _build_pipeline(
    settings: _Settings,
    load_plugins: _Callable[
        [str, list[str], _Settings, dict[str, dict[str, _Any]]], list[object]
    ],
) -> tuple[
    list[object],
    list[object],
    list[object],
    list[object],
    list[object],
    _MetricsCollector | None,
]:
    """Build the complete logging pipeline from settings.

    Args:
        settings: The application settings.
        load_plugins: Callable to load plugins by group name. Signature:
            (group: str, names: list[str], settings: Settings, cfgs: dict) -> list[object]

    Returns:
        Tuple of (sinks, enrichers, redactors, processors, filters, metrics).
    """
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
    sinks = load_plugins("fapilog.sinks", sink_names, settings, sink_cfgs)
    if not sinks:
        sinks = [_StdoutJsonSink()]

    enricher_names = list(core_cfg.enrichers or [])
    enrichers = load_plugins(
        "fapilog.enrichers", enricher_names, settings, _enricher_configs(settings)
    )

    # Use redactors from settings directly. Settings now defaults to ["url_credentials"]
    # for secure defaults. Empty list means explicit opt-out - no fallback needed.
    redactor_names = list(core_cfg.redactors) if core_cfg.enable_redactors else []
    redactors = load_plugins(
        "fapilog.redactors", redactor_names, settings, _redactor_configs(settings)
    )

    processor_names = list(core_cfg.processors or [])
    processors = load_plugins(
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

    filters = load_plugins(
        "fapilog.filters",
        filter_names,
        settings,
        filter_cfgs,
    )

    return sinks, enrichers, redactors, processors, filters, metrics
