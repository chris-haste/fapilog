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
        description="Maximum in-memory queue size for async processing",
    )
    enable_metrics: bool = Field(
        default=False, description="Enable Prometheus-compatible metrics"
    )
    # Example of a field requiring async validation
    benchmark_file_path: str | None = Field(
        default=None,
        description="Optional path used by performance benchmarks",
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

    # Convenience serialization helpers
    def to_json(self) -> str:
        from typing import cast

        return cast(str, self.model_dump_json(by_alias=True, exclude_none=True))

    def to_dict(self) -> dict:
        from typing import Any, cast

        return cast(dict[str, Any], self.model_dump(by_alias=True, exclude_none=True))
