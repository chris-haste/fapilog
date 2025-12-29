from typing import Any, Mapping

import pytest

from fapilog.core.config import load_settings


@pytest.mark.asyncio
async def test_load_settings_defaults_env_prefix() -> None:
    # Ensure clean environment
    env: Mapping[str, str] = {}
    settings = await load_settings(env=env)
    assert settings.schema_version == "1.0"
    assert settings.core.app_name == "fapilog"
    assert settings.core.log_level == "INFO"
    assert settings.core.max_queue_size == 10_000
    # New groups exist with defaults
    assert settings.security.encryption.enabled is True
    assert settings.observability.metrics.enabled is False


@pytest.mark.asyncio
async def test_env_nested_overrides_take_effect() -> None:
    env = {
        "FAPILOG_CORE__APP_NAME": "demo-app",
        "FAPILOG_CORE__LOG_LEVEL": "DEBUG",
        "FAPILOG_CORE__MAX_QUEUE_SIZE": "1234",
    }
    settings = await load_settings(env=env)
    assert settings.core.app_name == "demo-app"
    assert settings.core.log_level == "DEBUG"
    assert settings.core.max_queue_size == 1234
    # Observability defaults apply
    assert settings.observability.metrics.port == 8000


@pytest.mark.asyncio
async def test_runtime_overrides_merge_safely(tmp_path: Any) -> None:
    # Provide an existing file to satisfy async validation if path is set
    existing = tmp_path / "bench.txt"
    existing.write_text("ok")

    env = {
        "FAPILOG_CORE__APP_NAME": "base-name",
        "FAPILOG_CORE__ENABLE_METRICS": "true",
    }
    settings = await load_settings(
        env=env,
        overrides={
            "core": {
                "app_name": "override-name",
                "benchmark_file_path": str(existing),
            }
        },
    )

    assert settings.core.app_name == "override-name"
    assert settings.core.enable_metrics is True
    assert settings.core.benchmark_file_path == str(existing)
    # Security default remains
    assert settings.security.access_control.enabled is True


@pytest.mark.asyncio
async def test_schema_version_mismatch_raises() -> None:
    env = {
        "FAPILOG_SCHEMA_VERSION": "0.9",
    }
    with pytest.raises(Exception) as exc:
        await load_settings(env=env)
    assert "Unsupported settings schema_version" in str(exc.value)


@pytest.mark.asyncio
async def test_async_validation_missing_path_raises(tmp_path: Any) -> None:
    missing = tmp_path / "does_not_exist.txt"
    env = {
        "FAPILOG_CORE__BENCHMARK_FILE_PATH": str(missing),
    }
    with pytest.raises(Exception) as exc:
        await load_settings(env=env)
    assert "does not exist" in str(exc.value)


@pytest.mark.asyncio
async def test_load_settings_without_env_uses_os_environ() -> None:
    """Test load_settings when env=None uses os.environ directly."""
    import os

    # Set a test env var
    original_value = os.environ.get("FAPILOG_CORE__APP_NAME")
    try:
        os.environ["FAPILOG_CORE__APP_NAME"] = "from-os-environ"
        settings = await load_settings(env=None)
        assert settings.core.app_name == "from-os-environ"
    finally:
        if original_value is not None:
            os.environ["FAPILOG_CORE__APP_NAME"] = original_value
        elif "FAPILOG_CORE__APP_NAME" in os.environ:
            del os.environ["FAPILOG_CORE__APP_NAME"]


@pytest.mark.asyncio
async def test_load_settings_pydantic_validation_error() -> None:
    """Test load_settings handles PydanticValidationError."""
    from unittest.mock import patch

    from pydantic import ValidationError as PydanticValidationError

    from fapilog.core.config import ConfigurationError

    # Mock Settings to raise PydanticValidationError during validation
    with patch("fapilog.core.config.Settings") as mock_settings:
        mock_instance = mock_settings.return_value
        mock_instance.schema_version = "1.0"
        # Create a PydanticValidationError by trying to validate invalid data
        # This is a simpler way to get a real ValidationError
        try:
            from fapilog.core.settings import Settings

            # This will raise ValidationError
            Settings.model_validate({"core": {"app_name": 123}})  # Invalid type
        except PydanticValidationError as e:
            validation_error = e

        mock_instance.validate_async.side_effect = validation_error

        with pytest.raises(ConfigurationError) as exc_info:
            await load_settings(env={})
        assert "Pydantic validation failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_load_settings_generic_exception_handling() -> None:
    """Test load_settings handles generic exceptions during async validation."""
    from unittest.mock import patch

    from fapilog.core.config import ConfigurationError

    # Mock validate_async to raise a generic exception
    with patch("fapilog.core.config.Settings") as mock_settings:
        mock_instance = mock_settings.return_value
        mock_instance.schema_version = "1.0"
        mock_instance.validate_async.side_effect = ValueError("Unexpected error")

        with pytest.raises(ConfigurationError) as exc_info:
            await load_settings(env={})
        assert "Async settings validation failed" in str(exc_info.value)
