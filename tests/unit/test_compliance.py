from fapilog.core.audit import ComplianceLevel, CompliancePolicy
from fapilog.core.compliance import (
    AuditConfig,
    DataHandlingSettings,
    validate_audit_config,
    validate_compliance_policy,
    validate_data_handling,
)


def test_validate_compliance_policy_requires_baselines() -> None:
    policy = CompliancePolicy(
        level=ComplianceLevel.BASIC,
        enabled=True,
        retention_days=10,
        archive_after_days=3,
        encrypt_audit_logs=False,
        require_integrity_check=False,
    )

    result = validate_compliance_policy(policy)
    assert result.ok is False
    assert any(i.field == "retention_days" for i in result.issues)
    assert any(i.field == "archive_after_days" for i in result.issues)
    assert any(i.field == "encrypt_audit_logs" for i in result.issues)
    assert any(i.field == "require_integrity_check" for i in result.issues)


def test_validate_framework_specific_requirements() -> None:
    policy = CompliancePolicy(
        level=ComplianceLevel.HIPAA, hipaa_minimum_necessary=False
    )
    result = validate_compliance_policy(policy)
    assert result.ok is False
    assert any(i.field == "hipaa_minimum_necessary" for i in result.issues)

    policy = CompliancePolicy(
        level=ComplianceLevel.GDPR, gdpr_data_subject_rights=False
    )
    result = validate_compliance_policy(policy)
    assert result.ok is False
    assert any(i.field == "gdpr_data_subject_rights" for i in result.issues)


def test_validate_data_handling_baselines_and_frameworks() -> None:
    dh = DataHandlingSettings(
        encryption_at_rest=False,
        encryption_in_transit=False,
        allow_default_credentials=True,
        min_password_length=8,
        pii_redaction_enabled=False,
        phi_redaction_enabled=False,
    )
    result = validate_data_handling(level=ComplianceLevel.BASIC, settings=dh)
    assert result.ok is False
    assert any(i.field == "encryption_in_transit" for i in result.issues)
    assert any(i.field == "encryption_at_rest" for i in result.issues)
    assert any(i.field == "allow_default_credentials" for i in result.issues)
    assert any(i.field == "min_password_length" for i in result.issues)

    # HIPAA requires PHI redaction
    result = validate_data_handling(level=ComplianceLevel.HIPAA, settings=dh)
    assert any(i.field == "phi_redaction_enabled" for i in result.issues)

    # GDPR requires PII redaction
    result = validate_data_handling(level=ComplianceLevel.GDPR, settings=dh)
    assert any(i.field == "pii_redaction_enabled" for i in result.issues)


def test_validate_audit_config_delegates() -> None:
    policy = CompliancePolicy(enabled=True, retention_days=5)
    result = validate_audit_config(AuditConfig(policy=policy))
    assert result.ok is False
    assert any(i.field == "retention_days" for i in result.issues)
