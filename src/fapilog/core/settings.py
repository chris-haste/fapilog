"""
Async-first configuration models for Fapilog v3 using Pydantic v2 Settings.

This module defines the public configuration schema and provides
async-aware validation hooks used by the loader in `config.py`.
"""

from __future__ import annotations

from typing import Literal

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

# Keep explicit version to allow schema gating and forward migrations later
LATEST_CONFIG_SCHEMA_VERSION = "1.0"


class CoreSettings(BaseModel):
    """Core logging and performance settings.

    Keep this minimal and stable; prefer plugin-specific settings elsewhere.
    """

    app_name: str = Field(default="fapilog", description="Logical application name")
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
    # Structured internal diagnostics for non-fatal errors (worker/sink/metrics)
    internal_logging_enabled: bool = Field(
        default=False, description=("Emit DEBUG/WARN diagnostics for internal errors")
    )
    # Redactors stage toggles and guardrails
    enable_redactors: bool = Field(
        default=False,
        description=("Enable redactors stage between enrichers and sink emission"),
    )
    redactors_order: list[str] = Field(
        default_factory=list,
        description=("Ordered list of redactor plugin names to apply"),
    )
    redaction_max_depth: int | None = Field(
        default=None,
        ge=1,
        description=("Optional max depth guardrail for nested redaction"),
    )
    redaction_max_keys_scanned: int | None = Field(
        default=None,
        ge=1,
        description=("Optional max keys scanned guardrail for redaction"),
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


class Settings(BaseSettings):
    """Top-level configuration model with versioning and core settings."""

    # Schema/versioning
    schema_version: str = Field(default=LATEST_CONFIG_SCHEMA_VERSION)

    # Namespaced settings groups
    core: CoreSettings = Field(default_factory=CoreSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

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
