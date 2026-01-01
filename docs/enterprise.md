# Enterprise Features

Fapilog provides building blocks for enterprise environments. This page highlights the compliance, audit, and security capabilities you can compose with fapilog and its add-ons. It is **not** a certification or a guarantee of regulatory compliance; you must validate controls for your own environment.

## At a Glance

| Capability | Description |
|------------|-------------|
| **Compliance Controls (assist)** | Policy templates and logging patterns that can be aligned to SOC2, HIPAA, GDPR, PCI-DSS, ISO 27001, SOX (you own control validation) |
| **Audit Trail** | Structured audit events with optional tamper-evident hash chains (via add-on) |
| **Data Protection** | PII/PHI tagging, redaction knobs, encryption settings |
| **Access Control** | Role-based access settings and auth mode configuration helpers |
| **Integrity** | SHA-256 checksums, sequence numbers, chain verification (when enabled) |

---

## Add-on spotlight: Tamper-Evident Logging + KMS/Vault

- **What**: `fapilog-tamper` add-on that adds per-record MAC/signatures, sealed manifests, and cross-file chain verification.
- **Key management**: Integrates with AWS KMS, GCP KMS, Azure Key Vault, and HashiCorp Vault (including KMS-native signing so keys never leave the provider). Optional extras: `fapilog-tamper[all-kms]`.
- **Docs**: See [Enterprise Key Management for Tamper-Evident Logging](enterprise/tamper-enterprise-key-management.md) for architecture, configuration, and deployment guidance.
- **Use cases**: Regulated audit trails (SOX/SOC2/HIPAA/PCI), shared services with centralized key custodians, and environments that require attested manifests for log rotation.

---

## Compliance Framework Support (assist, not certification)

Fapilog ships configuration helpers that can map to common frameworks. Use them as starting points and validate against your own policies and auditors:

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

### Example control mappings (non-exhaustive)

| Framework | Control areas this can help with |
|-----------|----------------------------------|
| **SOC2** | Encryption, integrity checks, access logging |
| **HIPAA** | PHI redaction, minimum necessary patterns, audit trails |
| **GDPR** | PII redaction, data subject request support (application responsibility) |
| **PCI-DSS** | Encryption at rest, access logging (card data handling remains your responsibility) |
| **ISO 27001** | Security logging and integrity controls |
| **SOX** | Change/event logging with chain verification |

---

## Audit Trail System

The `AuditTrail` building blocks provide structured audit logging. You control event content and ensure policies meet your regulatory scope:

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

# Ensure queued audit events are flushed before shutdown
await audit.stop()  # stop() drains pending events; use audit.drain() for manual flush
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

Audit events include integrity fields to detect tampering or gaps:

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
# Or verify directly from disk:
# result = await audit.verify_chain_from_storage()

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

Built-in redactors help mask common sensitive fields but must be tuned to your schemas and policies:

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

Configure encryption with support for enterprise key management. These are primitives; key custody and rotation remain your responsibility:

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

Configure role-based access control. Integrate with your identity provider and test according to your threat model:

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

Configure log retention to align with your data lifecycle requirements:

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
