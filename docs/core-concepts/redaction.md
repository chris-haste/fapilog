# Redaction



Mask sensitive data before it reaches sinks.

## Built-in redactors

- **field-mask**: masks configured fields (from `core.sensitive_fields_policy`).
- **regex-mask**: masks values matching sensitive patterns (default regex covers passwords, tokens, emails, etc.).
- **url-credentials**: strips `user:pass@` credentials from URL-like strings.

## Defaults and configuration

- Enabled by default: `core.enable_redactors=True`.
- Default order: `core.redactors_order=["field-mask","regex-mask","url-credentials"]`.
- Guardrails: `core.redaction_max_depth`, `core.redaction_max_keys_scanned` limit traversal.

Override via env:

```bash
export FAPILOG_CORE__ENABLE_REDACTORS=true
export FAPILOG_CORE__SENSITIVE_FIELDS_POLICY=password,api_key,secret,token
export FAPILOG_CORE__REDACTION_MAX_DEPTH=8
export FAPILOG_CORE__REDACTION_MAX_KEYS_SCANNED=5000
```

## Usage notes

- Redactors run after enrichment, before sinks.
- Keep the order deterministic; regex runs after field masks by default.
- If you disable redactors, sensitive fields will flow to sinks unmasked.

See also: plugins/redactors for implementation details.
