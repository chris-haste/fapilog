# Enterprise Features

Fapilog provides building blocks for enterprise environments. This page highlights the compliance, audit, and security capabilities you can compose with fapilog and its add-ons. It is **not** a certification or a guarantee of regulatory compliance; you must validate controls for your own environment.

## At a Glance

| Capability | Description |
|------------|-------------|
| **Compliance Controls (assist)** | Policy templates and logging patterns that can be aligned to SOC2, HIPAA, GDPR, PCI-DSS, ISO 27001, SOX (you own control validation) |
| **Audit Trail** | Structured audit events with optional tamper-evident hash chains (via add-on) |
| **Data Protection** | PII/PHI tagging, redaction configuration |
| **Access Control** | Role-based access settings and auth mode configuration helpers |
| **Integrity** | SHA-256 checksums, sequence numbers, chain verification (when enabled) |

---

## Built-in Audit Sink

- Enable compliance logging via `core.sinks = ["audit"]`; configure with `sink_config.audit.*`
- Uses the existing `AuditTrail` with hash-chain integrity and compliance metadata
- See [Audit Sink (Compliance Trail)](enterprise/audit-sink.md) for configuration and verification

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
from fapilog_audit import ComplianceLevel, CompliancePolicy

# Configure for your compliance requirements
policy = CompliancePolicy(
    level=ComplianceLevel.SOC2,
    retention_days=365,
    require_integrity_check=True,
    real_time_alerts=True,
)
```

### Example control mappings (non-exhaustive)

| Framework | Control areas this can help with | Redaction Preset |
|-----------|----------------------------------|------------------|
| **SOC2** | Integrity checks, access logging, audit trails | `CREDENTIALS` |
| **HIPAA** | PHI redaction, minimum necessary patterns, audit trails | `HIPAA_PHI` |
| **GDPR** | PII redaction, data subject request support (application responsibility) | `GDPR_PII` |
| **PCI-DSS** | Access logging, audit trails (encryption and card data handling are your responsibility) | `PCI_DSS` |
| **ISO 27001** | Security logging and integrity controls | `CREDENTIALS` |
| **SOX** | Change/event logging with chain verification | `CREDENTIALS` |

See [Redaction Presets](redaction/presets.md) for complete field lists covered by each preset.

---

## Audit Trail System

The `AuditTrail` building blocks provide structured audit logging. You control event content and ensure policies meet your regulatory scope:

```python
from fapilog_audit import AuditTrail, AuditEventType, ComplianceLevel, CompliancePolicy

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
from fapilog_audit import AuditTrail

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

Fapilog provides compliance-focused redaction presets that automatically protect sensitive fields:

```python
from fapilog import LoggerBuilder

# HIPAA: Protects PHI (18 identifier categories)
logger = LoggerBuilder().with_redaction(preset="HIPAA_PHI").build()

# GDPR: Protects EU personal data
logger = LoggerBuilder().with_redaction(preset="GDPR_PII").build()

# PCI-DSS: Protects cardholder data
logger = LoggerBuilder().with_redaction(preset="PCI_DSS").build()

# Multiple regulations
logger = (
    LoggerBuilder()
    .with_redaction(preset=["HIPAA_PHI", "PCI_DSS", "CREDENTIALS"])
    .build()
)
```

**Compliance Presets:**

| Preset | Regulation | What It Protects |
|--------|------------|------------------|
| `HIPAA_PHI` | HIPAA | MRN, SSN, DOB, contact info, 18 PHI identifiers |
| `GDPR_PII` | GDPR | Email, phone, name, IP, national IDs, 70+ fields |
| `GDPR_PII_UK` | UK-GDPR | All GDPR fields plus NHS number, NI number |
| `PCI_DSS` | PCI-DSS | Card numbers, CVV, expiry, cardholder name |
| `CCPA_PII` | CCPA | California personal information |
| `CREDENTIALS` | N/A | Passwords, API keys, tokens, secrets |

See [Redaction Presets](redaction/presets.md) for complete field lists.

> **Important:** Redaction matches field names, not field content. PII embedded in message strings is not redacted. See [Compliance Redaction Cookbook](cookbook/compliance-redaction.md) for what works and what doesn't.

---

## Access Control

