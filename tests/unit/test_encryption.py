from __future__ import annotations

import pytest

from fapilog.core.encryption import (
    EncryptionSettings,
    validate_encryption,
    validate_encryption_async,
)


def test_validate_encryption_disabled_warns() -> None:
    s = EncryptionSettings(enabled=False)
    r = validate_encryption(s)
    assert r.ok is True
    assert any(i.field == "enabled" and i.severity == "warn" for i in r.issues)


def test_validate_encryption_missing_key_source_warns() -> None:
    s = EncryptionSettings(enabled=True, key_source=None)
    r = validate_encryption(s)
    assert r.ok is True
    assert any(i.field == "key_source" and i.severity == "warn" for i in r.issues)


def test_validate_encryption_env_requires_var() -> None:
    s = EncryptionSettings(enabled=True, key_source="env", env_var_name=None)
    r = validate_encryption(s)
    assert r.ok is False
    assert any(i.field == "env_var_name" for i in r.issues)


def test_validate_encryption_file_requires_path() -> None:
    s = EncryptionSettings(enabled=True, key_source="file", key_file_path=None)
    r = validate_encryption(s)
    assert r.ok is False
    assert any(i.field == "key_file_path" for i in r.issues)


def test_validate_encryption_kms_requires_key_id() -> None:
    s = EncryptionSettings(enabled=True, key_source="kms", key_id=None)
    r = validate_encryption(s)
    assert r.ok is False
    assert any(i.field == "key_id" for i in r.issues)


def test_validate_encryption_vault_requires_key_id() -> None:
    s = EncryptionSettings(enabled=True, key_source="vault", key_id=None)
    r = validate_encryption(s)
    assert r.ok is False
    assert any(i.field == "key_id" for i in r.issues)


def test_validate_encryption_warns_aes128_and_rotation_and_tls() -> None:
    s = EncryptionSettings(
        enabled=True,
        key_source="env",
        env_var_name="KEY",
        algorithm="AES-128",
        rotate_interval_days=366,
        min_tls_version="1.2",
    )
    r = validate_encryption(s)
    fields = {i.field for i in r.issues}
    assert r.ok is True
    assert {"algorithm", "rotate_interval_days", "min_tls_version"}.issubset(fields)


@pytest.mark.asyncio
async def test_validate_encryption_async_file_exists(tmp_path) -> None:
    key_path = tmp_path / "app.key"
    key_path.write_text("secret")
    s = EncryptionSettings(enabled=True, key_source="file", key_file_path=str(key_path))
    r = await validate_encryption_async(s)
    assert r.ok is True
    assert all(i.field != "key_file_path" for i in r.issues)
