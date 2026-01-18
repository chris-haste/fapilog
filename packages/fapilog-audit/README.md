# fapilog-audit

Enterprise compliance audit trail add-on for fapilog.

## Installation

```bash
pip install fapilog-audit
```

## Configuration

**Important:** fapilog-audit is an external plugin. External plugins are disabled by default for security. You must explicitly allow it.

### Option 1: Plugin Allowlist (Recommended)

```python
from fapilog import Settings, get_logger

settings = Settings(
    plugins={"allowlist": ["audit"]},
    core={"sinks": ["audit"]},
)
logger = get_logger(settings=settings)
```

### Option 2: Environment Variables

```bash
export FAPILOG_PLUGINS__ALLOWLIST='["audit"]'
export FAPILOG_CORE__SINKS='["audit"]'
```

### Option 3: Allow All External Plugins (Less Secure)

```python
settings = Settings(
    plugins={"allow_external": True},
    core={"sinks": ["audit"]},
)
```

## Complete Working Example

```python
from fapilog import Settings, get_logger
from fapilog_audit import AuditTrail, CompliancePolicy, ComplianceLevel

settings = Settings(
    plugins={"allowlist": ["audit"]},
    core={"sinks": ["audit"]},
)
logger = get_logger(settings=settings)
logger.info("Audit logging configured")
```

## Direct Usage

You can also use AuditTrail directly without the plugin system:

```python
from fapilog_audit import AuditTrail, CompliancePolicy, ComplianceLevel

trail = AuditTrail(policy=CompliancePolicy(level=ComplianceLevel.HIPAA))
await trail.start()
await trail.log_security_event(...)
await trail.stop()
```

## Migration from fapilog.core

If you previously imported audit functionality from fapilog core:

```python
# Old (no longer works)
from fapilog.core.audit import AuditTrail

# New
from fapilog_audit import AuditTrail
```
