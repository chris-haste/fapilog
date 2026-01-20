---
orphan: true
---

# Audit Sink (Compliance Trail)

The audit sink exposes the existing `AuditTrail` system as a standard plugin so you can turn on compliance logging with configuration instead of custom wiring.

## Enable

```python
from fapilog import Settings, get_logger

settings = Settings()
settings.core.sinks = ["audit"]
settings.sink_config.audit.storage_path = "./audit_logs"
settings.sink_config.audit.compliance_level = "soc2"

logger = get_logger(name="app", settings=settings)
logger.info("viewed record", user_id="u-123", contains_pii=True)
```

## Configuration

`sink_config.audit` controls the sink:

- `compliance_level` — `basic`, `sox`, `hipaa`, `gdpr`, `pci_dss`, `soc2`, `iso27001`
- `storage_path` — directory for JSONL audit files
- `retention_days` — retention window (metadata only; manage rotation/archival per policy)
- `require_integrity` — keep hash-chain integrity fields for tamper detection
- `real_time_alerts` — enable policy-driven alert detection (delivery requires custom integration; see [Enterprise Features](../enterprise.md))

## Event Mapping

- Error/critical log levels map to `ERROR_OCCURRED`
- Warning maps to `COMPLIANCE_CHECK`
- All other levels map to `DATA_ACCESS`
- Set `audit_event_type` in `logger.*` metadata to override per-entry

User/session context is lifted from log metadata when present (`user_id`, `session_id`, `request_id`, `contains_pii`, `contains_phi`).

## Verification

Audit files include sequence numbers and hash-chain fields. Verify integrity at any time:

```python
from pathlib import Path
from fapilog.core.audit import AuditTrail

trail = AuditTrail(storage_path=Path("./audit_logs"))
result = await trail.verify_chain_from_storage()
assert result.valid
```

Hash-chain integrity is preserved across sink start/stop; each write updates the chain and sequence numbers in order.
