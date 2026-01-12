"""Integration tests for Settings with string configuration."""

import pytest
from pydantic import ValidationError

from fapilog import Settings
from fapilog.core.settings import RotatingFileSettings, WebhookSettings


class TestRotatingFileSettingsStrings:
    """Test RotatingFileSettings with string values."""

    def test_all_fields_accept_strings(self) -> None:
        """All size/duration fields accept strings."""
        settings = RotatingFileSettings(
            max_bytes="10 MB",
            interval_seconds="1h",
            max_total_bytes="100 MB",
        )

        assert settings.max_bytes == 10 * 1024 * 1024
        assert settings.interval_seconds == 3600.0
        assert settings.max_total_bytes == 100 * 1024 * 1024

    def test_rotation_keywords(self) -> None:
        """Rotation keywords work."""
        settings = RotatingFileSettings(interval_seconds="hourly")
        assert settings.interval_seconds == 3600.0

        settings = RotatingFileSettings(interval_seconds="daily")
        assert settings.interval_seconds == 86400.0

    def test_mixed_strings_and_integers(self) -> None:
        """Strings and integers can be mixed."""
        settings = RotatingFileSettings(
            max_bytes="10 MB",
            interval_seconds=3600,
            max_files=7,
            max_total_bytes="50 MB",
        )

        assert settings.max_bytes == 10 * 1024 * 1024
        assert settings.interval_seconds == 3600.0
        assert settings.max_files == 7
        assert settings.max_total_bytes == 50 * 1024 * 1024

    def test_backward_compatibility(self) -> None:
        """Existing integer config still works."""
        settings = RotatingFileSettings(
            max_bytes=10485760,
            interval_seconds=86400,
            max_total_bytes=104857600,
        )

        assert settings.max_bytes == 10485760
        assert settings.interval_seconds == 86400.0
        assert settings.max_total_bytes == 104857600


class TestWebhookSettingsStrings:
    """Test WebhookSettings with string durations."""

    def test_timeout_accepts_string(self) -> None:
        """timeout_seconds accepts string."""
        settings = WebhookSettings(
            endpoint="https://example.com/webhook",
            timeout_seconds="10s",
        )

        assert settings.timeout_seconds == 10.0

    def test_all_duration_fields_accept_strings(self) -> None:
        """All duration fields accept strings."""
        settings = WebhookSettings(
            endpoint="https://example.com/webhook",
            timeout_seconds="30s",
            retry_backoff_seconds="2s",
            batch_timeout_seconds="5s",
        )

        assert settings.timeout_seconds == 30.0
        assert settings.retry_backoff_seconds == 2.0
        assert settings.batch_timeout_seconds == 5.0


class TestSettingsValidationErrors:
    """Test validation error messages."""

    def test_invalid_size_error_message(self) -> None:
        """Invalid size shows clear error."""
        with pytest.raises(ValidationError) as exc_info:
            RotatingFileSettings(max_bytes="10 XB")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "max_bytes" in str(errors[0]["loc"])
        assert "Invalid size format" in str(errors[0]["ctx"]["error"])
        assert "'10 XB'" in str(errors[0]["ctx"]["error"])

    def test_invalid_duration_error_message(self) -> None:
        """Invalid duration shows clear error."""
        with pytest.raises(ValidationError) as exc_info:
            RotatingFileSettings(interval_seconds="10x")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "interval_seconds" in str(errors[0]["loc"])
        assert "Invalid duration format" in str(errors[0]["ctx"]["error"])


class TestSettingsWithPreset:
    """Test Settings with preset and string overrides."""

    def test_preset_with_string_overrides(self) -> None:
        """Preset + string overrides work together."""
        settings = Settings(
            sink_config=Settings.SinkConfig(
                rotating_file=RotatingFileSettings(
                    max_bytes="50 MB",
                    interval_seconds="daily",
                )
            )
        )

        assert settings.sink_config.rotating_file.max_bytes == 50 * 1024 * 1024
        assert settings.sink_config.rotating_file.interval_seconds == 86400.0


class TestEnvironmentVariableParsing:
    """Test environment variable string format support."""

    def test_env_var_string_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables can use string formats for sizes."""
        monkeypatch.setenv("FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_BYTES", "10 MB")
        settings = Settings()
        assert settings.sink_config.rotating_file.max_bytes == 10 * 1024 * 1024

    def test_env_var_string_duration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables can use string formats for durations."""
        monkeypatch.setenv(
            "FAPILOG_SINK_CONFIG__ROTATING_FILE__INTERVAL_SECONDS", "daily"
        )
        settings = Settings()
        assert settings.sink_config.rotating_file.interval_seconds == 86400.0

    def test_env_var_quoted_strings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Quoted strings in env vars are handled."""
        monkeypatch.setenv("FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_BYTES", '"10 MB"')
        settings = Settings()
        assert settings.sink_config.rotating_file.max_bytes == 10 * 1024 * 1024
