"""
Universal settings for fapilog v3 async-first logging.

This module provides the UniversalSettings class that configures all aspects
of the async-first logging system with enterprise compliance features.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field, validator


class ComplianceStandard(str, Enum):
    """Enterprise compliance standards."""
    
    NONE = "none"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    SOX = "sox"
    GDPR = "gdpr"
    SOC2 = "soc2"


class OverflowStrategy(str, Enum):
    """Queue overflow handling strategies."""
    
    DROP = "drop"
    BLOCK = "block"
    SAMPLE = "sample"


class LogLevel(str, Enum):
    """Standard log levels."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class UniversalSettings(BaseModel):
    """Universal settings for async-first logging configuration."""
    
    # Core settings
    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level for the system"
    )
    sinks: List[str] = Field(
        default=["stdout"],
        description="List of sink URIs to write logs to"
    )
    
    # Async processing settings
    async_processing: bool = Field(
        default=True,
        description="Enable async-first processing"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of events to batch before processing"
    )
    batch_timeout: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Maximum time to wait for batch completion (seconds)"
    )
    
    # Performance settings
    zero_copy_operations: bool = Field(
        default=True,
        description="Enable zero-copy operations for maximum performance"
    )
    parallel_processing: bool = Field(
        default=True,
        description="Enable parallel processing of events"
    )
    max_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Maximum number of parallel workers"
    )
    
    # Queue settings
    queue_max_size: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum size of the async queue"
    )
    overflow_strategy: OverflowStrategy = Field(
        default=OverflowStrategy.DROP,
        description="Strategy for handling queue overflow"
    )
    sampling_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sampling rate for log events (0.0 to 1.0)"
    )
    
    # Enterprise compliance settings
    compliance_standard: ComplianceStandard = Field(
        default=ComplianceStandard.NONE,
        description="Enterprise compliance standard to enforce"
    )
    data_minimization: bool = Field(
        default=False,
        description="Enable automatic PII detection and redaction"
    )
    audit_trail: bool = Field(
        default=False,
        description="Enable immutable audit trail logging"
    )
    encryption_enabled: bool = Field(
        default=False,
        description="Enable log encryption for sensitive data"
    )
    
    # Plugin ecosystem settings
    plugins_enabled: bool = Field(
        default=True,
        description="Enable the universal plugin ecosystem"
    )
    plugin_marketplace: bool = Field(
        default=True,
        description="Enable plugin marketplace functionality"
    )
    plugin_auto_discovery: bool = Field(
        default=True,
        description="Enable automatic plugin discovery"
    )
    
    # Metrics and monitoring settings
    metrics_enabled: bool = Field(
        default=True,
        description="Enable performance metrics collection"
    )
    health_checks_enabled: bool = Field(
        default=True,
        description="Enable health check endpoints"
    )
    prometheus_enabled: bool = Field(
        default=False,
        description="Enable Prometheus metrics export"
    )
    
    # Future alerting settings (disabled by default)
    alerting_enabled: bool = Field(
        default=False,
        description="Enable future alerting capabilities"
    )
    alerting_plugins: List[str] = Field(
        default=[],
        description="List of alerting plugin URIs"
    )
    
    # Event structure settings
    include_source: bool = Field(
        default=True,
        description="Include source field in log events"
    )
    include_severity: bool = Field(
        default=True,
        description="Include severity field in log events"
    )
    include_tags: bool = Field(
        default=True,
        description="Include tags field in log events"
    )
    include_metrics: bool = Field(
        default=True,
        description="Include metrics field in log events"
    )
    include_correlation: bool = Field(
        default=True,
        description="Include correlation_id field in log events"
    )
    
    # Custom configuration
    custom_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom settings for plugins and extensions"
    )
    
    @validator("sinks")
    def validate_sinks(cls, v: List[str]) -> List[str]:
        """Validate sink URIs."""
        if not v:
            raise ValueError("At least one sink must be specified")
        return v
    
    @validator("custom_settings")
    def validate_custom_settings(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate custom settings."""
        # Ensure no reserved keys are used
        reserved_keys = {
            "level", "sinks", "async_processing", "batch_size",
            "batch_timeout", "zero_copy_operations", "parallel_processing",
            "max_workers", "queue_max_size", "overflow_strategy",
            "sampling_rate", "compliance_standard", "data_minimization",
            "audit_trail", "encryption_enabled", "plugins_enabled",
            "plugin_marketplace", "plugin_auto_discovery", "metrics_enabled",
            "health_checks_enabled", "prometheus_enabled", "alerting_enabled",
            "alerting_plugins", "include_source", "include_severity",
            "include_tags", "include_metrics", "include_correlation"
        }
        
        for key in v.keys():
            if key in reserved_keys:
                raise ValueError(
                    f"Custom setting '{key}' conflicts with reserved key"
                )
        
        return v
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        extra = "forbid" 