"""
Fapilog Audit - Enterprise Compliance Audit Trails.

This package provides comprehensive audit trail functionality for enterprise
compliance, including error tracking, compliance reporting, security event
monitoring, and tamper-evident logging.

Installation:
    pip install fapilog-audit

Usage:
    from fapilog_audit import AuditSink, AuditTrail, CompliancePolicy

    # Use AuditSink with fapilog pipeline
    sink = AuditSink(AuditSinkConfig(compliance_level="sox"))
    await sink.start()

    # Or use AuditTrail directly
    trail = AuditTrail(policy=CompliancePolicy(level=ComplianceLevel.HIPAA))
    await trail.start()
    await trail.log_security_event(...)
"""

from .audit import (
    AuditChainVerificationResult,
    AuditEvent,
    AuditEventType,
    AuditLogLevel,
    AuditTrail,
    ComplianceLevel,
    CompliancePolicy,
    audit_error,
    audit_security_event,
    emit_compliance_alert,
    get_audit_trail,
    reset_all_audit_trails,
    reset_audit_trail,
)
from .compliance import (
    AuditConfig,
    DataHandlingSettings,
    validate_audit_config,
    validate_compliance_policy,
    validate_data_handling,
)
from .sink import AuditSink, AuditSinkConfig

__all__ = [
    # Core audit trail
    "AuditTrail",
    "AuditEvent",
    "AuditEventType",
    "AuditLogLevel",
    "AuditChainVerificationResult",
    # Policy and configuration
    "CompliancePolicy",
    "ComplianceLevel",
    "AuditConfig",
    "DataHandlingSettings",
    # Sink
    "AuditSink",
    "AuditSinkConfig",
    # Convenience functions
    "get_audit_trail",
    "audit_error",
    "audit_security_event",
    "emit_compliance_alert",
    # Instance management
    "reset_audit_trail",
    "reset_all_audit_trails",
    # Validation functions
    "validate_compliance_policy",
    "validate_data_handling",
    "validate_audit_config",
]