> **Note:** `AccessControlSettings` provides configuration primitives only. Fapilog does not enforce access control - you must integrate these settings with your identity provider and application middleware.

Define access control policies using the configuration model:

```python
from fapilog.core.access_control import AccessControlSettings, validate_access_control

access = AccessControlSettings(
    enabled=True,
    auth_mode="oauth2",  # Options: none, basic, token, oauth2
    allowed_roles=["admin", "auditor", "system"],
    require_admin_for_sensitive_ops=True,
    allow_anonymous_read=False,
    allow_anonymous_write=False,
)

# Validate configuration against security baselines
result = validate_access_control(access)
if not result.ok:
    for issue in result.issues:
        print(f"{issue.field}: {issue.message}")
```

**Integration responsibility:** Use these settings to configure your authentication middleware, API gateway, or application-level access checks. For example:

```python
# Example: FastAPI dependency using AccessControlSettings
async def require_role(role: str, settings: AccessControlSettings = Depends(get_settings)):
    if not settings.enabled:
        return
    if role not in settings.allowed_roles:
        raise HTTPException(403, "Insufficient permissions")
```

---

## Retention Policies

Configure log retention to align with your data lifecycle requirements:

```python
policy = CompliancePolicy(
    retention_days=365,      # Keep logs for 1 year
    archive_after_days=90,   # Archive after 90 days
)
```

**Note:** Fapilog provides retention *configuration* as library primitives. Actual retention enforcement (deletion, archival) is the responsibility of your application or infrastructure.

---

## Compliance Validation

Validate your configuration against compliance baselines:

```python
from fapilog_audit import validate_compliance_policy

result = validate_compliance_policy(policy)

if not result.ok:
    for issue in result.issues:
        print(f"[{issue.severity}] {issue.field}: {issue.message}")
```

**Example validation output:**

```
[error] retention_days: must be >= 30
[error] require_integrity_check: must be enabled
[error] gdpr_data_subject_rights: required
```

---

## Real-Time Compliance Alerts

> **Note:** Alert *detection* is implemented, but alert *delivery* is a stub. You must provide your own alerting integration.

Configure which events should trigger alerts:

```python
policy = CompliancePolicy(
    real_time_alerts=True,
    alert_on_critical_errors=True,
    alert_on_security_events=True,
)
```

When these flags are enabled, the `AuditTrail` identifies events that should trigger alerts (security events, critical errors, PII access for GDPR, PHI access for HIPAA). However, the actual alert delivery is not implemented - you must integrate your own alerting system.

**Option 1: Custom sink for alert routing**

```python
class ComplianceAlertSink:
    async def write(self, entry: dict) -> None:
        if entry.get("log_level") == "SECURITY":
            await send_to_pagerduty(entry)
            await send_to_slack(entry)
```

**Option 2: Subclass AuditTrail and override `_send_compliance_alert`**

```python
class MyAuditTrail(AuditTrail):
    async def _send_compliance_alert(self, event: AuditEvent) -> None:
        await send_to_pagerduty(event.model_dump())
        await send_to_slack(event.message)
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
| URL credential protection | `url_credentials` redactor | Enabled by default |
| HIPAA PHI redaction | `HIPAA_PHI` preset | `.with_redaction(preset="HIPAA_PHI")` |
| GDPR PII redaction | `GDPR_PII` preset | `.with_redaction(preset="GDPR_PII")` |
| PCI-DSS redaction | `PCI_DSS` preset | `.with_redaction(preset="PCI_DSS")` |
| Credential redaction | `CREDENTIALS` preset | `.with_redaction(preset="CREDENTIALS")` |
| Access control | `AccessControlSettings` | `access_control.enabled=True` |
| Retention policy | `CompliancePolicy` | `retention_days=365` |
| Security events | `AuditEventType` | `log_security_event()` |
| Data classification | Event flags | `contains_pii`, `data_classification` |

---

## Further Reading

- [Redaction Presets](redaction/presets.md) - Complete field lists for HIPAA, GDPR, PCI-DSS
- [Compliance Redaction Cookbook](cookbook/compliance-redaction.md) - What works and what doesn't
- [Redaction Configuration](redaction/configuration.md) - Builder API and settings
- [API Reference: Configuration](api-reference/configuration.md) - Settings reference
