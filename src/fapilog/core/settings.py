"""
Async Configuration and Validation for Fapilog v3.

This module provides async configuration loading with comprehensive validation,
plugin marketplace integration, enterprise compliance, and security validation.
"""

import asyncio
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigurationError


class LogLevel(str, Enum):
    """Log levels for configuration."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PluginDiscoveryMethod(str, Enum):
    """Plugin discovery methods."""

    ENTRY_POINTS = "entry_points"
    LOCAL_PATHS = "local_paths"
    MARKETPLACE = "marketplace"
    ALL = "all"


class ComplianceStandard(str, Enum):
    """Enterprise compliance standards."""

    SOX = "sox"
    PCI_DSS = "pci_dss"
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    GDPR = "gdpr"


class EncryptionMethod(str, Enum):
    """Encryption methods for sensitive data."""

    AES_256_GCM = "aes_256_gcm"
    CHACHA20_POLY1305 = "chacha20_poly1305"
    FERNET = "fernet"


class CoreConfig(BaseModel):
    """Core logging configuration."""

    # Basic logging settings
    log_level: LogLevel = LogLevel.INFO
    structured_logging: bool = True
    async_logging: bool = True

    # Performance settings
    buffer_size: int = Field(default=1000, ge=1, le=100000)
    flush_interval: float = Field(default=1.0, ge=0.1, le=60.0)
    max_queue_size: int = Field(default=10000, ge=100, le=1000000)

    # Context preservation
    preserve_context: bool = True
    context_timeout: float = Field(default=30.0, ge=1.0, le=300.0)

    # Error handling
    circuit_breaker_enabled: bool = True
    retry_enabled: bool = True
    fallback_enabled: bool = True


class PluginConfig(BaseModel):
    """Plugin configuration and validation."""

    # Discovery settings
    discovery_methods: List[PluginDiscoveryMethod] = Field(
        default=[PluginDiscoveryMethod.ENTRY_POINTS, PluginDiscoveryMethod.LOCAL_PATHS]
    )
    discovery_paths: List[Path] = Field(default_factory=list)

    # Plugin validation
    require_signature_validation: bool = False
    allow_unsigned_plugins: bool = True
    plugin_timeout: float = Field(default=30.0, ge=1.0, le=300.0)

    # Plugin isolation
    enable_plugin_isolation: bool = True
    plugin_memory_limit_mb: Optional[int] = Field(default=None, ge=1, le=10240)

    # Marketplace integration
    marketplace_enabled: bool = False
    marketplace_url: Optional[str] = None
    marketplace_api_key: Optional[str] = None
    marketplace_cache_ttl: int = Field(default=3600, ge=60, le=86400)

    @field_validator("discovery_paths")
    @classmethod
    def validate_discovery_paths(cls, v: List[Path]) -> List[Path]:
        """Validate that discovery paths exist and are directories."""
        validated_paths = []
        for path in v:
            if not path.exists():
                raise ValueError(f"Discovery path does not exist: {path}")
            if not path.is_dir():
                raise ValueError(f"Discovery path is not a directory: {path}")
            validated_paths.append(path)
        return validated_paths

    @field_validator("marketplace_url")
    @classmethod
    def validate_marketplace_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate marketplace URL format."""
        if v is not None:
            if not v.startswith(("http://", "https://")):
                raise ValueError("Marketplace URL must start with http:// or https://")
        return v


class ComplianceConfig(BaseModel):
    """Enterprise compliance configuration."""

    # Compliance features
    compliance_enabled: bool = False
    compliance_standards: Set[ComplianceStandard] = Field(default_factory=set)

    # Audit trail settings
    audit_enabled: bool = False
    audit_retention_days: int = Field(default=365, ge=30, le=2555)  # 7 years max
    audit_integrity_checks: bool = False

    # Data handling
    data_classification_enabled: bool = False
    pii_detection_enabled: bool = False
    data_anonymization_enabled: bool = False

    # Access control
    role_based_access_enabled: bool = False
    audit_access_roles: Set[str] = Field(default_factory=set)

    # Retention policies
    retention_policy_enabled: bool = False
    retention_categories: Dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_compliance_consistency(self) -> "ComplianceConfig":
        """Validate compliance configuration consistency."""
        if self.compliance_enabled and not self.compliance_standards:
            raise ValueError(
                "At least one compliance standard must be specified when compliance is enabled"
            )

        if self.audit_integrity_checks and not self.audit_enabled:
            raise ValueError("Audit must be enabled to use integrity checks")

        if self.role_based_access_enabled and not self.audit_access_roles:
            raise ValueError(
                "At least one audit access role must be specified when RBAC is enabled"
            )

        return self


