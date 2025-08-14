from __future__ import annotations

from fapilog.core.observability import (
    MonitoringSettings,
    ObservabilitySettings,
    validate_observability,
)


def test_monitoring_enabled_without_endpoint_warns() -> None:
    settings = ObservabilitySettings(monitoring=MonitoringSettings(enabled=True))
    res = validate_observability(settings)
    assert any(i.field == "monitoring.endpoint" for i in res.issues)
