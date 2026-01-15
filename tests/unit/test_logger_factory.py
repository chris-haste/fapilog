"""Tests for _prepare_logger() unified factory function."""

import pytest

from fapilog import Settings, _prepare_logger


class TestPrepareLoggerValidation:
    """Test mutual exclusivity validation in _prepare_logger()."""

    def test_format_and_settings_raises_value_error(self):
        """Cannot specify both format and settings."""
        with pytest.raises(
            ValueError, match="Cannot specify both 'format' and 'settings'"
        ):
            _prepare_logger(
                name=None,
                preset=None,
                format="json",
                settings=Settings(),
                sinks=None,
                auto_detect=False,
                environment=None,
            )

    def test_preset_and_settings_raises_value_error(self):
        """Cannot specify both preset and settings."""
        with pytest.raises(
            ValueError, match="Cannot specify both 'preset' and 'settings'"
        ):
            _prepare_logger(
                name=None,
                preset="dev",
                format=None,
                settings=Settings(),
                sinks=None,
                auto_detect=False,
                environment=None,
            )

    def test_environment_and_settings_raises_value_error(self):
        """Cannot specify both environment and settings."""
        with pytest.raises(
            ValueError, match="Cannot specify both 'environment' and 'settings'"
        ):
            _prepare_logger(
                name=None,
                preset=None,
                format=None,
                settings=Settings(),
                sinks=None,
                auto_detect=False,
                environment="docker",
            )

    def test_environment_and_preset_raises_value_error(self):
        """Cannot specify both environment and preset."""
        with pytest.raises(
            ValueError, match="Cannot specify both 'environment' and 'preset'"
        ):
            _prepare_logger(
                name=None,
                preset="dev",
                format=None,
                settings=None,
                sinks=None,
                auto_detect=False,
                environment="docker",
            )


class TestPrepareLoggerPresetResolution:
    """Test that _prepare_logger() applies presets correctly."""

    def test_dev_preset_returns_setup(self):
        """Dev preset returns a valid _LoggerSetup with expected structure."""
        setup, settings = _prepare_logger(
            name=None,
            preset="dev",
            format=None,
            settings=None,
            sinks=None,
            auto_detect=False,
            environment=None,
        )
        # Verify setup contains expected lists
        assert isinstance(setup.sinks, list)
        assert isinstance(setup.enrichers, list)
        # Verify settings is returned correctly
        assert isinstance(settings, Settings)

    def test_production_preset_returns_setup(self):
        """Production preset returns a valid _LoggerSetup."""
        setup, settings = _prepare_logger(
            name=None,
            preset="production",
            format=None,
            settings=None,
            sinks=None,
            auto_detect=False,
            environment=None,
        )
        # Verify setup has the settings attribute
        assert isinstance(setup.settings, Settings)
        assert isinstance(settings, Settings)

    def test_invalid_preset_raises_value_error(self):
        """Invalid preset name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid preset"):
            _prepare_logger(
                name=None,
                preset="nonexistent",
                format=None,
                settings=None,
                sinks=None,
                auto_detect=False,
                environment=None,
            )


class TestPrepareLoggerEnvironmentDetection:
    """Test that _prepare_logger() handles environment configuration."""

    def test_explicit_environment_returns_setup(self):
        """Explicit environment returns a valid setup."""
        setup, settings = _prepare_logger(
            name=None,
            preset=None,
            format=None,
            settings=None,
            sinks=None,
            auto_detect=False,
            environment="docker",
        )
        # Verify setup has required structure
        assert isinstance(setup.settings, Settings)
        assert isinstance(settings, Settings)

    def test_no_options_returns_default_setup(self):
        """No options returns a default setup."""
        setup, settings = _prepare_logger(
            name=None,
            preset=None,
            format=None,
            settings=None,
            sinks=None,
            auto_detect=False,
            environment=None,
        )
        # Verify default setup has expected structure
        assert isinstance(setup.settings, Settings)
        assert isinstance(settings, Settings)
        assert isinstance(setup.sinks, list)


class TestPrepareLoggerReturnType:
    """Test that _prepare_logger() returns the correct structure."""

    def test_returns_tuple_of_setup_and_settings(self):
        """Returns a tuple of (_LoggerSetup, Settings)."""
        result = _prepare_logger(
            name=None,
            preset=None,
            format=None,
            settings=None,
            sinks=None,
            auto_detect=False,
            environment=None,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

        setup, settings = result
        # Check setup has expected attributes
        assert hasattr(setup, "settings")
        assert hasattr(setup, "sinks")
        assert hasattr(setup, "enrichers")
        assert hasattr(setup, "redactors")
        assert hasattr(setup, "processors")
        assert hasattr(setup, "filters")

        # Check settings is a Settings instance
        assert isinstance(settings, Settings)
