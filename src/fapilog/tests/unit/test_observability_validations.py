from __future__ import annotations

from fapilog.core.observability import (
    LoggingSettings,
    ObservabilitySettings,
    validate_observability,
)


def test_logging_text_with_correlation_warns() -> None:
    settings = ObservabilitySettings(
        logging=LoggingSettings(format="text", include_correlation=True)
    )
    res = validate_observability(settings)
    issues = [i for i in res.issues if getattr(i, "severity", "") == "warn"]
    assert any("logging.format" == i.field for i in issues)
