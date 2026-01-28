"""
Async-first configuration models for Fapilog v3 using Pydantic v2 Settings.

This module defines the public configuration schema and provides
async-aware validation hooks used by the loader in `config.py`.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import (  # type: ignore[import-not-found]
    BaseSettings,
    SettingsConfigDict,
)

from .observability import (
    ObservabilitySettings,
    validate_observability,
)
from .security import (
    SecuritySettings,
    validate_security,
)
from .types import (
    DurationField,
    OptionalDurationField,
    OptionalRotationDurationField,
    OptionalSizeField,
    SizeField,
    _parse_duration,
    _parse_size,
)
from .validation import ensure_path_exists


class EnvFieldType(Enum):
    """Type hints for environment variable value conversion."""

    STRING = "string"
    INT = "int"
    BOOL = "bool"
    FLOAT = "float"
    DURATION = "duration"
    LIST = "list"
    SIZE = "size"
    DICT = "dict"
    ENUM = "enum"
    ROUTING_RULES = "routing_rules"


def _convert_env_value(
    value: str,
    field_type: EnvFieldType,
    allowed_values: set[str] | None = None,
) -> Any:
    """Convert a string environment variable value to the target type.

    Args:
        value: The raw string value from the environment.
        field_type: The target type to convert to.
        allowed_values: For ENUM type, the set of allowed values.

    Returns:
        The converted value, or None if conversion fails.
    """
    try:
        if field_type == EnvFieldType.STRING:
            return value

        if field_type == EnvFieldType.INT:
            return int(value)

        if field_type == EnvFieldType.FLOAT:
            return float(value)

        if field_type == EnvFieldType.BOOL:
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            return None

        if field_type == EnvFieldType.DURATION:
            return _parse_duration(value)

        if field_type == EnvFieldType.SIZE:
            return _parse_size(value)

        if field_type == EnvFieldType.LIST:
            # Try JSON first
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed]
            except Exception:
                pass
            # Fall back to CSV parsing
            stripped = value.strip()
            if not stripped:
                return []
            return [v for v in (item.strip() for item in stripped.split(",")) if v]

        if field_type == EnvFieldType.DICT:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
            return None

        if field_type == EnvFieldType.ENUM:
            if allowed_values is None:
                return None
            normalized = value.strip().lower()
            if normalized in allowed_values:
                return normalized
            return None

        if field_type == EnvFieldType.ROUTING_RULES:
            # Import here to avoid circular dependency
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [
                    RoutingRule.model_validate(item)
                    for item in parsed
                    if isinstance(item, dict)
                ]
            return None

    except Exception:
        return None


def _apply_env_aliases(
    target: BaseModel,
    field_map: dict[str, tuple[str, EnvFieldType] | tuple[str, EnvFieldType, set[str]]],
) -> None:
    """Apply environment variable overrides to a Pydantic model.

    Args:
        target: The Pydantic model instance to modify.
        field_map: A mapping of field names to (env_var_name, field_type) tuples.
            For ENUM types, a third element contains the allowed values.
    """
    for field_name, field_spec in field_map.items():
        env_var = field_spec[0]
        field_type = field_spec[1]
        allowed_values = field_spec[2] if len(field_spec) > 2 else None  # type: ignore[misc]

        value = os.getenv(env_var)
        if value is None:
            continue

        converted = _convert_env_value(value, field_type, allowed_values)  # type: ignore[arg-type]
        if converted is not None:
            setattr(target, field_name, converted)


class RotatingFileSettings(BaseModel):
    """Per-plugin configuration for RotatingFileSink."""

    directory: str | None = Field(
        default=None, description="Log directory for rotating file sink"
    )
    filename_prefix: str = Field(default="fapilog", description="Filename prefix")
    mode: Literal["json", "text"] = Field(
        default="json", description="Output format: json or text"
    )
    max_bytes: SizeField = Field(
        default=10 * 1024 * 1024,
        ge=1,
        description="Max bytes before rotation. Accepts '10 MB' or 10485760",
    )
    interval_seconds: OptionalRotationDurationField = Field(
        default=None,
        description="Rotation interval. Accepts '1h', 'daily', or 3600",
    )
    max_files: int | None = Field(
        default=None, description="Max number of rotated files to keep"
    )
    max_total_bytes: OptionalSizeField = Field(
        default=None,
        description="Max total bytes across all rotated files. Accepts '100 MB' or 104857600",
    )
    compress_rotated: bool = Field(
        default=False, description="Compress rotated log files with gzip"
    )


class WebhookSettings(BaseModel):
    """Per-plugin configuration for WebhookSink."""

    endpoint: str | None = Field(default=None, description="Webhook destination URL")
    secret: str | None = Field(default=None, description="Shared secret for signing")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Additional HTTP headers"
    )
    retry_max_attempts: int | None = Field(
        default=None, ge=1, description="Maximum retry attempts on failure"
    )
    retry_backoff_seconds: OptionalDurationField = Field(
        default=None,
        gt=0.0,
        description="Backoff between retries. Accepts '2s' or 2.0",
    )
    timeout_seconds: DurationField = Field(
        default=5.0,
        gt=0.0,
        description="Request timeout. Accepts '5s' or 5.0",
    )
    batch_size: int = Field(
        default=1,
        ge=1,
        description="Maximum events per webhook request (1 = no batching)",
    )
    batch_timeout_seconds: DurationField = Field(
        default=5.0,
        gt=0.0,
        description="Max seconds before flushing a partial webhook batch. Accepts '5s' or 5.0",
    )


class SealedSinkSettings(BaseModel):
    """Standard configuration for the tamper-evident sealed sink."""

    inner_sink: str = Field(
        default="rotating_file", description="Inner sink to wrap with sealing"
    )
    inner_config: dict[str, Any] = Field(
        default_factory=dict, description="Configuration for the inner sink"
    )
    manifest_path: str | None = Field(
        default=None, description="Directory where manifests are written"
    )
    sign_manifests: bool = Field(
        default=True, description="Sign manifests when keys are available"
    )
    key_id: str | None = Field(
        default=None, description="Optional override for signing key identifier"
    )
    key_provider: str | None = Field(
        default="env", description="Key provider for manifest signing"
    )
    chain_state_path: str | None = Field(
        default=None, description="Directory to persist chain state"
    )
    rotate_chain: bool = Field(
        default=False, description="Reset chain state on rotation"
    )
    fsync_on_write: bool = Field(
        default=False, description="Fsync inner sink on every write"
    )
    fsync_on_rotate: bool = Field(
        default=True, description="Fsync inner sink after rotation"
    )
    compress_rotated: bool = Field(
        default=False, description="Compress rotated files after sealing"
    )
    use_kms_signing: bool = Field(
        default=False, description="Sign manifests via external KMS provider"
    )


class CloudWatchSinkSettings(BaseModel):
    """Configuration for the CloudWatch sink."""

    log_group_name: str = Field(
        default="/fapilog/default", description="CloudWatch log group name"
    )
    log_stream_name: str | None = Field(
        default=None, description="CloudWatch log stream name"
    )
    region: str | None = Field(
        default=None, description="AWS region for CloudWatch Logs API calls"
    )
    create_log_group: bool = Field(
        default=True, description="Create log group if missing"
    )
    create_log_stream: bool = Field(
        default=True, description="Create log stream if missing"
    )
    batch_size: int = Field(default=100, ge=1, le=10000, description="Events per batch")
    batch_timeout_seconds: DurationField = Field(
        default=5.0,
        gt=0,
        description="Max seconds before flushing a partial batch. Accepts '5s' or 5.0",
    )
    endpoint_url: str | None = Field(
        default=None, description="Custom endpoint (e.g., LocalStack)"
    )
    max_retries: int = Field(
        default=3, ge=1, description="Max retries for PutLogEvents"
    )
    retry_base_delay: DurationField = Field(
        default=0.5,
        gt=0,
        description="Base delay for exponential backoff. Accepts '1s' or 0.5",
    )
    circuit_breaker_enabled: bool = Field(
        default=True, description="Enable internal circuit breaker for CloudWatch sink"
    )
    circuit_breaker_threshold: int = Field(
        default=5, ge=1, description="Failures before opening circuit"
    )


class LokiSinkSettings(BaseModel):
    """Configuration for Grafana Loki sink."""

    model_config = ConfigDict(extra="forbid", validate_default=True)

    url: str = Field(
        default="http://localhost:3100", description="Loki push endpoint base URL"
    )
    tenant_id: str | None = Field(
        default=None, description="Optional multi-tenant identifier"
    )
    labels: dict[str, str] = Field(
        default_factory=lambda: {"service": "fapilog"},
        description="Static labels to apply to each log stream",
    )
    label_keys: list[str] = Field(
        default_factory=lambda: ["level"],
        description="Event keys to promote to labels",
    )
    batch_size: int = Field(default=100, ge=1, description="Events per batch")
    batch_timeout_seconds: DurationField = Field(
        default=5.0,
        gt=0,
        description="Max seconds before flushing a partial batch. Accepts '5s' or 5.0",
    )
    timeout_seconds: DurationField = Field(
        default=10.0,
        gt=0,
        description="HTTP timeout seconds. Accepts '10s' or 10.0",
    )
    max_retries: int = Field(default=3, ge=1, description="Max retries on push failure")
    retry_base_delay: DurationField = Field(
        default=0.5,
        gt=0,
        description="Base delay for backoff. Accepts '1s' or 0.5",
    )
    auth_username: str | None = Field(default=None, description="Basic auth username")
    auth_password: str | None = Field(default=None, description="Basic auth password")
    auth_token: str | None = Field(default=None, description="Bearer token for Loki")
    circuit_breaker_enabled: bool = Field(
        default=True, description="Enable circuit breaker for the Loki sink"
    )
    circuit_breaker_threshold: int = Field(
        default=5, ge=1, description="Failures before opening circuit"
    )


class PostgresSinkSettings(BaseModel):
    """Configuration for PostgreSQL sink."""

    model_config = ConfigDict(extra="forbid", validate_default=True)

    dsn: str | None = Field(default=None, description="PostgreSQL connection string")
    host: str = Field(
        default="localhost", description="PostgreSQL server hostname or IP address"
    )
    port: int = Field(default=5432, ge=1, description="PostgreSQL server port number")
    database: str = Field(
        default="fapilog", description="PostgreSQL database name to connect to"
    )
    user: str = Field(
        default="fapilog", description="PostgreSQL username for authentication"
    )
    password: str | None = Field(default=None, description="Database password")
    table_name: str = Field(default="logs", description="Target table name")
    schema_name: str = Field(default="public", description="Database schema name")
    create_table: bool = Field(default=True, description="Auto-create table if missing")
    min_pool_size: int = Field(default=2, ge=1, description="Minimum pool connections")
    max_pool_size: int = Field(default=10, ge=1, description="Maximum pool connections")
    pool_acquire_timeout: DurationField = Field(
        default=10.0,
        gt=0.0,
        description="Timeout when acquiring connections. Accepts '10s' or 10.0",
    )
    batch_size: int = Field(default=100, ge=1, description="Events per batch")
    batch_timeout_seconds: DurationField = Field(
        default=5.0,
        gt=0,
        description="Max seconds before flushing a partial batch. Accepts '5s' or 5.0",
    )
    max_retries: int = Field(
        default=3, ge=0, description="Maximum retries for failed inserts"
    )
    retry_base_delay: DurationField = Field(
        default=0.5,
        ge=0.0,
        description="Base delay for exponential backoff. Accepts '1s' or 0.5",
    )
    circuit_breaker_enabled: bool = Field(
        default=True, description="Enable circuit breaker for the PostgreSQL sink"
    )
    circuit_breaker_threshold: int = Field(
        default=5, ge=1, description="Failures before opening circuit breaker"
    )
    use_jsonb: bool = Field(default=True, description="Use JSONB column type")
    include_raw_json: bool = Field(
        default=True, description="Store full event JSON payload"
    )
    extract_fields: list[str] = Field(
        default_factory=lambda: [
            "timestamp",
            "level",
            "logger",
            "correlation_id",
            "message",
        ],
        description="Fields to promote to columns for fast queries",
    )


class RoutingRule(BaseModel):
    """A routing rule mapping levels to sinks."""

    levels: list[str] = Field(default_factory=list, description="Levels to match")
    sinks: list[str] = Field(default_factory=list, description="Target sink names")

    @field_validator("levels")
    @classmethod
    def _normalize_levels(cls, value: list[str]) -> list[str]:
        return [lvl.upper() for lvl in value]


class SinkRoutingSettings(BaseModel):
    """Configuration for level-based sink routing."""

    enabled: bool = Field(
        default=False, description="Enable routing (False = fanout to all sinks)"
    )
    rules: list[RoutingRule] = Field(
        default_factory=list, description="Routing rules in priority order"
    )
    overlap: bool = Field(
        default=True, description="Allow events to match multiple rules"
    )
    fallback_sinks: list[str] = Field(
        default_factory=list, description="Sinks used when no rules match"
    )

    @field_validator("fallback_sinks", mode="before")
    @classmethod
    def _coerce_fallback(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed]
            except Exception:
                pass
            return [v for v in (item.strip() for item in value.split(",")) if v]
        return []


class IntegrityEnricherSettings(BaseModel):
    """Standard configuration for the tamper-evident integrity enricher."""

    algorithm: Literal["sha256", "ed25519"] = Field(
        default="sha256", description="MAC or signature algorithm"
    )
    key_id: str | None = Field(
        default=None, description="Key identifier used for MAC/signature"
    )
    key_provider: str | None = Field(
        default="env", description="Key provider for MAC/signature"
    )
    chain_state_path: str | None = Field(
        default=None, description="Directory to persist chain state"
    )
    rotate_chain: bool = Field(default=False, description="Reset chain after rotation")
    use_kms_signing: bool = Field(
        default=False, description="Sign integrity hashes via KMS provider"
    )


class RedactorFieldMaskSettings(BaseModel):
    """Per-plugin configuration for FieldMaskRedactor."""

    fields_to_mask: list[str] = Field(
        default_factory=list, description="Field names to mask (case-insensitive)"
    )
    mask_string: str = Field(default="***", description="Replacement mask string")
    block_on_unredactable: bool = Field(
        default=False, description="Block log entry if redaction fails"
    )
    max_depth: int = Field(default=16, ge=1, description="Max nested depth to scan")
    max_keys_scanned: int = Field(
        default=1000, ge=1, description="Max keys to scan before stopping"
    )


class RedactorRegexMaskSettings(BaseModel):
    """Per-plugin configuration for RegexMaskRedactor."""

    patterns: list[str] = Field(
        default_factory=list, description="Regex patterns to match and mask"
    )
    mask_string: str = Field(default="***", description="Replacement mask string")
    block_on_unredactable: bool = Field(
        default=False, description="Block log entry if redaction fails"
    )
    max_depth: int = Field(default=16, ge=1, description="Max nested depth to scan")
    max_keys_scanned: int = Field(
        default=1000, ge=1, description="Max keys to scan before stopping"
    )


class RedactorUrlCredentialsSettings(BaseModel):
    """Per-plugin configuration for UrlCredentialsRedactor."""

    max_string_length: int = Field(
        default=4096, ge=1, description="Max string length to parse for URL credentials"
    )


class SizeGuardSettings(BaseModel):
    """Per-plugin configuration for SizeGuardProcessor."""

    max_bytes: SizeField = Field(
        default=256000,
        ge=100,
        description="Maximum payload size in bytes (min 100). Accepts '1 MB' or 1048576",
    )
    action: Literal["truncate", "drop", "warn"] = Field(
        default="truncate", description="Action to take when payload exceeds max_bytes"
    )
    preserve_fields: list[str] = Field(
        default_factory=lambda: ["level", "timestamp", "logger", "correlation_id"],
        description="Fields that should never be removed during truncation",
    )


class ProcessorConfigSettings(BaseModel):
    """Per-processor configuration for built-in and third-party processors."""

    zero_copy: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration for zero_copy processor (reserved for future options)",
    )
    size_guard: SizeGuardSettings = Field(
        default_factory=SizeGuardSettings,
        description="Configuration for size_guard processor",
    )
    extra: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Configuration for third-party processors by name",
    )


# Keep explicit version to allow schema gating and forward migrations later
LATEST_CONFIG_SCHEMA_VERSION = "1.0"


class CoreSettings(BaseModel):
    """Core logging and performance settings.

    Keep this minimal and stable; prefer plugin-specific settings elsewhere.
    """

    app_name: str = Field(
        default="fapilog",
        description="Logical application name",
    )
    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
    ] = Field(
        default="INFO",
        description="Default log level",
    )
    max_queue_size: int = Field(
        default=10_000,
        ge=1,
        description=("Maximum in-memory queue size for async processing"),
    )
    batch_max_size: int = Field(
        default=256,
        ge=1,
        description=("Maximum number of events per batch before a flush is triggered"),
    )
    batch_timeout_seconds: float = Field(
        default=0.25,
        gt=0.0,
        description=("Maximum time to wait before flushing a partial batch"),
    )
    backpressure_wait_ms: int = Field(
        default=50,
        ge=0,
        description=("Milliseconds to wait for queue space before dropping"),
    )
    drop_on_full: bool = Field(
        default=True,
        description=(
            "If True, drop events after backpressure_wait_ms elapses when queue is full"
        ),
    )
    enable_metrics: bool = Field(
        default=False,
        description=("Enable Prometheus-compatible metrics"),
    )
    # Context binding feature toggles
    context_binding_enabled: bool = Field(
        default=True,
        description=("Enable per-task bound context via logger.bind/unbind/clear"),
    )
    default_bound_context: dict[str, object] = Field(
        default_factory=dict,
        description=("Default bound context applied at logger creation when enabled"),
    )
    # Structured internal diagnostics (worker/sink/metrics)
    internal_logging_enabled: bool = Field(
        default=False,
        description=("Emit DEBUG/WARN diagnostics for internal errors"),
    )
    diagnostics_output: Literal["stderr", "stdout"] = Field(
        default="stderr",
        description=(
            "Output stream for internal diagnostics: stderr (default, Unix convention)"
            " or stdout (backward compat)"
        ),
    )
    # Error deduplication window
    error_dedupe_window_seconds: float = Field(
        default=5.0,
        ge=0.0,
        description=(
            "Seconds to suppress duplicate ERROR logs with the same"
            " message; 0 disables deduplication"
        ),
    )
    # Shutdown behavior
    shutdown_timeout_seconds: float = Field(
        default=3.0,
        gt=0.0,
        description=("Maximum time to flush on shutdown signals"),
    )
    worker_count: int = Field(
        default=1,
        ge=1,
        description=("Number of worker tasks for flush processing"),
    )
    # Optional policy hint to encourage enabling redaction
    sensitive_fields_policy: list[str] = Field(
        default_factory=list,
        description=(
            "Optional list of dotted paths for sensitive fields policy;"
            " warning if no redactors configured"
        ),
    )
    # Redactors stage toggles and guardrails
    enable_redactors: bool = Field(
        default=True,
        description=("Enable redactors stage between enrichers and sink emission"),
    )
    redactors_order: list[str] = Field(
        default_factory=lambda: [
            "field-mask",
            "regex-mask",
            "url-credentials",
        ],
        description=("Ordered list of redactor plugin names to apply"),
    )
    # Plugin selection (new) — canonical lists; empty list disables stage
    sinks: list[str] = Field(
        default_factory=list,
        description=(
            "Sink plugins to use (by name); falls back to env-based default when empty"
        ),
    )
    enrichers: list[str] = Field(
        default_factory=lambda: ["runtime_info", "context_vars"],
        description=("Enricher plugins to use (by name)"),
    )
    redactors: list[str] = Field(
        default_factory=lambda: ["url_credentials"],
        description=(
            "Redactor plugins to use (by name); "
            "defaults to ['url_credentials'] for secure defaults; "
            "set to [] to disable all redaction"
        ),
    )
    processors: list[str] = Field(
        default_factory=list,
        description=("Processor plugins to use (by name)"),
    )
    filters: list[str] = Field(
        default_factory=list,
        description=("Filter plugins to apply before enrichment (by name)"),
    )
    redaction_max_depth: int | None = Field(
        default=6,
        ge=1,
        description=("Optional max depth guardrail for nested redaction"),
    )
    redaction_max_keys_scanned: int | None = Field(
        default=5000,
        ge=1,
        description=("Optional max keys scanned guardrail for redaction"),
    )
    # Exceptions and traceback serialization
    exceptions_enabled: bool = Field(
        default=True,
        description=("Enable structured exception serialization for log calls"),
    )
    exceptions_max_frames: int = Field(
        default=10,
        ge=1,
        description=("Maximum number of stack frames to capture for exceptions"),
    )
    exceptions_max_stack_chars: int = Field(
        default=20000,
        ge=1000,
        description=("Maximum total characters for serialized stack string"),
    )
    # Envelope strict mode
    strict_envelope_mode: bool = Field(
        default=False,
        description=(
            "If True, drop emission when envelope cannot be"
            " produced; otherwise fallback to best-effort"
            " serialization with diagnostics"
        ),
    )
    capture_unhandled_enabled: bool = Field(
        default=False,
        description=("Automatically install unhandled exception hooks (sys/asyncio)"),
    )
    # Fast-path serialization: serialize once in flush and pass to sinks
    serialize_in_flush: bool = Field(
        default=False,
        description=(
            "If True, pre-serialize envelopes once during flush and pass"
            " SerializedView to sinks that support write_serialized"
        ),
    )
    # Resource pool defaults (can be overridden per pool at construction)
    resource_pool_max_size: int = Field(
        default=8,
        ge=1,
        description=("Default max size for resource pools"),
    )
    resource_pool_acquire_timeout_seconds: float = Field(
        default=2.0,
        gt=0.0,
        description=("Default acquire timeout for pools"),
    )
    # Sink fault isolation and circuit breaker
    sink_circuit_breaker_enabled: bool = Field(
        default=False,
        description=("Enable circuit breaker for sink fault isolation"),
    )
    sink_circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        description=("Number of consecutive failures before opening circuit"),
    )
    sink_circuit_breaker_recovery_timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description=("Seconds to wait before probing a failed sink"),
    )
    sink_parallel_writes: bool = Field(
        default=False,
        description=("Write to multiple sinks in parallel instead of sequentially"),
    )
    # Fallback PII protection (Story 4.46)
    fallback_redact_mode: Literal["inherit", "minimal", "none"] = Field(
        default="minimal",
        description=(
            "Redaction mode for fallback stderr output: "
            "'inherit' uses pipeline redactors, "
            "'minimal' applies built-in sensitive field masking, "
            "'none' writes unredacted (opt-in to legacy behavior)"
        ),
    )
    # Redaction fail mode (Story 4.54, updated Story 4.61)
    redaction_fail_mode: Literal["open", "closed", "warn"] = Field(
        default="warn",
        description=(
            "Behavior when _apply_redactors() catches an unexpected exception: "
            "'open' passes original event, "
            "'closed' drops the event, "
            "'warn' (default) passes event but emits diagnostic warning"
        ),
    )
    # Graceful shutdown settings (Story 6.13)
    atexit_drain_enabled: bool = Field(
        default=True,
        description=(
            "Register atexit handler to drain pending logs on normal process exit"
        ),
    )
    atexit_drain_timeout_seconds: float = Field(
        default=2.0,
        gt=0.0,
        description=("Maximum seconds to wait for log drain during atexit handler"),
    )
    signal_handler_enabled: bool = Field(
        default=True,
        description=(
            "Install signal handlers for SIGTERM/SIGINT to enable graceful drain"
        ),
    )
    flush_on_critical: bool = Field(
        default=False,
        description=(
            "Immediately flush ERROR and CRITICAL logs (bypass batching) "
            "to reduce log loss on abrupt shutdown"
        ),
    )
    # Drop/dedupe visibility (Story 12.20)
    emit_drop_summary: bool = Field(
        default=False,
        description=(
            "Emit summary log events when events are dropped due to backpressure "
            "or deduplicated due to error dedupe window"
        ),
    )
    drop_summary_window_seconds: float = Field(
        default=60.0,
        ge=1.0,
        description=(
            "Window in seconds for aggregating drop/dedupe summary events. "
            "Summaries are emitted at most once per window."
        ),
    )
    # Fallback raw output hardening (Story 4.59)
    fallback_scrub_raw: bool = Field(
        default=True,
        description=(
            "Apply keyword scrubbing to raw (non-JSON) fallback output; "
            "set to False for debugging when raw output is needed"
        ),
    )
    fallback_raw_max_bytes: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Optional limit for raw fallback output bytes; "
            "payloads exceeding this are truncated with '[truncated]' marker"
        ),
    )

    # Example of a field requiring async validation
    benchmark_file_path: str | None = Field(
        default=None,
        description=("Optional path used by performance benchmarks"),
    )

    @field_validator("app_name")
    @classmethod
    def _ensure_app_name_non_empty(cls, value: str) -> str:  # pragma: no cover
        value = value.strip()
        if not value:
            raise ValueError("app_name must not be empty")
        return value


class HttpSinkSettings(BaseModel):
    """Configuration for the built-in HTTP sink."""

    endpoint: str | None = Field(
        default=None, description="HTTP endpoint to POST log events to"
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Default headers to send with each request",
    )
    headers_json: str | None = Field(
        default=None,
        description=(
            'JSON-encoded headers map (e.g. \'{"Authorization": "Bearer x"}\')'
        ),
    )
    retry_max_attempts: int | None = Field(
        default=None,
        ge=1,
        description="Optional max attempts for HTTP retries",
    )
    retry_backoff_seconds: OptionalDurationField = Field(
        default=None,
        gt=0.0,
        description="Optional base backoff between retries. Accepts '2s' or 2.0",
    )
    timeout_seconds: DurationField = Field(
        default=5.0,
        gt=0.0,
        description="Request timeout for HTTP sink operations. Accepts '5s' or 5.0",
    )
    batch_size: int = Field(
        default=1,
        ge=1,
        description="Maximum events per HTTP request (1 = no batching)",
    )
    batch_timeout_seconds: DurationField = Field(
        default=5.0,
        gt=0.0,
        description="Max seconds before flushing a partial batch. Accepts '5s' or 5.0",
    )
    batch_format: str = Field(
        default="array",
        description="Batch format: 'array', 'ndjson', or 'wrapped'",
    )
    batch_wrapper_key: str = Field(
        default="logs",
        description="Wrapper key when batch_format='wrapped'",
    )

    @field_validator("headers_json")
    @classmethod
    def _parse_headers_json(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        try:
            import json

            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("headers_json must decode to a JSON object")
        except Exception as exc:
            raise ValueError(f"Invalid headers_json: {exc}") from exc
        return value

    def resolved_headers(self) -> dict[str, str]:
        if self.headers:
            return dict(self.headers)
        if self.headers_json:
            import json

            parsed = json.loads(self.headers_json)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        return {}


class Settings(BaseSettings):
    """Top-level configuration model with versioning and core settings."""

    # Schema/versioning
    schema_version: str = Field(
        default=LATEST_CONFIG_SCHEMA_VERSION,
        description=("Configuration schema version for forward/backward compatibility"),
    )

    # Namespaced settings groups
    core: CoreSettings = Field(
        default_factory=CoreSettings,
        description="Core logging, performance, and pipeline behavior",
    )
    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="Security controls (encryption, access control, compliance)",
    )
    observability: ObservabilitySettings = Field(
        default_factory=ObservabilitySettings,
        description="Monitoring, metrics, tracing, logging, and alerting",
    )
    http: HttpSinkSettings = Field(
        default_factory=HttpSinkSettings,
        description="Built-in HTTP sink configuration (optional)",
    )

    class SinkConfig(BaseModel):
        """Per-sink configuration for built-in sinks."""

        rotating_file: RotatingFileSettings = Field(
            default_factory=RotatingFileSettings,
            description="Configuration for rotating_file sink",
        )
        http: HttpSinkSettings = Field(
            default_factory=HttpSinkSettings,
            description="Configuration for http sink",
        )
        webhook: WebhookSettings = Field(
            default_factory=WebhookSettings,
            description="Configuration for webhook sink",
        )
        loki: LokiSinkSettings = Field(
            default_factory=LokiSinkSettings,
            description="Configuration for Loki sink",
        )
        stdout_json: dict[str, Any] = Field(
            default_factory=dict, description="Configuration for stdout_json sink"
        )
        sealed: SealedSinkSettings = Field(
            default_factory=SealedSinkSettings,
            description="Configuration for sealed sink (fapilog-tamper)",
        )
        cloudwatch: CloudWatchSinkSettings = Field(
            default_factory=CloudWatchSinkSettings,
            description="Configuration for CloudWatch sink",
        )
        postgres: PostgresSinkSettings = Field(
            default_factory=PostgresSinkSettings,
            description="Configuration for PostgreSQL sink",
        )
        # Third-party sinks use dicts
        extra: dict[str, dict[str, Any]] = Field(
            default_factory=dict,
            description="Configuration for third-party sinks by name",
        )

    class EnricherConfig(BaseModel):
        """Per-enricher configuration for built-in enrichers."""

        runtime_info: dict[str, Any] = Field(
            default_factory=dict, description="Configuration for runtime_info enricher"
        )
        context_vars: dict[str, Any] = Field(
            default_factory=dict, description="Configuration for context_vars enricher"
        )
        integrity: IntegrityEnricherSettings = Field(
            default_factory=IntegrityEnricherSettings,
            description="Configuration for integrity enricher (fapilog-tamper)",
        )
        extra: dict[str, dict[str, Any]] = Field(
            default_factory=dict,
            description="Configuration for third-party enrichers by name",
        )

    class RedactorConfig(BaseModel):
        """Per-redactor configuration for built-in redactors."""

        field_mask: RedactorFieldMaskSettings = Field(
            default_factory=RedactorFieldMaskSettings,
            description="Configuration for field_mask redactor",
        )
        regex_mask: RedactorRegexMaskSettings = Field(
            default_factory=RedactorRegexMaskSettings,
            description="Configuration for regex_mask redactor",
        )
        url_credentials: RedactorUrlCredentialsSettings = Field(
            default_factory=RedactorUrlCredentialsSettings,
            description="Configuration for url_credentials redactor",
        )
        extra: dict[str, dict[str, Any]] = Field(
            default_factory=dict,
            description="Configuration for third-party redactors by name",
        )

    class FilterConfig(BaseModel):
        """Per-filter configuration for built-in filters."""

        level: dict[str, Any] = Field(
            default_factory=dict, description="Configuration for level filter"
        )
        sampling: dict[str, Any] = Field(
            default_factory=dict, description="Configuration for sampling filter"
        )
        rate_limit: dict[str, Any] = Field(
            default_factory=dict, description="Configuration for rate_limit filter"
        )
        adaptive_sampling: dict[str, Any] = Field(
            default_factory=dict,
            description="Configuration for adaptive_sampling filter",
        )
        trace_sampling: dict[str, Any] = Field(
            default_factory=dict,
            description="Configuration for trace_sampling filter",
        )
        first_occurrence: dict[str, Any] = Field(
            default_factory=dict,
            description="Configuration for first_occurrence filter",
        )
        extra: dict[str, dict[str, Any]] = Field(
            default_factory=dict,
            description="Configuration for third-party filters by name",
        )

    # Plugin configuration (simplified - discovery/registry removed)
    class PluginsSettings(BaseModel):
        """Settings controlling plugin behavior."""

        enabled: bool = Field(default=True, description="Enable plugin loading")
        allow_external: bool = Field(
            default=False,
            description="Allow loading plugins from entry points (security risk)",
        )
        allowlist: list[str] = Field(
            default_factory=list,
            description="If non-empty, only these plugin names are allowed",
        )
        denylist: list[str] = Field(
            default_factory=list,
            description="Plugin names to block from loading",
        )
        validation_mode: str = Field(
            default="disabled",
            description="Plugin validation mode: disabled, warn, or strict",
        )

    plugins: PluginsSettings = Field(
        default_factory=PluginsSettings,
        description="Plugin configuration",
    )

    sink_config: SinkConfig = Field(
        default_factory=SinkConfig, description="Per-sink plugin configuration"
    )
    sink_routing: SinkRoutingSettings = Field(
        default_factory=SinkRoutingSettings,
        description="Level-based sink routing configuration",
    )
    enricher_config: EnricherConfig = Field(
        default_factory=EnricherConfig, description="Per-enricher plugin configuration"
    )
    redactor_config: RedactorConfig = Field(
        default_factory=RedactorConfig, description="Per-redactor plugin configuration"
    )
    filter_config: FilterConfig = Field(
        default_factory=FilterConfig, description="Per-filter plugin configuration"
    )
    processor_config: ProcessorConfigSettings = Field(
        default_factory=ProcessorConfigSettings,
        description="Per-processor plugin configuration",
    )

    # Settings behavior
    model_config = SettingsConfigDict(
        env_prefix="FAPILOG_",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    @staticmethod
    def _parse_env_list(value: str) -> list[str]:
        value = value.strip()
        if not value:
            return []
        try:
            import json

            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except Exception:
            pass
        return [v for v in (item.strip() for item in value.split(",")) if v]

    @model_validator(mode="after")
    def _apply_size_guard_env_aliases(self) -> Settings:
        """Support short env aliases like FAPILOG_SIZE_GUARD__MAX_BYTES."""
        _apply_env_aliases(
            self.processor_config.size_guard,
            {
                "action": (
                    "FAPILOG_SIZE_GUARD__ACTION",
                    EnvFieldType.ENUM,
                    {"truncate", "drop", "warn"},
                ),
                "max_bytes": ("FAPILOG_SIZE_GUARD__MAX_BYTES", EnvFieldType.SIZE),
                "preserve_fields": (
                    "FAPILOG_SIZE_GUARD__PRESERVE_FIELDS",
                    EnvFieldType.LIST,
                ),
            },
        )
        return self

    @model_validator(mode="after")
    def _apply_cloudwatch_env_aliases(self) -> Settings:
        """Support short env aliases like FAPILOG_CLOUDWATCH__LOG_GROUP_NAME."""
        _apply_env_aliases(
            self.sink_config.cloudwatch,
            {
                "log_group_name": (
                    "FAPILOG_CLOUDWATCH__LOG_GROUP_NAME",
                    EnvFieldType.STRING,
                ),
                "log_stream_name": (
                    "FAPILOG_CLOUDWATCH__LOG_STREAM_NAME",
                    EnvFieldType.STRING,
                ),
                "region": ("FAPILOG_CLOUDWATCH__REGION", EnvFieldType.STRING),
                "endpoint_url": (
                    "FAPILOG_CLOUDWATCH__ENDPOINT_URL",
                    EnvFieldType.STRING,
                ),
                "batch_size": ("FAPILOG_CLOUDWATCH__BATCH_SIZE", EnvFieldType.INT),
                "batch_timeout_seconds": (
                    "FAPILOG_CLOUDWATCH__BATCH_TIMEOUT_SECONDS",
                    EnvFieldType.DURATION,
                ),
                "max_retries": ("FAPILOG_CLOUDWATCH__MAX_RETRIES", EnvFieldType.INT),
                "retry_base_delay": (
                    "FAPILOG_CLOUDWATCH__RETRY_BASE_DELAY",
                    EnvFieldType.DURATION,
                ),
                "create_log_group": (
                    "FAPILOG_CLOUDWATCH__CREATE_LOG_GROUP",
                    EnvFieldType.BOOL,
                ),
                "create_log_stream": (
                    "FAPILOG_CLOUDWATCH__CREATE_LOG_STREAM",
                    EnvFieldType.BOOL,
                ),
                "circuit_breaker_enabled": (
                    "FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_ENABLED",
                    EnvFieldType.BOOL,
                ),
                "circuit_breaker_threshold": (
                    "FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_THRESHOLD",
                    EnvFieldType.INT,
                ),
            },
        )
        return self

    @model_validator(mode="after")
    def _apply_loki_env_aliases(self) -> Settings:
        """Support short env aliases like FAPILOG_LOKI__URL."""
        _apply_env_aliases(
            self.sink_config.loki,
            {
                "url": ("FAPILOG_LOKI__URL", EnvFieldType.STRING),
                "tenant_id": ("FAPILOG_LOKI__TENANT_ID", EnvFieldType.STRING),
                "auth_username": ("FAPILOG_LOKI__AUTH_USERNAME", EnvFieldType.STRING),
                "auth_password": ("FAPILOG_LOKI__AUTH_PASSWORD", EnvFieldType.STRING),
                "auth_token": ("FAPILOG_LOKI__AUTH_TOKEN", EnvFieldType.STRING),
                "timeout_seconds": (
                    "FAPILOG_LOKI__TIMEOUT_SECONDS",
                    EnvFieldType.DURATION,
                ),
                "batch_size": ("FAPILOG_LOKI__BATCH_SIZE", EnvFieldType.INT),
                "batch_timeout_seconds": (
                    "FAPILOG_LOKI__BATCH_TIMEOUT_SECONDS",
                    EnvFieldType.DURATION,
                ),
                "max_retries": ("FAPILOG_LOKI__MAX_RETRIES", EnvFieldType.INT),
                "retry_base_delay": (
                    "FAPILOG_LOKI__RETRY_BASE_DELAY",
                    EnvFieldType.DURATION,
                ),
                "circuit_breaker_enabled": (
                    "FAPILOG_LOKI__CIRCUIT_BREAKER_ENABLED",
                    EnvFieldType.BOOL,
                ),
                "circuit_breaker_threshold": (
                    "FAPILOG_LOKI__CIRCUIT_BREAKER_THRESHOLD",
                    EnvFieldType.INT,
                ),
                "labels": ("FAPILOG_LOKI__LABELS", EnvFieldType.DICT),
                "label_keys": ("FAPILOG_LOKI__LABEL_KEYS", EnvFieldType.LIST),
            },
        )
        return self

    @model_validator(mode="after")
    def _apply_postgres_env_aliases(self) -> Settings:
        """Support short env aliases like FAPILOG_POSTGRES__HOST."""
        _apply_env_aliases(
            self.sink_config.postgres,
            {
                "dsn": ("FAPILOG_POSTGRES__DSN", EnvFieldType.STRING),
                "host": ("FAPILOG_POSTGRES__HOST", EnvFieldType.STRING),
                "port": ("FAPILOG_POSTGRES__PORT", EnvFieldType.INT),
                "database": ("FAPILOG_POSTGRES__DATABASE", EnvFieldType.STRING),
                "user": ("FAPILOG_POSTGRES__USER", EnvFieldType.STRING),
                "password": ("FAPILOG_POSTGRES__PASSWORD", EnvFieldType.STRING),
                "table_name": ("FAPILOG_POSTGRES__TABLE_NAME", EnvFieldType.STRING),
                "schema_name": ("FAPILOG_POSTGRES__SCHEMA_NAME", EnvFieldType.STRING),
                "min_pool_size": ("FAPILOG_POSTGRES__MIN_POOL_SIZE", EnvFieldType.INT),
                "max_pool_size": ("FAPILOG_POSTGRES__MAX_POOL_SIZE", EnvFieldType.INT),
                "pool_acquire_timeout": (
                    "FAPILOG_POSTGRES__POOL_ACQUIRE_TIMEOUT",
                    EnvFieldType.DURATION,
                ),
                "batch_size": ("FAPILOG_POSTGRES__BATCH_SIZE", EnvFieldType.INT),
                "batch_timeout_seconds": (
                    "FAPILOG_POSTGRES__BATCH_TIMEOUT_SECONDS",
                    EnvFieldType.DURATION,
                ),
                "max_retries": ("FAPILOG_POSTGRES__MAX_RETRIES", EnvFieldType.INT),
                "retry_base_delay": (
                    "FAPILOG_POSTGRES__RETRY_BASE_DELAY",
                    EnvFieldType.DURATION,
                ),
                "circuit_breaker_threshold": (
                    "FAPILOG_POSTGRES__CIRCUIT_BREAKER_THRESHOLD",
                    EnvFieldType.INT,
                ),
                "create_table": ("FAPILOG_POSTGRES__CREATE_TABLE", EnvFieldType.BOOL),
                "use_jsonb": ("FAPILOG_POSTGRES__USE_JSONB", EnvFieldType.BOOL),
                "include_raw_json": (
                    "FAPILOG_POSTGRES__INCLUDE_RAW_JSON",
                    EnvFieldType.BOOL,
                ),
                "circuit_breaker_enabled": (
                    "FAPILOG_POSTGRES__CIRCUIT_BREAKER_ENABLED",
                    EnvFieldType.BOOL,
                ),
                "extract_fields": (
                    "FAPILOG_POSTGRES__EXTRACT_FIELDS",
                    EnvFieldType.LIST,
                ),
            },
        )
        return self

    @model_validator(mode="after")
    def _apply_sink_routing_env_aliases(self) -> Settings:
        """Support env aliases for sink routing."""
        _apply_env_aliases(
            self.sink_routing,
            {
                "enabled": ("FAPILOG_SINK_ROUTING__ENABLED", EnvFieldType.BOOL),
                "overlap": ("FAPILOG_SINK_ROUTING__OVERLAP", EnvFieldType.BOOL),
                "rules": ("FAPILOG_SINK_ROUTING__RULES", EnvFieldType.ROUTING_RULES),
                "fallback_sinks": (
                    "FAPILOG_SINK_ROUTING__FALLBACK_SINKS",
                    EnvFieldType.LIST,
                ),
            },
        )
        return self

    # Async validation entrypoint, called by loader after instantiation
    async def validate_async(self) -> None:
        """Run async validations for fields requiring async checks."""

        if self.core.benchmark_file_path:
            await ensure_path_exists(
                self.core.benchmark_file_path,
                message="benchmark_file_path does not exist",
            )

        # Validate security (async, aggregates issues)
        sec_result = await validate_security(self.security)
        sec_result.raise_if_error(plugin_name="security")

        # Validate observability (sync)
        obs_result = validate_observability(self.observability)
        obs_result.raise_if_error(plugin_name="observability")

    # Convenience serialization helpers
    def to_json(self) -> str:
        import json

        # Use json.dumps to provide a concrete str return type for
        # type checkers
        return json.dumps(self.model_dump(by_alias=True, exclude_none=True))

    def to_dict(self) -> dict[str, object]:
        from typing import cast

        return cast(
            dict[str, object],
            self.model_dump(by_alias=True, exclude_none=True),
        )
