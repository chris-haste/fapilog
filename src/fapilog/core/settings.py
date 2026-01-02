"""
Async-first configuration models for Fapilog v3 using Pydantic v2 Settings.

This module defines the public configuration schema and provides
async-aware validation hooks used by the loader in `config.py`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
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
from .validation import ensure_path_exists


class RotatingFileSettings(BaseModel):
    """Per-plugin configuration for RotatingFileSink."""

    directory: str | None = Field(
        default=None, description="Log directory for rotating file sink"
    )
    filename_prefix: str = Field(default="fapilog", description="Filename prefix")
    mode: Literal["json", "text"] = Field(
        default="json", description="Output format: json or text"
    )
    max_bytes: int = Field(
        default=10 * 1024 * 1024, ge=1, description="Max bytes before rotation"
    )
    interval_seconds: int | None = Field(
        default=None, description="Rotation interval in seconds (optional)"
    )
    max_files: int | None = Field(
        default=None, description="Max number of rotated files to keep"
    )
    max_total_bytes: int | None = Field(
        default=None, description="Max total bytes across all rotated files"
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
    retry_backoff_seconds: float | None = Field(
        default=None, gt=0.0, description="Backoff between retries in seconds"
    )
    timeout_seconds: float = Field(
        default=5.0, gt=0.0, description="Request timeout in seconds"
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
        default_factory=list,
        description=("Redactor plugins to use (by name); empty to disable"),
    )
    processors: list[str] = Field(
        default_factory=list,
        description=("Processor plugins to use (by name)"),
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
        default=50,
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
    # Optional integrity/tamper-evident add-on selection
    integrity_plugin: str | None = Field(
        default=None,
        description=(
            "Optional integrity plugin name (fapilog.integrity entry point) to enable"
        ),
    )
    integrity_config: dict[str, object] | None = Field(
        default=None,
        description=(
            "Opaque configuration mapping passed to the selected integrity plugin"
        ),
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
    retry_backoff_seconds: float | None = Field(
        default=None,
        gt=0.0,
        description="Optional base backoff seconds between retries",
    )
    timeout_seconds: float = Field(
        default=5.0,
        gt=0.0,
        description="Request timeout for HTTP sink operations",
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
        stdout_json: dict[str, Any] = Field(
            default_factory=dict, description="Configuration for stdout_json sink"
        )
        sealed: SealedSinkSettings = Field(
            default_factory=SealedSinkSettings,
            description="Configuration for sealed sink (fapilog-tamper)",
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

    # Plugin configuration (simplified - discovery/registry removed)
    class PluginsSettings(BaseModel):
        """Settings controlling plugin behavior."""

        enabled: bool = Field(default=True, description="Enable plugin loading")
        allowlist: list[str] = Field(
            default_factory=list,
            description="If non-empty, only these plugin names are allowed",
        )
        denylist: list[str] = Field(
            default_factory=list,
            description="Plugin names to block from loading",
        )

    plugins: PluginsSettings = Field(
        default_factory=PluginsSettings,
        description="Plugin configuration",
    )

    sink_config: SinkConfig = Field(
        default_factory=SinkConfig, description="Per-sink plugin configuration"
    )
    enricher_config: EnricherConfig = Field(
        default_factory=EnricherConfig, description="Per-enricher plugin configuration"
    )
    redactor_config: RedactorConfig = Field(
        default_factory=RedactorConfig, description="Per-redactor plugin configuration"
    )

    # Settings behavior
    model_config = SettingsConfigDict(
        env_prefix="FAPILOG_",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

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
