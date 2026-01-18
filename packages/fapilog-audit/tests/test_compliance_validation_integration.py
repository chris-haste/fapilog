"""Tests for compliance validation integration with AuditTrail.start()."""

import warnings
from pathlib import Path

import pytest

from fapilog_audit import AuditTrail, ComplianceLevel, CompliancePolicy


@pytest.fixture
def tmp_storage(tmp_path: Path) -> Path:
    """Provide a temporary storage path."""
    return tmp_path / "audit"


class TestComplianceValidationAtStartup:
    """Tests for compliance validation during AuditTrail.start()."""

    @pytest.mark.asyncio
    async def test_start_validates_policy_when_enabled(self, tmp_storage: Path) -> None:
        """Validation warnings are emitted for policy issues when enabled."""
        policy = CompliancePolicy(
            enabled=True,
            retention_days=10,  # Below minimum of 30
            archive_after_days=3,  # Below minimum of 7
            require_integrity_check=False,  # Should be True
        )
        trail = AuditTrail(policy=policy, storage_path=tmp_storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await trail.start()

            # Should have warnings for validation issues
            compliance_warnings = [
                warning for warning in w if "Compliance:" in str(warning.message)
            ]
            assert len(compliance_warnings) >= 3

            # Check specific warnings
            warning_messages = [str(warning.message) for warning in compliance_warnings]
            assert any("retention_days" in msg for msg in warning_messages)
            assert any("archive_after_days" in msg for msg in warning_messages)
            assert any("require_integrity_check" in msg for msg in warning_messages)

        await trail.stop()

    @pytest.mark.asyncio
    async def test_start_skips_validation_when_disabled(
        self, tmp_storage: Path
    ) -> None:
        """Validation is skipped when policy is disabled."""
        policy = CompliancePolicy(
            enabled=False,
            retention_days=10,  # Would fail if validated
            archive_after_days=3,
        )
        trail = AuditTrail(policy=policy, storage_path=tmp_storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await trail.start()

            # No compliance validation warnings when disabled
            compliance_warnings = [
                warning for warning in w if "Compliance:" in str(warning.message)
            ]
            assert len(compliance_warnings) == 0

        await trail.stop()

    @pytest.mark.asyncio
    async def test_start_no_warnings_for_valid_policy(self, tmp_storage: Path) -> None:
        """No warnings when policy meets all requirements."""
        policy = CompliancePolicy(
            enabled=True,
            retention_days=365,
            archive_after_days=90,
            require_integrity_check=True,
        )
        trail = AuditTrail(policy=policy, storage_path=tmp_storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await trail.start()

            # No compliance warnings for valid policy
            compliance_warnings = [
                warning for warning in w if "Compliance:" in str(warning.message)
            ]
            assert len(compliance_warnings) == 0

        await trail.stop()

    @pytest.mark.asyncio
    async def test_start_warns_for_hipaa_missing_minimum_necessary(
        self, tmp_storage: Path
    ) -> None:
        """HIPAA level warns when hipaa_minimum_necessary is False."""
        policy = CompliancePolicy(
            level=ComplianceLevel.HIPAA,
            enabled=True,
            retention_days=365,
            archive_after_days=90,
            require_integrity_check=True,
            hipaa_minimum_necessary=False,  # Required for HIPAA
        )
        trail = AuditTrail(policy=policy, storage_path=tmp_storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await trail.start()

            compliance_warnings = [
                warning for warning in w if "Compliance:" in str(warning.message)
            ]
            warning_messages = [str(warning.message) for warning in compliance_warnings]
            assert any("hipaa_minimum_necessary" in msg for msg in warning_messages)

        await trail.stop()

    @pytest.mark.asyncio
    async def test_start_warns_for_gdpr_missing_data_subject_rights(
        self, tmp_storage: Path
    ) -> None:
        """GDPR level warns when gdpr_data_subject_rights is False."""
        policy = CompliancePolicy(
            level=ComplianceLevel.GDPR,
            enabled=True,
            retention_days=365,
            archive_after_days=90,
            require_integrity_check=True,
            gdpr_data_subject_rights=False,  # Required for GDPR
        )
        trail = AuditTrail(policy=policy, storage_path=tmp_storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await trail.start()

            compliance_warnings = [
                warning for warning in w if "Compliance:" in str(warning.message)
            ]
            warning_messages = [str(warning.message) for warning in compliance_warnings]
            assert any("gdpr_data_subject_rights" in msg for msg in warning_messages)

        await trail.stop()
