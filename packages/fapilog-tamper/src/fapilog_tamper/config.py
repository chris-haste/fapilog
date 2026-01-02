"""
Configuration model for tamper-evident logging.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TamperConfig(BaseModel):
    """User-facing configuration for the tamper plugin."""

    enabled: bool = False
    algorithm: Literal["HMAC-SHA256", "Ed25519"] = "HMAC-SHA256"
    key_id: str = ""
    key_source: Literal[
        "env", "file", "aws-kms", "gcp-kms", "azure-keyvault", "vault"
    ] = "env"
    key_env_var: str = "FAPILOG_TAMPER_KEY"
    key_file_path: str | None = None
    key_cache_ttl_seconds: int = 300
    use_kms_signing: bool = False
    aws_region: str | None = None
    vault_addr: str | None = None
    vault_auth_method: Literal["token", "approle", "kubernetes"] = "token"
    vault_role: str | None = None
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    state_dir: str = ".fapilog-chainstate"
    fsync_on_write: bool = False
    fsync_on_rotate: bool = True
    compress_rotated: bool = False
    rotate_chain: bool = False
    verify_on_close: bool = False
    alert_on_failure: bool = True


class IntegrityEnricherConfig(BaseModel):
    """Standard enricher configuration exposed via fapilog.enrichers."""

    algorithm: Literal["sha256", "ed25519"] = "sha256"
    key_id: str | None = Field(
        default=None, description="Key identifier or alias for HMAC/signing"
    )
    key_provider: Literal[
        "env", "file", "aws-kms", "gcp-kms", "azure-keyvault", "vault"
    ] = "env"
    chain_state_path: str | None = Field(
        default=None, description="Directory to persist chain state files"
    )
    rotate_chain: bool = False
    use_kms_signing: bool = False


class SealedSinkConfig(BaseModel):
    """Standard sink configuration exposed via fapilog.sinks."""

    inner_sink: str = Field(
        default="rotating_file", description="Inner sink to wrap with sealing"
    )
    inner_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration passed to the inner sink",
    )
    manifest_path: str | None = Field(
        default=None, description="Directory to write manifest files"
    )
    sign_manifests: bool = Field(
        default=True, description="Whether to sign manifests when keys are available"
    )
    key_id: str | None = Field(
        default=None, description="Optional override for signing key identifier"
    )
    key_provider: Literal[
        "env", "file", "aws-kms", "gcp-kms", "azure-keyvault", "vault"
    ] = "env"
    chain_state_path: str | None = Field(
        default=None, description="Directory to persist chain state files"
    )
    rotate_chain: bool = False
    fsync_on_write: bool = False
    fsync_on_rotate: bool = True
    compress_rotated: bool = False
    use_kms_signing: bool = False


def _normalize_algorithm(value: str | None) -> str:
    if value is None:
        return "HMAC-SHA256"
    lowered = value.replace("_", "-").lower()
    if lowered in {"sha256", "hmac-sha256"}:
        return "HMAC-SHA256"
    if lowered == "ed25519":
        return "Ed25519"
    return value


def _normalize_key_source(value: str | None) -> str:
    return value or "env"


def coerce_tamper_config(
    config: TamperConfig
    | IntegrityEnricherConfig
    | SealedSinkConfig
    | dict[str, Any]
    | None,
    *,
    enabled_if_unspecified: bool = False,
    overrides: dict[str, Any] | None = None,
) -> TamperConfig:
    """
    Convert standard enricher/sink configuration into TamperConfig.

    Unknown fields are ignored by TamperConfig, so callers can pass plugin-specific
    options without breaking backwards compatibility.
    """

    overrides = overrides or {}
    if isinstance(config, TamperConfig):
        data: dict[str, Any] = config.model_dump()
    elif isinstance(config, BaseModel):
        data = config.model_dump(exclude_none=True)
    else:
        data = dict(config or {})

    for key, value in overrides.items():
        if value is not None:
            data[key] = value

    # Map standard aliases to TamperConfig fields
    if "key_provider" in data and "key_source" not in data:
        data["key_source"] = data.pop("key_provider")
    if "chain_state_path" in data and "state_dir" not in data:
        data["state_dir"] = data.pop("chain_state_path")

    data["algorithm"] = _normalize_algorithm(data.get("algorithm"))
    data["key_source"] = _normalize_key_source(data.get("key_source"))
    data.setdefault("key_id", "")
    if enabled_if_unspecified and "enabled" not in data:
        data["enabled"] = True

    return TamperConfig(**data)
