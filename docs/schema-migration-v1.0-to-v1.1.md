# Schema Migration Guide: v1.0 to v1.1

This guide documents the breaking changes in log schema v1.1 and how to update your code.

## Overview

Schema v1.1 introduces semantic field groupings to improve log analysis and fix the internal schema mismatch between `build_envelope()` and `serialize_envelope()`.

## Breaking Changes

### Schema Changes

| Change | v1.0 | v1.1 |
|--------|------|------|
| User data field | `metadata` | `data` |
| Correlation ID | `correlation_id` (top-level) | `context.correlation_id` |
| Timestamp format | POSIX float | RFC3339 string with Z suffix |
| Exception info | `metadata.error.*` | `diagnostics.exception.error.*` |

### New Semantic Groupings

v1.1 organizes fields into three semantic groups:

```python
{
    "timestamp": str,      # RFC3339 UTC with Z suffix (e.g., "2024-01-15T10:30:00.123Z")
    "level": str,          # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "message": str,        # Human-readable log message
    "logger": str,         # Logger name
    "context": {           # Request/trace identifiers (WHO/WHAT)
        "correlation_id": str,
        "request_id": str | None,
        "user_id": str | None,
        "tenant_id": str | None,
        "trace_id": str | None,
        "span_id": str | None,
    },
    "diagnostics": {       # Runtime/operational context (WHERE/system state)
        "exception": {...} | None,
    },
    "data": {...},         # User-provided structured data
}
```

| Field | Purpose | Example Values |
|-------|---------|----------------|
| `context` | WHO/WHAT request context | correlation_id, user_id, request_id, trace_id, span_id, tenant_id |
| `diagnostics` | WHERE/system state | exception info, service metadata |
| `data` | Business/user data | All other fields from extra and bound_context |

## Code Migration

### Accessing Fields

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

**Before (v1.0):**
```python
FieldMaskRedactor(config={"fields_to_mask": ["metadata.password"]})
```

**After (v1.1):**
```python
FieldMaskRedactor(config={"fields_to_mask": ["data.password"]})
```

### Log Parser Updates

If you have downstream log parsers or analytics queries, update field paths:

| v1.0 Path | v1.1 Path |
|-----------|-----------|
| `$.correlation_id` | `$.context.correlation_id` |
| `$.metadata.*` | `$.data.*` |
| `$.metadata.error.type` | `$.diagnostics.exception.error.type` |
| `$.metadata.error.message` | `$.diagnostics.exception.error.message` |

### Context Field Routing

Context fields (`request_id`, `user_id`, `tenant_id`, `trace_id`, `span_id`) are automatically routed:
- From `bound_context` to `context` dict
- From `extra` to `context` dict (overrides bound_context)
- NOT duplicated in `data`

All other fields go to `data`.

## References

- [ADR-0003: Canonical Log Schema v1.1](https://github.com/chris-haste/fapilog/blob/main/docs/adr/0003-canonical-log-schema-v1.1.md)
- Story 1.26 (see `docs/stories/`)
- JSON Schema: `jsonschema/log_envelope_v1.json`
