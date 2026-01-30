# Redactors

Plugins that mask or remove sensitive data.

!!! warning "PII in Message Strings Is Not Redacted"

    Redactors only process **structured fields** in the log envelope.
    PII embedded in the message string will pass through unchanged.

    ```python
    # UNSAFE - email will NOT be redacted
    logger.info(f"User {email} logged in")

    # SAFE - email field will be redacted
    logger.info("User logged in", email=email)
    ```

    See [PII Showing Despite Redaction](../../troubleshooting/pii-showing-despite-redaction.md)
    for more details.

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

Redactors run after enrichers and before sinks.
