# ADR-0003: Canonical Log Schema v1.1

**Status:** Accepted
**Date:** 2026-01-19
**Story:** 1.26 - Canonical Log Schema v1.1

## Context

The v1.0 log schema had a mismatch between `build_envelope()` and `serialize_envelope()`:
- `build_envelope()` returned `{timestamp, level, message, logger, correlation_id, metadata}`
- `serialize_envelope()` expected `{timestamp, level, message, context, diagnostics}`

This schema mismatch caused serialization failures in the pipeline.

## Decision

Adopt a canonical v1.1 schema with semantic field groupings:

```python
{
    "timestamp": str,      # RFC3339 UTC with Z suffix (millisecond precision)
    "level": str,          # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "message": str,        # Human-readable log message
    "logger": str,         # Logger name
    "context": {           # Request/trace identifiers
        "correlation_id": str,
        "request_id": str | None,
        "user_id": str | None,
        "tenant_id": str | None,
        "trace_id": str | None,
        "span_id": str | None,
    },
    "diagnostics": {       # Runtime/operational context
        "exception": {...} | None,
    },
    "data": {...},         # User-provided structured data
}
```

### Field Semantics

| Field | Purpose | Example Values |
|-------|---------|----------------|
| `context` | WHO/WHAT request context | correlation_id, user_id, request_id, trace_id, span_id, tenant_id |
| `diagnostics` | WHERE/system state | exception info, service metadata |
| `data` | Business/user data | All other fields from extra and bound_context |

### Context Field Routing

Context fields (`request_id`, `user_id`, `tenant_id`, `trace_id`, `span_id`) are automatically routed:
- From `bound_context` to `context` dict
- From `extra` to `context` dict (overrides bound_context)
- NOT duplicated in `data`

All other fields go to `data`.

## Breaking Changes

### Schema Changes
- `metadata` field removed (replaced by `data`)
- `correlation_id` moved from top-level to `context.correlation_id`
- `timestamp` now RFC3339 string (was POSIX float)
- Exception info moved from flat fields to `diagnostics.exception`

### Migration Guide

**Before (v1.0):**
```python
# Access correlation_id
corr_id = event["correlation_id"]

# Access user data
user_data = event["metadata"]

# Access exception info
error_type = event["metadata"]["error.type"]
```

**After (v1.1):**
```python
# Access correlation_id
corr_id = event["context"]["correlation_id"]

# Access user data
user_data = event["data"]

# Access exception info
error_type = event["diagnostics"]["exception"]["error.type"]
```

### Redactor Path Changes

Update redactor configurations to use new paths:

```python
# Before (v1.0)
FieldMaskRedactor(config={"fields_to_mask": ["metadata.password"]})

# After (v1.1)
FieldMaskRedactor(config={"fields_to_mask": ["data.password"]})
```

## Consequences

### Positive
- Semantic field groupings improve log analysis
- Clear separation of concerns (context vs data vs diagnostics)
- `build_envelope()` and `serialize_envelope()` now produce/consume compatible schemas
- RFC3339 timestamps are human-readable and standard

### Negative
- Breaking change requires downstream consumer updates
- Redactor paths need updating

### Neutral
- JSON schema updated to v1.1
- All envelope tests updated for new schema

## References

- Story: 1.26 - Canonical Log Schema v1.1 (see `docs/stories/`)
- JSON Schema: `jsonschema/log_envelope_v1.json`
