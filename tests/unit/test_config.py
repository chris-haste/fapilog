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