class SecurityConfig(BaseModel):
    """Security configuration and validation."""

    # Encryption settings
    encryption_enabled: bool = False
    encryption_method: EncryptionMethod = EncryptionMethod.AES_256_GCM
    encryption_key_rotation_days: int = Field(default=90, ge=1, le=365)

    # Key management
    encryption_key: Optional[str] = None
    key_derivation_iterations: int = Field(default=100000, ge=10000, le=1000000)

    # Access control
    authentication_enabled: bool = False
    authorization_enabled: bool = False
    session_timeout_minutes: int = Field(default=60, ge=5, le=1440)

    # Security headers and validation
    validate_input_schemas: bool = True
    sanitize_log_content: bool = True
    mask_sensitive_fields: bool = True
    sensitive_field_patterns: List[str] = Field(
        default=["password", "token", "key", "secret", "credential"]
    )

    @model_validator(mode="after")
    def validate_security_consistency(self) -> "SecurityConfig":
        """Validate security configuration consistency."""
        if self.encryption_enabled and not self.encryption_key:
            raise ValueError(
                "Encryption key must be provided when encryption is enabled"
            )

        if self.authorization_enabled and not self.authentication_enabled:
            raise ValueError("Authentication must be enabled to use authorization")

        return self


class ObservabilityConfig(BaseModel):
    """Observability configuration for enterprise standards."""

    # Metrics collection
    metrics_enabled: bool = True
    metrics_port: int = Field(default=8000, ge=1024, le=65535)
    metrics_path: str = "/metrics"

    # Performance monitoring
    performance_monitoring_enabled: bool = True
    performance_sampling_rate: float = Field(default=0.1, ge=0.0, le=1.0)

    # Health checks
    health_check_enabled: bool = True
    health_check_interval: int = Field(default=30, ge=5, le=300)

    # Distributed tracing
    tracing_enabled: bool = False
    tracing_endpoint: Optional[str] = None
    tracing_sampling_rate: float = Field(default=0.01, ge=0.0, le=1.0)

    # Alerting
    alerting_enabled: bool = False
    alert_thresholds: Dict[str, float] = Field(default_factory=dict)

    @field_validator("tracing_endpoint")
    @classmethod
    def validate_tracing_endpoint(cls, v: Optional[str]) -> Optional[str]:
        """Validate tracing endpoint URL format."""
        if v is not None:
            if not v.startswith(("http://", "https://", "grpc://")):
                raise ValueError(
                    "Tracing endpoint must start with http://, https://, or grpc://"
                )
        return v


