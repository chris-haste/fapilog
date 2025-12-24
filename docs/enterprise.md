# Enterprise Features

Fapilog is built for production use in enterprise environments. This page consolidates the compliance, audit, and security capabilities that differentiate fapilog from general-purpose logging libraries.

## At a Glance

| Capability | Description |
|------------|-------------|
| **Compliance Levels** | SOC2, HIPAA, GDPR, PCI-DSS, ISO 27001, SOX |
| **Audit Trail** | Structured audit events with tamper-evident hash chains |
| **Data Protection** | PII/PHI classification, redaction, encryption config |
| **Access Control** | Role-based access, auth mode configuration |
| **Integrity** | SHA-256 checksums, sequence numbers, chain verification |

---

## Compliance Framework Support

Fapilog provides configuration presets for major compliance frameworks:

```python
from fapilog.core.audit import ComplianceLevel, CompliancePolicy

# Configure for your compliance requirements
policy = CompliancePolicy(
    level=ComplianceLevel.SOC2,
    retention_days=365,
    encrypt_audit_logs=True,
    require_integrity_check=True,
    real_time_alerts=True,
)
```

### Supported Frameworks

| Framework | Key Features Enabled |
|-----------|---------------------|
| **SOC2** | Encryption, integrity checks, access logging |
| **HIPAA** | PHI redaction, minimum necessary rule, audit trails |
| **GDPR** | PII redaction, data subject rights support |
| **PCI-DSS** | Encryption at rest, access control validation |
| **ISO 27001** | Full security controls, integrity verification |
| **SOX** | Change control, audit trails |

---

## Audit Trail System

The `AuditTrail` class provides comprehensive audit logging for compliance:

```python
from fapilog.core.audit import AuditTrail, AuditEventType, CompliancePolicy

# Initialize audit trail
audit = AuditTrail(
    policy=CompliancePolicy(level=ComplianceLevel.SOC2),
    storage_path=Path("./audit_logs"),
)
await audit.start()

# Log security events
await audit.log_security_event(
    AuditEventType.AUTHENTICATION_FAILED,
    "Login attempt failed",
    user_id="user@example.com",
    client_ip="192.168.1.100",
)

# Log data access for compliance
await audit.log_data_access(
    resource="customer_records",
    operation="read",
    user_id="admin@example.com",
    data_classification="confidential",
    contains_pii=True,
)
```

### Audit Event Types

| Category | Event Types |
|----------|------------|
| **Security** | `AUTHENTICATION_FAILED`, `AUTHORIZATION_FAILED`, `SECURITY_VIOLATION` |
| **Data** | `DATA_ACCESS`, `DATA_MODIFICATION`, `DATA_DELETION`, `DATA_EXPORT` |
| **System** | `SYSTEM_STARTUP`, `SYSTEM_SHUTDOWN`, `COMPONENT_FAILURE` |
| **Config** | `CONFIG_CHANGED`, `PLUGIN_LOADED`, `PLUGIN_UNLOADED` |
| **Compliance** | `COMPLIANCE_CHECK`, `AUDIT_LOG_ACCESS`, `RETENTION_POLICY_APPLIED` |

---

## Tamper-Evident Hash Chains

Every audit event includes cryptographic integrity fields that enable detection of tampering or gaps:

```python
# Each AuditEvent automatically includes:
event.sequence_number  # Monotonic counter (gap detection)
event.previous_hash    # SHA-256 of previous event (chain linkage)
event.checksum         # SHA-256 of this event (integrity)
```

### Chain Verification

Verify integrity of audit logs at any time:

```python
from fapilog.core.audit import AuditTrail

# Load events from storage
events = await audit.get_events(
    start_time=datetime(2025, 1, 1),
    end_time=datetime(2025, 12, 31),
)

# Verify chain integrity
result = AuditTrail.verify_chain(events)

if result.valid:
    print(f"✓ {result.events_checked} events verified")
else:
    print(f"✗ Chain broken at sequence {result.first_invalid_sequence}")
    print(f"  Error: {result.error_message}")
```

### What Chain Verification Detects

- **Tampering** - Any modification to an event breaks the checksum
- **Deletion** - Missing events create sequence gaps
- **Insertion** - Added events break the hash chain
- **Reordering** - Events out of sequence fail validation

---

## Data Protection

### PII/PHI Classification

Flag events containing sensitive data:

```python
await audit.log_data_access(
    resource="patient_records",
    operation="read",
    contains_pii=True,    # Personally Identifiable Information
    contains_phi=True,    # Protected Health Information (HIPAA)
    data_classification="restricted",
)
```

### Automatic Redaction

Built-in redactors protect sensitive data in logs:

```python
from fapilog import get_logger, Settings

# Redactors are enabled by default
logger = get_logger()

# Sensitive fields are automatically masked
logger.info("User created", password="secret123", api_key="sk-xxx")
# Output: {"password": "***REDACTED***", "api_key": "***REDACTED***"}
```

**Built-in Redactors:**

| Redactor | What It Protects |
|----------|-----------------|
| `field-mask` | Named fields (password, secret, token, etc.) |
| `regex-mask` | Pattern-based detection (SSN, email, etc.) |
| `url-credentials` | Credentials in URLs (`user:pass@host`) |

See [Redaction Guarantees](redaction-guarantees.md) for configuration details.

### Encryption Configuration

Configure encryption with support for enterprise key management:

```python
from fapilog.core.encryption import EncryptionSettings

encryption = EncryptionSettings(
    enabled=True,
    algorithm="AES-256",
    key_source="vault",  # Options: env, file, kms, vault
    key_id="fapilog/audit-key",
    rotate_interval_days=90,
    min_tls_version="1.3",
)
```

**Key Sources:**

| Source | Use Case |
|--------|----------|
| `env` | Environment variable (development) |
| `file` | File path (on-prem) |
| `kms` | AWS KMS, GCP KMS, Azure Key Vault |
| `vault` | HashiCorp Vault |

---

## Access Control

Configure role-based access control:

```python
from fapilog.core.access_control import AccessControlSettings

access = AccessControlSettings(
    enabled=True,
    auth_mode="oauth2",  # Options: none, basic, token, oauth2
    allowed_roles=["admin", "auditor", "system"],
    require_admin_for_sensitive_ops=True,
    allow_anonymous_read=False,
    allow_anonymous_write=False,
)
```

---

## Retention Policies

Configure log retention for compliance:

```python
policy = CompliancePolicy(
    retention_days=365,      # Keep logs for 1 year
    archive_after_days=90,   # Archive after 90 days
    encrypt_audit_logs=True,
)
```

**Note:** Fapilog provides retention *configuration* as library primitives. Actual retention enforcement (deletion, archival) is the responsibility of your application or infrastructure.

---

## Compliance Validation

Validate your configuration against compliance baselines:

```python
from fapilog.core.compliance import validate_compliance_policy

result = validate_compliance_policy(policy)

if not result.ok:
    for issue in result.issues:
        print(f"[{issue.severity}] {issue.field}: {issue.message}")
```

**Example validation output:**

```
[error] retention_days: must be >= 30
[error] encrypt_audit_logs: must be enabled
[warn] gdpr_data_subject_rights: required for GDPR level
```

---

## Real-Time Compliance Alerts

Configure alerts for compliance-relevant events:

```python
policy = CompliancePolicy(
    real_time_alerts=True,
    alert_on_critical_errors=True,
    alert_on_security_events=True,
)
```

When enabled, security events and critical errors trigger the alert pathway. Implement your alerting logic via a custom sink:

```python
class ComplianceAlertSink:
    async def write(self, entry: dict) -> None:
        if entry.get("log_level") == "SECURITY":
            await send_to_pagerduty(entry)
            await send_to_slack(entry)
```

---

## Integration with Enterprise Systems

### SIEM Integration

Audit events export cleanly for SIEM ingestion:

```python
# Events provide structured data for SIEM transformation
event_dict = event.model_dump()

# Transform to your SIEM format (CEF, LEEF, etc.)
cef_line = transform_to_cef(event_dict)
```

### Log Aggregation

Fapilog's JSON output integrates with standard log aggregators:

- **Splunk** - JSON logs ingest directly
- **Elasticsearch** - Structured fields map to indices
- **Datadog** - Labels and metadata propagate
- **CloudWatch** - JSON Insights queries work out of the box

---

## Quick Reference: Compliance Checklist

| Requirement | Fapilog Feature | Configuration |
|-------------|-----------------|---------------|
| Audit trail | `AuditTrail` | `CompliancePolicy.enabled=True` |
| Log integrity | Hash chains | Automatic (sequence + checksum) |
| PII protection | Redactors | `core.enable_redactors=True` |
| Encryption config | `EncryptionSettings` | `encryption.enabled=True` |
| Access control | `AccessControlSettings` | `access_control.enabled=True` |
| Retention policy | `CompliancePolicy` | `retention_days=365` |
| Security events | `AuditEventType` | `log_security_event()` |
| Data classification | Event flags | `contains_pii`, `data_classification` |

---

## Further Reading

- [Redaction Guarantees](redaction-guarantees.md) - PII/secret protection
- [Core Concepts: Redaction](core-concepts/redaction.md) - Redactor configuration
- [API Reference: Configuration](api-reference/configuration.md) - Settings reference

