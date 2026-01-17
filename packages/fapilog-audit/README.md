# fapilog-audit

Enterprise compliance audit trail add-on for fapilog.

## Installation

```bash
pip install fapilog-audit
```

## Usage

```python
from fapilog_audit import AuditSink, AuditTrail, CompliancePolicy, ComplianceLevel

# Use with fapilog pipeline (auto-discovered via entry point)
# Just install fapilog-audit and configure in settings

# Or use AuditTrail directly
trail = AuditTrail(policy=CompliancePolicy(level=ComplianceLevel.HIPAA))
await trail.start()
await trail.log_security_event(...)
```

## Migration from fapilog.core

If you previously imported audit functionality from fapilog core:

```python
# Old (no longer works)
from fapilog.core.audit import AuditTrail

# New
from fapilog_audit import AuditTrail
```
