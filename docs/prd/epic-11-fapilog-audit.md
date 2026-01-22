# Epic 11: fapilog-audit Enterprise Audit Trail

**Epic Goal**: Deliver a production-solid, enterprise-grade audit trail package with tamper-evident logging, pluggable storage, compliance alerting, and comprehensive test coverage.

**Package**: `fapilog-audit` (separate installable package)

**Current State**: Functional foundation with 52% test coverage. Core audit trail works but lacks enterprise-grade tamper-evident features and pluggable interfaces.

---

## Roadmap Overview

### Phase 1: Foundation Hardening (Complete)
Stories that established the basic audit trail functionality.

| Story | Title | Status |
|-------|-------|--------|
| 1.22 | Compliance Validation Integration | Complete |
| 4.28 | Non-Blocking Audit Trail File I/O | Complete |
| 4.29 | Audit Encryption Configuration Accuracy | Complete |
| 4.43 | Audit Trail Instance Management | Complete |

### Phase 2: Test Coverage & Quality
Bring test coverage to production standards before adding new features.

| Story | Title | Status |
|-------|-------|--------|
| 11.1 | fapilog-audit Test Coverage to 90% | Ready |

### Phase 3: Pluggable Interfaces
Enable enterprise integrations through well-defined extension points.

| Story | Title | Status | Dependencies |
|-------|-------|--------|--------------|
| 4.10 | Pluggable Audit Storage Interface | Planned | None |
| 4.11 | Audit Integrity (HMAC) | Planned | None |
| 4.12 | Alerting Interface | Planned | 4.10 |

### Phase 4: Tamper-Evident Logging (fapilog-tamper)
Cryptographic tamper-evidence for regulated environments requiring provable log integrity.

| Story | Title | Status | Dependencies |
|-------|-------|--------|--------------|
| 4.14 | fapilog-tamper Package Bootstrap | Ready | None |
| 4.15 | IntegrityEnricher and ChainState Persistence | Ready | 4.14 |
| 4.16 | SealedSink Wrapper and Manifest Generation | Ready | 4.14, 4.15 |
| 4.17 | Verification API and CLI | Ready | 4.14, 4.15, 4.16 |
| 4.18 | Enterprise Key Management Integration | Ready | 4.14-4.17 |

---

## Story Details

### Story 11.1: fapilog-audit Test Coverage to 90%

**Status:** Ready
**Priority:** High
**Effort:** Medium (2-3 days)
**Dependencies:** None

#### Context

Current test coverage is 52% line / 22% branch. The project standard requires 90% coverage. Before adding new features, the existing codebase must be properly tested to prevent regressions.

#### Acceptance Criteria

1. Line coverage >= 90% for all modules in `src/fapilog_audit/`
2. Branch coverage >= 80% for all modules
3. All edge cases in `audit.py` (917 lines) covered
4. All compliance validation paths tested
5. Error handling paths tested
6. Async behavior tested under concurrent load

#### Modules Requiring Coverage

| Module | Current | Target | Gap |
|--------|---------|--------|-----|
| `audit.py` | ~49% | 90% | ~375 lines |
| `compliance.py` | ~60% | 90% | ~60 lines |
| `sink.py` | ~55% | 90% | ~55 lines |

#### Test Categories Needed

- Unit tests for all public API methods
- Edge case tests (empty inputs, boundary conditions)
- Error path tests (invalid configs, I/O failures)
- Async concurrency tests
- Integration tests with fapilog core

---

### Story 4.10: Pluggable Audit Storage Interface

**Status:** Planned
**Priority:** High
**Effort:** Medium (2-3 days)
**Dependencies:** None

#### Context

Currently `AuditTrail` writes to local files only. Enterprise users need to route audit events to databases, cloud storage, or SIEM platforms.

#### Acceptance Criteria

1. `StorageBackend` protocol defined with async `write()`, `read()`, `close()` methods
2. `FileStorageBackend` implements protocol (current behavior)
3. `AuditTrail` accepts optional `storage_backend` parameter
4. Backend is pluggable at runtime without code changes
5. Documentation shows how to implement custom backends

#### Example Usage

```python
from fapilog_audit import AuditTrail
from fapilog_audit.backends import PostgresBackend

trail = AuditTrail(
    storage_backend=PostgresBackend(connection_string="...")
)
```

---

### Story 4.11: Audit Integrity (HMAC)

**Status:** Planned
**Priority:** High
**Effort:** Medium (2-3 days)
**Dependencies:** None

#### Context

Audit events need cryptographic integrity verification. HMAC-SHA256 provides tamper detection without requiring PKI infrastructure.

#### Acceptance Criteria

1. Optional HMAC-SHA256 computation per event
2. Key sourced from environment variable or file path
3. HMAC stored in event metadata
4. Verification utility to check event integrity
5. Configuration via `AuditTrail` or `AuditSinkConfig`

---

### Story 4.12: Alerting Interface

**Status:** Planned
**Priority:** Medium
**Effort:** Medium (2-3 days)
**Dependencies:** 4.10

#### Context

Compliance alerts (policy violations, security events) need routing to external systems without coupling audit core to specific providers.

#### Acceptance Criteria

1. `AlertDispatcher` protocol with `dispatch(alert)` method
2. `NoopAlertDispatcher` as default (logs only)
3. Alert types: `compliance_violation`, `security_event`, `integrity_failure`
4. Pluggable dispatchers for Slack, PagerDuty, webhooks
5. Alert batching and rate limiting

---

## Definition of Done (Epic Level)

- [ ] Test coverage >= 90% across all fapilog-audit modules
- [ ] All Phase 3 stories (pluggable interfaces) complete
- [ ] All Phase 4 stories (fapilog-tamper) complete
- [ ] Documentation updated for all new features
- [ ] Migration guide for users upgrading from pre-extraction audit code
- [ ] Package published to PyPI as stable (1.0.0)

---

## Related Documents

- [Story 4.44: Extract Audit to Separate Package](../stories/4.44.extract-audit-to-separate-package.md) (Complete)
- [Epic 4: Enterprise Compliance & Observability](epic-4-enterprise-compliance-observability.md)
- [fapilog-audit stories](../stories/fapilog-audit/)
