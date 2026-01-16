"""Tests for audit encryption configuration accuracy (Story 4.29)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from fapilog.core.audit import AuditTrail, CompliancePolicy
from fapilog.plugins.sinks.audit import AuditSink, AuditSinkConfig


class TestCompliancePolicyDefault:
    """Tests for CompliancePolicy.encrypt_audit_logs default value."""

    def test_default_encrypt_audit_logs_is_false(self) -> None:
        """Default should be False since encryption is not implemented."""
        policy = CompliancePolicy()
        assert policy.encrypt_audit_logs is False

    def test_explicit_false_is_allowed(self) -> None:
        """Explicitly setting False should work without issue."""
        policy = CompliancePolicy(encrypt_audit_logs=False)
        assert policy.encrypt_audit_logs is False


class TestAuditTrailEncryptionWarning:
    """Tests for warning when encrypt_audit_logs=True."""

    def test_warning_when_encrypt_audit_logs_true(self, tmp_path: Path) -> None:
        """Should emit warning when encrypt_audit_logs=True."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            policy = CompliancePolicy(encrypt_audit_logs=True)
            _ = AuditTrail(policy=policy, storage_path=tmp_path)

            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)
            assert "not yet implemented" in str(w[0].message).lower()

    def test_no_warning_when_encrypt_audit_logs_false(self, tmp_path: Path) -> None:
        """Should not emit warning when encrypt_audit_logs=False."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            policy = CompliancePolicy(encrypt_audit_logs=False)
            _ = AuditTrail(policy=policy, storage_path=tmp_path)

            # Filter for UserWarning only (ignore any other warnings)
            user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(user_warnings) == 0

    def test_no_warning_with_default_policy(self, tmp_path: Path) -> None:
        """Should not emit warning with default policy (which defaults to False)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = AuditTrail(storage_path=tmp_path)

            user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(user_warnings) == 0


class TestAuditSinkConfigDefault:
    """Tests for AuditSinkConfig.encrypt_logs default value."""

    def test_default_encrypt_logs_is_false(self) -> None:
        """Default should be False since encryption is not implemented."""
        config = AuditSinkConfig()
        assert config.encrypt_logs is False

    def test_explicit_false_is_allowed(self) -> None:
        """Explicitly setting False should work without issue."""
        config = AuditSinkConfig(encrypt_logs=False)
        assert config.encrypt_logs is False


class TestAuditSinkEncryptionWarning:
    """Tests for warning when AuditSink encrypt_logs=True."""

    @pytest.mark.asyncio
    async def test_warning_when_encrypt_logs_true(self, tmp_path: Path) -> None:
        """Should emit warning when encrypt_logs=True on sink start."""
        config = AuditSinkConfig(encrypt_logs=True, storage_path=str(tmp_path))
        sink = AuditSink(config=config)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await sink.start()
            await sink.stop()

            # Exactly one encryption warning should be emitted
            encryption_warnings = [
                x
                for x in w
                if issubclass(x.category, UserWarning)
                and "not yet implemented" in str(x.message).lower()
            ]
            assert len(encryption_warnings) == 1

    @pytest.mark.asyncio
    async def test_no_warning_when_encrypt_logs_false(self, tmp_path: Path) -> None:
        """Should not emit warning when encrypt_logs=False."""
        config = AuditSinkConfig(encrypt_logs=False, storage_path=str(tmp_path))
        sink = AuditSink(config=config)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await sink.start()
            await sink.stop()

            user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(user_warnings) == 0
