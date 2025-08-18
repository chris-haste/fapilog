"""
Observability configuration models and validation for enterprise standards.

Covers monitoring, metrics, tracing, logging, and alerting configuration.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..metrics.metrics import MetricsCollector
from .plugin_config import ValidationIssue, ValidationResult


class MonitoringSettings(BaseModel):
    enabled: bool = Field(
        default=False, description="Enable health/monitoring checks and endpoints"
    )
    endpoint: str | None = Field(
        default=None,
        description="Monitoring endpoint URL",
    )


class MetricsSettings(BaseModel):
    enabled: bool = Field(
        default=False, description="Enable internal metrics collection/export"
    )
    exporter: Literal["prometheus", "none"] = Field(
        default="prometheus",
        description="Metrics exporter to use ('prometheus' or 'none')",
    )
    port: int = Field(
        default=8000, ge=1, le=65535, description="TCP port for metrics exporter"
    )


class TracingSettings(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable distributed tracing features",
    )
    provider: Literal["otel", "none"] = Field(
        default="otel",
        description="Tracing backend provider ('otel' or 'none')",
    )
    sampling_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Trace sampling probability in range 0.0–1.0",
    )


class LoggingSettings(BaseModel):
    format: Literal["json", "text"] = Field(
        default="json",
        description="Output format for logs (machine-friendly JSON or text)",
    )
    include_correlation: bool = Field(
        default=True,
        description="Include correlation IDs and trace/span metadata in logs",
    )
    sampling_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Log sampling probability in range 0.0–1.0",
    )


class AlertingSettings(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable emitting alerts from the logging pipeline",
    )
    # Simple placeholder for future extension
    min_severity: Literal["INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="ERROR",
        description="Minimum alert severity to emit (filter threshold)",
    )


class ObservabilitySettings(BaseModel):
    monitoring: MonitoringSettings = Field(
        default_factory=MonitoringSettings,
        description="Monitoring configuration (health/endpoint)",
    )
    metrics: MetricsSettings = Field(
        default_factory=MetricsSettings,
        description="Metrics configuration (exporter and port)",
    )
    tracing: TracingSettings = Field(
        default_factory=TracingSettings, description="Tracing configuration"
    )
    logging: LoggingSettings = Field(
        default_factory=LoggingSettings,
        description="Logging output format and correlation settings",
    )
    alerting: AlertingSettings = Field(
        default_factory=AlertingSettings, description="Alerting configuration"
    )


def validate_observability(
    settings: ObservabilitySettings,
) -> ValidationResult:
    """Validate observability configuration for enterprise readiness."""
    result = ValidationResult(ok=True)

    # Monitoring
    if settings.monitoring.enabled and not settings.monitoring.endpoint:
        result.add_issue(
            ValidationIssue(
                field="monitoring.endpoint",
                message="required when monitoring.enabled is true",
            )
        )

    # Metrics
    if settings.metrics.enabled and settings.metrics.exporter == "none":
        result.add_issue(
            ValidationIssue(
                field="metrics.exporter",
                message=("exporter must not be 'none' when metrics are enabled"),
            )
        )

    # Tracing sampling bounds reminder
    if settings.tracing.enabled and settings.tracing.sampling_rate == 0.0:
        result.add_issue(
            ValidationIssue(
                field="tracing.sampling_rate",
                message=("sampling_rate is 0.0; traces will be disabled"),
                severity="warn",
            )
        )

    # Alerting severity guidance
    if settings.alerting.enabled and settings.alerting.min_severity == "INFO":
        result.add_issue(
            ValidationIssue(
                field="alerting.min_severity",
                message="INFO may generate high alert volume",
                severity="warn",
            )
        )

    # Tracing
    if settings.tracing.enabled and settings.tracing.provider == "none":
        result.add_issue(
            ValidationIssue(
                field="tracing.provider",
                message="provider must not be 'none' when tracing is enabled",
            )
        )

    # Logging
    if settings.logging.format == "text" and settings.logging.include_correlation:
        # Text format often loses structure; warn but allow
        result.add_issue(
            ValidationIssue(
                field="logging.format",
                message=("text format with correlation may be hard to parse"),
                severity="warn",
            )
        )

    return result


def create_metrics_collector_from_settings(
    settings: ObservabilitySettings,
) -> MetricsCollector:
    """Factory helper to provision a `MetricsCollector`.

    Enables metrics only when both the metrics group is enabled and a valid
    exporter is selected. The collector does not start any HTTP server;
    exporting is left to application integration.
    """
    enabled = bool(settings.metrics.enabled and settings.metrics.exporter != "none")
    return MetricsCollector(enabled=enabled)
