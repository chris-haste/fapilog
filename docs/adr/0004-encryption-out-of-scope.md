# ADR-0004: Encryption Out of Scope

**Status:** Accepted
**Date:** 2026-01-19

## Context

The enterprise features documentation and codebase included `EncryptionSettings` configuration models and references to `encrypt_audit_logs` in `CompliancePolicy`. However, encryption was never actually implemented - the code contained stubs, warnings ("encryption not yet implemented"), and skipped validation for encryption-related fields.

Questions arose about whether fapilog should implement encryption:
- Log encryption at rest
- Key management integration (KMS, Vault)
- Encrypted transport configuration

## Decision

Encryption is **out of scope** for fapilog. Users are responsible for encryption at the infrastructure level.

### Rationale

1. **Infrastructure-level concern**: Encryption at rest is better handled by the storage layer (encrypted filesystems, cloud storage encryption, database encryption). Fapilog writing encrypted files would duplicate what infrastructure already provides.

2. **Transport encryption**: TLS configuration belongs to the HTTP client/server layer, not the logging library. Fapilog's HTTP sink relies on the underlying HTTP client for TLS.

3. **Complexity vs value**: Implementing encryption correctly (key management, rotation, algorithm selection, secure key storage) is a significant undertaking that would duplicate existing, battle-tested solutions.

4. **Separation of concerns**: A logging library should focus on structured log generation, redaction, and routing. Encryption is orthogonal and better solved by specialized tools.

### Recommended Alternatives

Users requiring encryption should use:

| Requirement | Recommended Solution |
|-------------|---------------------|
| Encryption at rest | Encrypted filesystems (LUKS, FileVault), cloud storage encryption (S3 SSE, GCS encryption), database TDE |
| Encryption in transit | TLS configuration on HTTP clients, load balancers, or reverse proxies |
| Key management | AWS KMS, GCP KMS, Azure Key Vault, HashiCorp Vault - at the infrastructure layer |

## Consequences

### Positive
- Simpler codebase without encryption stubs and unimplemented features
- Clear documentation about what fapilog does and doesn't do
- Users aren't misled by configuration options that don't work
- Encourages proper infrastructure-level encryption practices

### Negative
- Users expecting built-in encryption must implement it elsewhere
- May require documentation to guide users toward infrastructure solutions

### Actions Taken
- Removed `EncryptionSettings` documentation from enterprise.md
- Removed `encrypt_audit_logs` from CompliancePolicy examples
- Removed encryption references from compliance framework mappings
- Updated "At a Glance" table to remove encryption from Data Protection

### Future Consideration
The `EncryptionSettings` model and `encrypt_audit_logs` field remain in the codebase as deprecated stubs. A future cleanup story could remove them entirely, or they could be repurposed if a valid use case emerges (e.g., field-level encryption for specific sensitive values before they reach sinks).
