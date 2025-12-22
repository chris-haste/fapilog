# Redactors

Plugins that mask or remove sensitive data.

## Contract

Implement `BaseRedactor.redact(entry: dict) -> dict` (async). Return the updated entry; contain errors so the pipeline continues.

## Built-in redactors

- **field-mask**: masks configured field names (from `sensitive_fields_policy`).
- **regex-mask**: masks values matching sensitive patterns (default regex covers common secrets).
- **url-credentials**: strips credentials from URL-like strings.

## Configuration

- Enable/disable: `FAPILOG_CORE__ENABLE_REDACTORS`
- Order: `FAPILOG_CORE__REDACTORS_ORDER`
- Guardrails: `FAPILOG_CORE__REDACTION_MAX_DEPTH`, `FAPILOG_CORE__REDACTION_MAX_KEYS_SCANNED`
- Sensitive fields: `FAPILOG_CORE__SENSITIVE_FIELDS_POLICY`

Redactors run after enrichers and before sinks.*** End Patch
