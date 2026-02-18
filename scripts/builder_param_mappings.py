"""Registry of builder parameter to settings field mappings.

This file serves as:
1. Documentation of all param name translations
2. Source of truth for parity checking
3. Reference for implementers adding new settings

Maintained manually; validated by pre-commit hook.
"""

from __future__ import annotations

# === EXCLUSIONS (with rationale) ===

CORE_EXCLUSIONS: set[str] = {
    "schema_version",  # Internal versioning, not user-configurable
    "benchmark_file_path",  # Test-only field
    "sensitive_fields_policy",  # Policy hint, not runtime config
    "redactors_order",  # Managed internally by redactor methods
    "enable_redactors",  # Controlled via redactor list being non-empty
    "processors",  # Managed internally, not directly set by builder
    "sinks",  # Managed by add_* sink methods
}

SINK_EXCLUSIONS: set[str] = {
    "model_config",  # Pydantic internal
}


# === CORE SETTINGS COVERAGE ===
# Maps builder method -> list of CoreSettings fields it covers

CORE_COVERAGE: dict[str, list[str]] = {
    "with_level": ["log_level"],
    "with_queue_size": ["max_queue_size", "protected_queue_size"],
    "with_queue_budget": ["max_queue_size", "protected_queue_size"],
    "with_batch_size": ["batch_max_size"],
    "with_batch_timeout": ["batch_timeout_seconds"],
    "with_context": ["default_bound_context"],
    "with_enrichers": ["enrichers"],
    "with_filters": ["filters"],
    "with_redaction": ["redactors"],
    "with_circuit_breaker": [
        "sink_circuit_breaker_enabled",
        "sink_circuit_breaker_failure_threshold",
        "sink_circuit_breaker_recovery_timeout_seconds",
        "sink_circuit_breaker_fallback_sink",
    ],
    "with_backpressure": ["backpressure_wait_ms", "drop_on_full"],
    "with_protected_levels": ["protected_levels"],
    "with_workers": ["worker_count"],
    "with_shutdown_timeout": ["shutdown_timeout_seconds"],
    "with_exceptions": [
        "exceptions_enabled",
        "exceptions_max_frames",
        "exceptions_max_stack_chars",
    ],
    "with_parallel_sink_writes": ["sink_parallel_writes"],
    "with_sink_concurrency": ["sink_concurrency"],
    "with_metrics": ["enable_metrics"],
    "with_error_deduplication": [
        "error_dedupe_window_seconds",
        "error_dedupe_max_entries",
        "error_dedupe_ttl_multiplier",
    ],
    "with_drop_summary": ["emit_drop_summary", "drop_summary_window_seconds"],
    "with_diagnostics": ["internal_logging_enabled", "diagnostics_output"],
    "with_app_name": ["app_name"],
    "with_strict_mode": ["strict_envelope_mode"],
    "with_unhandled_exception_capture": ["capture_unhandled_enabled"],
    "with_context_binding": ["context_binding_enabled"],
    "with_serialize_in_flush": ["serialize_in_flush"],
    "with_resource_pool": [
        "resource_pool_max_size",
        "resource_pool_acquire_timeout_seconds",
    ],
    "with_redaction_guardrails": [
        "redaction_max_depth",
        "redaction_max_keys_scanned",
    ],
    "with_fallback_redaction": [
        "fallback_redact_mode",
        "redaction_fail_mode",
        "fallback_scrub_raw",
        "fallback_raw_max_bytes",
    ],
    # Adaptive pipeline (Story 10.57)
    "with_adaptive": [
        "enabled",
        "check_interval_seconds",
        "cooldown_seconds",
        "escalate_to_elevated",
        "escalate_to_high",
        "escalate_to_critical",
        "deescalate_from_critical",
        "deescalate_from_high",
        "deescalate_from_elevated",
        "batch_sizing",
        "max_workers",
        "circuit_pressure_boost",
        "filter_tightening",
        "worker_scaling",
    ],
    # Graceful shutdown (Story 6.13)
    "with_atexit_drain": ["atexit_drain_enabled", "atexit_drain_timeout_seconds"],
    "with_signal_handlers": ["signal_handler_enabled"],
    "with_flush_on_critical": ["flush_on_critical"],
}


# === SINK PARAMETER MAPPINGS ===
# Maps builder param name -> settings field name

