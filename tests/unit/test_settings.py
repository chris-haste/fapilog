"""
Unit tests for UniversalSettings.
"""

import pytest
from pydantic import ValidationError

from fapilog.core.settings import (
    ComplianceStandard,
    LogLevel,
    OverflowStrategy,
    UniversalSettings,
)


class TestUniversalSettings:
    """Test UniversalSettings configuration."""

    def test_default_settings(self) -> None:
        """Test default settings are valid."""
        settings = UniversalSettings()

        assert settings.level == LogLevel.INFO
        assert settings.sinks == ["stdout"]
        assert settings.async_processing is True
        assert settings.zero_copy_operations is True
        assert settings.parallel_processing is True
        assert settings.max_workers == 4

    def test_custom_settings(self) -> None:
        """Test custom settings validation."""
        settings = UniversalSettings(
            level=LogLevel.DEBUG,
            sinks=["file://logs/app.log", "stdout"],
            max_workers=8,
            batch_size=50,
        )

        assert settings.level == LogLevel.DEBUG
        assert settings.sinks == ["file://logs/app.log", "stdout"]
        assert settings.max_workers == 8
        assert settings.batch_size == 50

    def test_sink_validation_empty_list(self) -> None:
        """Test that empty sinks list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            UniversalSettings(sinks=[])

        assert "At least one sink must be specified" in str(exc_info.value)

    def test_custom_settings_reserved_key_conflict(self) -> None:
        """Test that custom settings cannot use reserved keys."""
        with pytest.raises(ValidationError) as exc_info:
            UniversalSettings(custom_settings={"level": "CRITICAL"})

        assert "conflicts with reserved key" in str(exc_info.value)

    def test_compliance_standards(self) -> None:
        """Test compliance standard settings."""
        settings = UniversalSettings(
            compliance_standard=ComplianceStandard.HIPAA,
            data_minimization=True,
            audit_trail=True,
            encryption_enabled=True,
        )

        assert settings.compliance_standard == ComplianceStandard.HIPAA
        assert settings.data_minimization is True
        assert settings.audit_trail is True
        assert settings.encryption_enabled is True

    def test_overflow_strategies(self) -> None:
        """Test overflow strategy settings."""
        for strategy in OverflowStrategy:
            settings = UniversalSettings(overflow_strategy=strategy)
            assert settings.overflow_strategy == strategy

    def test_worker_limits(self) -> None:
        """Test worker count validation."""
        # Valid worker count
        settings = UniversalSettings(max_workers=16)
        assert settings.max_workers == 16

        # Test minimum boundary
        settings = UniversalSettings(max_workers=1)
        assert settings.max_workers == 1

        # Test maximum boundary
        settings = UniversalSettings(max_workers=32)
        assert settings.max_workers == 32

    def test_batch_settings(self) -> None:
        """Test batch processing settings."""
        settings = UniversalSettings(batch_size=200, batch_timeout=2.5)

        assert settings.batch_size == 200
        assert settings.batch_timeout == 2.5

    def test_plugin_settings(self) -> None:
        """Test plugin ecosystem settings."""
        settings = UniversalSettings(
            plugins_enabled=False, plugin_marketplace=False, plugin_auto_discovery=False
        )

        assert settings.plugins_enabled is False
        assert settings.plugin_marketplace is False
        assert settings.plugin_auto_discovery is False
