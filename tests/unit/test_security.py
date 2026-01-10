from __future__ import annotations

import pytest

from fapilog.core import (
    AccessControlSettings,
    EncryptionSettings,
    ObservabilitySettings,
    SecuritySettings,
    validate_access_control,
    validate_encryption_async,
    validate_observability,
    validate_security,
)

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_encryption_validation_env_ok() -> None:
    settings = EncryptionSettings(
        enabled=True, key_source="env", env_var_name="APP_KEY"
    )
    result = await validate_encryption_async(settings)
    assert result.ok is True


@pytest.mark.asyncio
async def test_encryption_validation_file_missing(tmp_path) -> None:
    settings = EncryptionSettings(
        enabled=True,
        key_source="file",
        key_file_path=str(tmp_path / "missing.key"),
    )
    result = await validate_encryption_async(settings)
    # Should contain an error for missing key file
    assert any(
        "key_file_path" in i.field and "not found" in i.message for i in result.issues
    )
    assert result.ok is False


def test_access_control_validation_basic_rules() -> None:
    # auth_mode none not allowed when enabled
    ac = AccessControlSettings(enabled=True, auth_mode="none")
    result = validate_access_control(ac)
    assert result.ok is False

    # anonymous write not allowed
    ac2 = AccessControlSettings(allow_anonymous_write=True)
    result2 = validate_access_control(ac2)
    assert result2.ok is False


def test_observability_validation_rules() -> None:
    # Enable monitoring to trigger endpoint requirement
    obs = ObservabilitySettings(monitoring={"enabled": True})
    result = validate_observability(obs)
    assert any(i.field == "monitoring.endpoint" for i in result.issues)
    assert result.ok is False


def test_observability_validation_metrics_exporter() -> None:
    """Test that metrics.exporter cannot be 'none' when metrics are enabled."""
    obs = ObservabilitySettings(metrics={"enabled": True, "exporter": "none"})
    result = validate_observability(obs)
    assert result.ok is False
    assert any(
        i.field == "metrics.exporter"
        and "must not be 'none' when metrics are enabled" in i.message
        for i in result.issues
    )


def test_observability_validation_tracing_sampling_rate() -> None:
    """Test warning when tracing.sampling_rate is 0.0."""
    obs = ObservabilitySettings(tracing={"enabled": True, "sampling_rate": 0.0})
    result = validate_observability(obs)
    # Should have a warning (not an error)
    assert any(
        i.field == "tracing.sampling_rate"
        and i.severity == "warn"
        and "0.0" in i.message
        for i in result.issues
    )


def test_observability_validation_alerting_min_severity() -> None:
    """Test warning when alerting.min_severity is INFO."""
    obs = ObservabilitySettings(alerting={"enabled": True, "min_severity": "INFO"})
    result = validate_observability(obs)
    # Should have a warning (not an error)
    assert any(
        i.field == "alerting.min_severity"
        and i.severity == "warn"
        and "INFO" in i.message
        for i in result.issues
    )


def test_observability_validation_tracing_provider() -> None:
    """Test that tracing.provider cannot be 'none' when tracing is enabled."""
    obs = ObservabilitySettings(tracing={"enabled": True, "provider": "none"})
    result = validate_observability(obs)
    assert result.ok is False
    assert any(
        i.field == "tracing.provider"
        and "must not be 'none' when tracing is enabled" in i.message
        for i in result.issues
    )


def test_observability_validation_logging_format() -> None:
    """Test warning when logging.format is 'text' with correlation enabled."""
    obs = ObservabilitySettings(logging={"format": "text", "include_correlation": True})
    result = validate_observability(obs)
    # Should have a warning (not an error)
    assert any(
        i.field == "logging.format"
        and i.severity == "warn"
        and "text format" in i.message.lower()
        for i in result.issues
    )


def test_create_metrics_collector_from_settings() -> None:
    """Test create_metrics_collector_from_settings factory function."""
    from fapilog.core.observability import create_metrics_collector_from_settings

    # Test with metrics enabled and valid exporter
    obs = ObservabilitySettings(metrics={"enabled": True, "exporter": "prometheus"})
    collector = create_metrics_collector_from_settings(obs)
    # Just verify it creates a MetricsCollector instance
    assert collector is not None

    # Test with metrics disabled
    obs = ObservabilitySettings(metrics={"enabled": False})
    collector = create_metrics_collector_from_settings(obs)
    assert collector is not None

    # Test with metrics enabled but exporter is 'none'
    obs = ObservabilitySettings(metrics={"enabled": True, "exporter": "none"})
    collector = create_metrics_collector_from_settings(obs)
    assert collector is not None


@pytest.mark.asyncio
async def test_security_aggregate_validation(tmp_path) -> None:
    # Setup security with file-based key that exists
    key_path = tmp_path / "app.key"
    key_path.write_text("dummy")

    sec = SecuritySettings(
        encryption=EncryptionSettings(
            enabled=True, key_source="file", key_file_path=str(key_path)
        ),
        access_control=AccessControlSettings(enabled=True, auth_mode="token"),
    )

    result = await validate_security(sec)
    assert result.ok is True


def test_access_control_disabled_warns() -> None:
    ac = AccessControlSettings(enabled=False)
    result = validate_access_control(ac)
    assert result.ok is True
    assert any(i.field == "enabled" and i.severity == "warn" for i in result.issues)


def test_access_control_requires_roles() -> None:
    ac = AccessControlSettings(allowed_roles=[])
    result = validate_access_control(ac)
    assert result.ok is False
    assert any(i.field == "allowed_roles" for i in result.issues)


def test_access_control_warnings_for_read_and_admin() -> None:
    ac = AccessControlSettings(
        allow_anonymous_read=True,
        require_admin_for_sensitive_ops=False,
    )
    result = validate_access_control(ac)
    assert result.ok is True
    fields = {i.field for i in result.issues}
    assert "allow_anonymous_read" in fields
    assert "require_admin_for_sensitive_ops" in fields


@pytest.mark.asyncio
async def test_security_validation_aggregates_access_control_issues() -> None:
    """Test that validate_security aggregates access control validation issues."""
    # Create access control settings that will generate validation issues
    sec = SecuritySettings(
        encryption=EncryptionSettings(enabled=False),
        access_control=AccessControlSettings(
            enabled=True,
            auth_mode="none",  # This will generate an error
        ),
    )
    result = await validate_security(sec)
    assert result.ok is False
    # Should have aggregated the access control issue with prefixed field name
    assert any(
        i.field == "access_control.auth_mode" or i.field.startswith("access_control.")
        for i in result.issues
    )