SINK_PARAM_MAPPINGS: dict[str, dict[str, str]] = {
    "add_cloudwatch": {
        # Builder param: Settings field
        "log_group": "log_group_name",
        "stream": "log_stream_name",
        "region": "region",
        "endpoint_url": "endpoint_url",
        "batch_size": "batch_size",
        "batch_timeout": "batch_timeout_seconds",
        "max_retries": "max_retries",
        "retry_delay": "retry_base_delay",
        "create_group": "create_log_group",
        "create_stream": "create_log_stream",
        "circuit_breaker": "circuit_breaker_enabled",
        "circuit_breaker_threshold": "circuit_breaker_threshold",
    },
    "add_loki": {
        "url": "url",
        "tenant_id": "tenant_id",
        "labels": "labels",
        "label_keys": "label_keys",
        "batch_size": "batch_size",
        "batch_timeout": "batch_timeout_seconds",
        "timeout": "timeout_seconds",
        "max_retries": "max_retries",
        "retry_delay": "retry_base_delay",
        "auth_username": "auth_username",
        "auth_password": "auth_password",
        "auth_token": "auth_token",
        "circuit_breaker": "circuit_breaker_enabled",
        "circuit_breaker_threshold": "circuit_breaker_threshold",
    },
    "add_postgres": {
        "dsn": "dsn",
        "host": "host",
        "port": "port",
        "database": "database",
        "user": "user",
        "password": "password",
        "table": "table_name",
        "schema": "schema_name",
        "batch_size": "batch_size",
        "batch_timeout": "batch_timeout_seconds",
        "max_retries": "max_retries",
        "retry_delay": "retry_base_delay",
        "min_pool": "min_pool_size",
        "max_pool": "max_pool_size",
        "pool_acquire_timeout": "pool_acquire_timeout",
        "create_table": "create_table",
        "use_jsonb": "use_jsonb",
        "include_raw_json": "include_raw_json",
        "extract_fields": "extract_fields",
        "circuit_breaker": "circuit_breaker_enabled",
        "circuit_breaker_threshold": "circuit_breaker_threshold",
    },
}


# === FILTER COVERAGE ===
# Maps filter type -> builder method that covers it

FILTER_COVERAGE: dict[str, str] = {
    "sampling": "with_sampling",
    "rate_limit": "with_rate_limit",
    "adaptive_sampling": "with_adaptive_sampling",
    "trace_sampling": "with_trace_sampling",
    "first_occurrence": "with_first_occurrence",
}


# === FILTER PARAMETER MAPPINGS ===
# Maps builder param name -> plugin config field name
# Story 12.28: Added to document param-to-field translations

FILTER_PARAM_MAPPINGS: dict[str, dict[str, str]] = {
    "with_sampling": {
        "rate": "sample_rate",
        "seed": "seed",
    },
    "with_adaptive_sampling": {
        # Builder uses human-friendly names, plugin uses abbreviated field names
        "min_rate": "min_sample_rate",
        "max_rate": "max_sample_rate",
        "target_events_per_sec": "target_eps",
        "window_seconds": "window_seconds",
    },
    "with_trace_sampling": {
        # Builder param 'default_rate' maps to plugin field 'sample_rate'
        "default_rate": "sample_rate",
        # Note: honor_upstream was removed (not in TraceSamplingConfig)
    },
    "with_rate_limit": {
        "capacity": "capacity",
        "refill_rate": "refill_rate_per_sec",
        "key_field": "key_field",
        "max_keys": "max_keys",
        "overflow_action": "overflow_action",
    },
    "with_first_occurrence": {
        "window_seconds": "window_seconds",
        "max_keys": "max_keys",
        "key_fields": "key_fields",
    },
}


# === PROCESSOR COVERAGE ===
# Maps processor -> param:field mappings

PROCESSOR_COVERAGE: dict[str, dict[str, str]] = {
    "size_guard": {
        "max_bytes": "max_bytes",
        "action": "action",
        "preserve_fields": "preserve_fields",
    },
}


# === ADVANCED COVERAGE ===
# Maps method -> param:field for routing, redactors, plugins

ADVANCED_COVERAGE: dict[str, dict[str, str]] = {
    "with_routing": {
        "rules": "rules",
        "fallback": "fallback_sinks",
        "overlap": "overlap",
    },
    # Unified redaction API covers all redaction functionality
    "with_redaction": {
        "preset": "(resolves to fields_to_mask, patterns)",
        "fields": "fields_to_mask",
        "patterns": "patterns",
        "mask": "mask_string",
        "url_credentials": "(url_credentials redactor)",
        "url_max_length": "max_string_length",
        "block_on_failure": "block_on_unredactable",
        "block_fields": "blocked_fields",
        "max_string_length": "max_string_length (string_truncate redactor)",
        "max_depth": "redaction_max_depth",
        "max_keys": "redaction_max_keys_scanned",
        "auto_prefix": "(applies data. prefix to fields)",
        "replace": "(controls additive vs replace behavior)",
    },
    "with_plugins": {
        "enabled": "enabled",
        "allow_external": "allow_external",
        "allowlist": "allowlist",
        "denylist": "denylist",
        "validation_mode": "validation_mode",
    },
}
