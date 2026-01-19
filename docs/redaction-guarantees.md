# Redaction Guarantees

This document defines the guarantees, guardrails, and configuration for data redaction in Fapilog.

> **Important:** Redaction is disabled by default. Features below only apply when enabled via `preset="production"` or explicit redactor configuration. See [Reliability Defaults](user-guide/reliability-defaults.md) for details.

## Guarantees

- URL credentials are scrubbed from string values resembling `scheme://user:pass@host...` across all fields **when the `url_credentials` redactor is enabled**.
- Explicitly configured dotted field paths are masked, including nested objects and lists, **when the `field_mask` redactor is enabled**. Arrays support `*`/`[*]` wildcard and numeric indices.
- Regex-based masks are applied to dotted field paths that match configured regular expressions **when the `regex_mask` redactor is enabled**.
- Redactors never raise upstream; failures are recorded via diagnostics with a `{ redactor, reason }` payload.

## Deterministic Order

Default order for built-in redactors:

1. `field-mask`
2. `regex-mask`
3. `url-credentials`

Rationale: explicit path masking first, then broader regex matching, then URL credential sanitization for any remaining strings.

Configure via `core.redactors_order`.

## Guardrails

- `core.redaction_max_depth` (default: 6)
- `core.redaction_max_keys_scanned` (default: 5000)

Exceeding limits results in best-effort redaction and emits a diagnostics entry. Redactors read these guardrails when configured by the runtime.

## Centralized Pipeline Placement

Redaction runs in the logger worker loop before envelope serialization and sink emission. Pipeline: enrichers → redactors → envelope serialization → sinks.

## Example Configuration

```yaml
core:
  redactors_order: ["field-mask", "regex-mask", "url-credentials"]
  redaction_max_depth: 6
  redaction_max_keys_scanned: 5000
redactors:
  field_mask:
    paths:
      - context.user.email
      - context.auth.token
      - diagnostics.secrets[*].value
  regex_mask:
    patterns:
      - "(?i)password=([^&\\s]+)"
      - "(?i)api[_-]?key([=:])([A-Za-z0-9_-]{16,})"
```

## Example Before/After

Input log (pre-redaction):

```json
{
  "message": "login",
  "context": {
    "user": { "email": "alice@example.com" },
    "auth": { "token": "s3cr3t" },
    "url": "https://alice:pa55@service.local/path?password=hunter2"
  }
}
```

Output log (post-redaction, before envelope):

```json
{
  "message": "login",
  "context": {
    "user": { "email": "***" },
    "auth": { "token": "***" },
    "url": "https://service.local/path?password=***"
  }
}
```