class MarketplaceConfig(BaseModel):
    """Plugin marketplace configuration for ecosystem growth."""

    # Marketplace settings
    marketplace_enabled: bool = False
    marketplace_url: str = "https://plugins.fapilog.dev/api/v1"
    marketplace_api_key: Optional[str] = None

    # Plugin discovery
    auto_discovery_enabled: bool = False
    discovery_interval_hours: int = Field(default=24, ge=1, le=168)  # Max 1 week

    # Plugin verification
    verify_plugin_signatures: bool = True
    trusted_publishers: Set[str] = Field(default_factory=set)

    # Caching
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=3600, ge=300, le=86400)
    cache_max_size_mb: int = Field(default=100, ge=10, le=1000)

    # Update management
    auto_update_enabled: bool = False
    update_check_interval_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("marketplace_url")
    @classmethod
    def validate_marketplace_url(cls, v: str) -> str:
        """Validate marketplace URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Marketplace URL must start with http:// or https://")
        return v


class FapilogSettings(BaseSettings):
    """
    Main Fapilog configuration with async loading and comprehensive validation.

    This configuration system provides:
    - Async configuration loading with environment variable support
    - Pydantic v2 validation excellence with async field validation patterns
    - Plugin configuration validation with quality gates
    - Enterprise compliance validation for sensitive data controls
    - Security configuration validation for encryption and access control
    - Hot-reloading capabilities for dynamic configuration updates
    """

    model_config = SettingsConfigDict(
        env_prefix="FAPILOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Core configuration sections
    core: CoreConfig = Field(default_factory=CoreConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    marketplace: MarketplaceConfig = Field(default_factory=MarketplaceConfig)

    # Global settings
    config_version: str = "3.0.0"
    environment: str = Field(
        default="development", pattern=r"^(development|staging|production|testing)$"
    )
    debug: bool = Field(default=False)

    # Configuration metadata
    config_source: Optional[str] = None
    last_loaded: Optional[float] = None

    @model_validator(mode="after")
    def validate_global_consistency(self) -> "FapilogSettings":
        """Validate global configuration consistency."""
        # Production environment validations
        if self.environment == "production":
            if self.debug:
                raise ValueError("Debug mode cannot be enabled in production")

            if (
                not self.security.encryption_enabled
                and self.compliance.compliance_enabled
            ):
                raise ValueError(
                    "Encryption must be enabled in production when compliance is enabled"
                )

        # Marketplace consistency
        if (
            self.marketplace.marketplace_enabled
            and not self.plugins.marketplace_enabled
        ):
            self.plugins.marketplace_enabled = True
            self.plugins.marketplace_url = self.marketplace.marketplace_url
            self.plugins.marketplace_api_key = self.marketplace.marketplace_api_key

        return self

    async def validate_async_fields(self) -> None:
        """Perform async validation of configuration fields."""
        tasks = []

        # Allow tests and certain environments to skip network validations
        skip_network_validation = os.getenv("FAPILOG_SKIP_NETWORK_VALIDATION") == "1"

        # Validate plugin paths accessibility
        if self.plugins.discovery_paths:
            tasks.append(self._validate_plugin_paths())

        # Validate marketplace connectivity
        if self.marketplace.marketplace_enabled and not skip_network_validation:
            tasks.append(self._validate_marketplace_connectivity())

        # Validate observability endpoints
        if (
            self.observability.tracing_enabled
            and self.observability.tracing_endpoint
            and not skip_network_validation
        ):
            tasks.append(self._validate_tracing_endpoint())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for validation errors
            for result in results:
                if isinstance(result, Exception):
                    raise ConfigurationError(f"Async validation failed: {result}")

    async def _validate_plugin_paths(self) -> None:
        """Validate plugin discovery paths asynchronously."""
        for path in self.plugins.discovery_paths:
            if not await asyncio.to_thread(path.exists):
                raise ValueError(f"Plugin discovery path does not exist: {path}")

            if not await asyncio.to_thread(path.is_dir):
                raise ValueError(f"Plugin discovery path is not a directory: {path}")

    async def _validate_marketplace_connectivity(self) -> None:
        """Validate marketplace connectivity asynchronously."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(self.marketplace.marketplace_url)
                if response.status_code >= 400:
                    raise ValueError(
                        f"Marketplace endpoint returned status {response.status_code}"
                    )
        except httpx.RequestError as e:
            raise ValueError(f"Failed to connect to marketplace: {e}") from e

    async def _validate_tracing_endpoint(self) -> None:
        """Validate distributed tracing endpoint asynchronously."""
        if not self.observability.tracing_endpoint:
            return

        endpoint = self.observability.tracing_endpoint

        # For gRPC endpoints, we just validate the format
        if endpoint.startswith("grpc://"):
            return

        # For HTTP endpoints, test connectivity
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.head(endpoint)
                if response.status_code >= 400:
                    raise ValueError(
                        f"Tracing endpoint returned status {response.status_code}"
                    )
        except httpx.RequestError as e:
            raise ValueError(f"Failed to connect to tracing endpoint: {e}") from e


# Global configuration instance
_settings: Optional[FapilogSettings] = None
_settings_lock: Optional[asyncio.Lock] = None


