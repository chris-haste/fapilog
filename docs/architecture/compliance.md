# Compliance Validation

## Overview

The `fapilog-audit` package provides enterprise compliance validation for audit trail configurations. This document describes the validation system, when it runs, and how to use it.

## Compliance Validation Strategy

**Decision: Integrated Validation**

Compliance validation is **automatically called during startup** when `AuditTrail.start()` is invoked with an enabled policy. This provides:

- Early detection of misconfigurations
- Clear warnings for compliance gaps
- Non-blocking behavior (warnings, not errors)

## How It Works

### Automatic Validation at Startup

When `AuditTrail.start()` is called with `policy.enabled=True`, the system:

1. Calls `validate_compliance_policy(policy)`
2. For each validation issue, emits a `UserWarning`
3. Continues startup regardless of validation results

```python
from fapilog_audit import AuditTrail, CompliancePolicy, ComplianceLevel

# Policy with issues will emit warnings at startup
policy = CompliancePolicy(
    level=ComplianceLevel.HIPAA,
    enabled=True,
    retention_days=10,  # Warning: must be >= 30
    hipaa_minimum_necessary=False,  # Warning: required for HIPAA
)

trail = AuditTrail(policy=policy)
await trail.start()  # Warnings emitted here
```

### Manual Pre-flight Validation

You can also validate policies explicitly before startup:

```python
from fapilog_audit import validate_compliance_policy, CompliancePolicy

policy = CompliancePolicy(...)
result = validate_compliance_policy(policy)

if not result.ok:
    for issue in result.issues:
        print(f"{issue.field}: {issue.message}")
```

## Validation Rules

### Baseline Rules (All Policies)

When `policy.enabled=True`:

| Field | Requirement | Message |
|-------|-------------|---------|
| `retention_days` | >= 30 | "must be >= 30" |
| `archive_after_days` | >= 7 | "must be >= 7" |
| `require_integrity_check` | True | "must be enabled" |

### Framework-Specific Rules

| Level | Field | Requirement |
|-------|-------|-------------|
| `HIPAA` | `hipaa_minimum_necessary` | Must be True |
| `GDPR` | `gdpr_data_subject_rights` | Must be True |
| `PCI_DSS`, `SOC2`, `ISO27001` | `require_integrity_check` | Must be True |

### Deferred Validations

The following are **not currently validated** because the features are not yet implemented:

| Field | Status | Roadmap |
|-------|--------|---------|
| `encrypt_audit_logs` | Skipped | Story 4.29 |

## Data Handling Validation

`validate_data_handling()` is an **opt-in utility** for validating `DataHandlingSettings`. It is NOT automatically called - use it explicitly when needed:

```python
from fapilog_audit import validate_data_handling, DataHandlingSettings, ComplianceLevel

settings = DataHandlingSettings(
    encryption_at_rest=True,
    encryption_in_transit=True,
)
result = validate_data_handling(level=ComplianceLevel.GDPR, settings=settings)
```

## Design Rationale

### Warnings vs Errors

Validation issues emit warnings rather than raising exceptions because:

1. **Backward Compatibility**: Existing configurations continue to work
2. **Observability**: Issues are logged for operators to address
3. **Non-Blocking**: Audit trails can start even with configuration gaps
4. **Progressive Adoption**: Teams can incrementally improve compliance

### Why Integrated (vs Opt-In)

The validation is integrated into `start()` rather than being purely opt-in because:

1. **Catches Misconfigurations Early**: Problems surface immediately, not in production
2. **Provides Enterprise Value**: Justifies the validation code's existence
3. **User Discovery**: Users see warnings without needing to know to call validation

## Related Stories

- Story 1.22: Integrate or Document Compliance Validation (this implementation)
- Story 4.29: Audit encryption config accuracy (encrypt_audit_logs feature)
