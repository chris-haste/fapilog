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