def _get_settings_lock() -> asyncio.Lock:
    """Get or create the settings lock."""
    global _settings_lock
    if _settings_lock is None:
        _settings_lock = asyncio.Lock()
    return _settings_lock


async def load_settings(
    config_file: Optional[Union[str, Path]] = None,
    environment_override: Optional[str] = None,
    **kwargs: Any,
) -> FapilogSettings:
    """
    Load Fapilog settings asynchronously with comprehensive validation.

    Args:
        config_file: Optional configuration file path
        environment_override: Override environment setting
        **kwargs: Additional configuration overrides

    Returns:
        Validated FapilogSettings instance

    Raises:
        ConfigurationError: If configuration loading or validation fails
    """
    global _settings

    async with _get_settings_lock():
        try:
            # Load configuration from file if provided
            file_config = {}
            if config_file:
                config_path = Path(config_file)
                if config_path.exists():
                    import tomllib

                    content = await asyncio.to_thread(config_path.read_text)
                    if config_path.suffix.lower() == ".toml":
                        file_config = tomllib.loads(content)
                    elif config_path.suffix.lower() in [".json"]:
                        import json

                        file_config = json.loads(content)
                    else:
                        raise ConfigurationError(
                            f"Unsupported configuration file format: {config_path.suffix}"
                        )

            # Merge configurations (kwargs > file > env)
            merged_config = {**file_config, **kwargs}

            # Add environment override to merged config
            if environment_override:
                merged_config["environment"] = environment_override

            # Create settings instance
            settings = FapilogSettings(**merged_config)

            # Set metadata
            settings.config_source = str(config_file) if config_file else "environment"
            settings.last_loaded = asyncio.get_event_loop().time()

            # Perform async validation
            await settings.validate_async_fields()

            _settings = settings
            return settings

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise

            raise ConfigurationError(
                f"Failed to load configuration: {e}",
                cause=e,
            ) from e


async def get_settings() -> FapilogSettings:
    """
    Get current Fapilog settings, loading defaults if not already loaded.

    Returns:
        Current FapilogSettings instance
    """
    global _settings

    if _settings is None:
        async with _get_settings_lock():
            if _settings is None:
                # Call the internal logic without acquiring the lock again
                try:
                    # Create settings instance with defaults
                    settings = FapilogSettings()

                    # Set metadata
                    settings.config_source = "environment"
                    settings.last_loaded = asyncio.get_event_loop().time()

                    # Perform async validation
                    await settings.validate_async_fields()

                    _settings = settings
                except Exception as e:
                    if isinstance(e, ConfigurationError):
                        raise
                    raise ConfigurationError(
                        f"Failed to load configuration: {e}"
                    ) from e

    return _settings


async def reload_settings(
    config_file: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> FapilogSettings:
    """
    Reload Fapilog settings with new configuration.

    Args:
        config_file: Optional configuration file path
        **kwargs: Configuration overrides

    Returns:
        New FapilogSettings instance
    """
    global _settings

    async with _get_settings_lock():
        _settings = None
        # Call the internal logic directly to avoid deadlock
        try:
            # Load configuration from file if provided
            file_config = {}
            if config_file:
                config_path = Path(config_file)
                if config_path.exists():
                    import tomllib

                    content = await asyncio.to_thread(config_path.read_text)
                    if config_path.suffix.lower() == ".toml":
                        file_config = tomllib.loads(content)
                    elif config_path.suffix.lower() in [".json"]:
                        import json

                        file_config = json.loads(content)
                    else:
                        raise ConfigurationError(
                            f"Unsupported configuration file format: {config_path.suffix}"
                        )

            # Merge configurations (kwargs > file > env)
            merged_config = {**file_config, **kwargs}

            # Create settings instance
            settings = FapilogSettings(**merged_config)

            # Set metadata
            settings.config_source = str(config_file) if config_file else "environment"
            settings.last_loaded = asyncio.get_event_loop().time()

            # Perform async validation
            await settings.validate_async_fields()

            _settings = settings
            return settings

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to load configuration: {e}") from e


def reset_settings() -> None:
    """Reset settings to force reload on next access"""
    global _settings
    _settings = None
