# Audit Trail

The `AuditTrail` class provides structured compliance/audit logging. It queues events asynchronously and flushes them to disk with integrity metadata.

## Key Methods

- `start()` / `stop()` - Begin/terminate processing. `stop()` now drains pending events to storage.
- `drain()` - Manually flush queued events without stopping the worker.
- `log_security_event(event_type, message, **metadata)` - Record security events (e.g., authentication/authorization failures).
- `log_data_access(resource, operation, *, user_id=None, data_classification=None, contains_pii=False, contains_phi=False, **metadata)` - Record data access/modification events.
- `verify_chain(events)` - Validate hash-chain integrity for a collection of `AuditEvent` objects.
- `verify_chain_from_storage()` - Load events from `storage_path` and validate the chain.

## Hash Chain Fields

Each `AuditEvent` now includes:

- `sequence_number` - Monotonic counter for gap detection
- `previous_hash` - SHA-256 of the prior event
- `checksum` - SHA-256 of the current event payload

These are populated automatically when events are stored; use `verify_chain`/`verify_chain_from_storage` to validate integrity.
