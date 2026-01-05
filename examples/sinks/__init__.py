"""Example cloud sinks for fapilog."""

from .cloud_sink_base import CloudSinkBase, CloudSinkConfig  # noqa: F401
from .datadog_sink import DatadogSink, DatadogSinkConfig  # noqa: F401
from .gcp_logging_sink import GCPCloudLoggingConfig, GCPCloudLoggingSink  # noqa: F401

__all__ = [
    "CloudSinkBase",
    "CloudSinkConfig",
    "DatadogSink",
    "DatadogSinkConfig",
    "GCPCloudLoggingSink",
    "GCPCloudLoggingConfig",
]
